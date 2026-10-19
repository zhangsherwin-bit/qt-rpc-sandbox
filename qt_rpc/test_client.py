import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from qt_rpc.client import WeightedLimiter, ReadOnlyRPC, RPCFailure, AuthenticatedBudget, parse_retry_seconds, request_units, read_key_status

class Clock:
 def __init__(self):self.t=1000.0;self.waited=[]
 def now(self):return self.t
 def sleep(self,s):self.waited.append(s);self.t+=s

class Reply:
 def __init__(self,body,status=200,headers=None):
  self.raw=io.BytesIO(json.dumps(body).encode());self.status=status;self.headers=headers or {}
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def read(self,n):return self.raw.read(n)

class Sequence:
 def __init__(self,entries):self.entries=list(entries);self.headers=[]
 def __call__(self,request,timeout):
  self.headers.append(dict(request.header_items()))
  if not self.entries:raise AssertionError("unexpected RPC")
  item=self.entries.pop(0)
  if isinstance(item,Exception):raise item
  return item

def denied(code,body,headers=None):
 return HTTPError("https://rpc-eth.blockmachine.io",code,"error",headers or {},io.BytesIO(json.dumps(body).encode()))

class TestTransport(unittest.TestCase):
 def test_rate_cost_and_range_gate(self):
  self.assertEqual(request_units("eth_getLogs",[{"fromBlock":"0x1","toBlock":"0x64"}]),5)
  self.assertEqual(request_units("eth_getLogs",[{"fromBlock":"0x1","toBlock":"0x3e8"}]),10)
  self.assertEqual(request_units("eth_getLogs",[{"fromBlock":"0x1","toBlock":"0x2710"}]),25)
  with self.assertRaises(RPCFailure):request_units("eth_getLogs",[{"fromBlock":"0x1","toBlock":"0x2711"}])
  with self.assertRaises(RPCFailure):request_units("eth_sendRawTransaction",["0x1234"])

 def test_weighted_quota_prevents_429_burst(self):
  c=Clock();lim=WeightedLimiter(cap_ru=25,now=c.now,sleeper=c.sleep)
  lim.admit(10);lim.admit(10);lim.admit(10)
  self.assertGreaterEqual(sum(c.waited),60.0)
  self.assertLessEqual(sum(w for t,w in lim.events),25)

 def test_status_bearer_header_no_key_output(self):
  fake=Sequence([Reply({"status":"active","rate_limit_rpm":300,"ru_budget":10000,"ru_remaining":7899,"is_exhausted":False})])
  result=read_key_status("secret-do-not-log",opener=fake)
  self.assertEqual(result["rate_limit_rpm"],300)
  self.assertNotIn("secret",json.dumps(result))
  self.assertEqual(fake.headers[0]["Authorization"],"Bearer secret-do-not-log")

 def test_429_retry_and_archive_redacts_key(self):
  c=Clock();fake=Sequence([denied(429,{"jsonrpc":"2.0","error":{"code":-32029,"data":{"retry_after_ms":6000},"message":"limit"}}),Reply({"jsonrpc":"2.0","id":1,"result":"0x1"})])
  with tempfile.TemporaryDirectory() as folder:
   obj=ReadOnlyRPC(1,folder,api_key="dont-put-this-token-in-evidence",opener=fake,now_unix=c.now,sleeper=c.sleep,limiter=WeightedLimiter(100,now=c.now,sleeper=c.sleep),status={"auth":"authenticated","rate_limit_rpm":200,"ru_remaining":978},budget=AuthenticatedBudget({"auth":"authenticated","ru_remaining":978},approved=True))
   self.assertEqual(obj.rpc("eth_chainId",[]),"0x1")
   self.assertEqual(obj.attempted,2)
   self.assertGreaterEqual(c.waited[0],6)
   for f in Path(folder).iterdir():self.assertNotIn(b"dont-put-this-token-in-evidence",f.read_bytes())
   self.assertEqual(len(obj.logs),2)
   self.assertEqual(fake.headers[0]["Authorization"],"Bearer dont-put-this-token-in-evidence")

 def test_requires_distinct_opt_in_even_when_secret_exists(self):
  status={"auth":"authenticated","rate_limit_rpm":300,"ru_remaining":978}
  with self.assertRaises(RPCFailure) as cm:
   AuthenticatedBudget(status,approved=False)
  self.assertEqual(cm.exception.kind,"AUTHENTICATED_RU_SPENDING_NOT_APPROVED")
  with self.assertRaises(RPCFailure) as cm:
   AuthenticatedBudget({"auth":"authenticated"},approved=True)
  self.assertEqual(cm.exception.kind,"AUTHENTICATED_REMAINING_RU_UNAVAILABLE")

 def test_monthly_floor_and_per_run_limit_across_chains(self):
  status={"auth":"authenticated","rate_limit_rpm":300,"ru_remaining":978}
  shared=AuthenticatedBudget(status,reserve_floor=975,max_run_ru=2,approved=True)
  fake=Sequence([Reply({"result":"0x1"}),Reply({"result":"0x2"})])
  with tempfile.TemporaryDirectory() as folder:
   a=ReadOnlyRPC(1,Path(folder)/"eth",api_key="dummy-not-secret",status=status,opener=fake,budget=shared)
   b=ReadOnlyRPC(8453,Path(folder)/"base",api_key="dummy-not-secret",status=status,opener=fake,budget=shared)
   self.assertEqual(a.rpc("eth_chainId",[]),"0x1")
   self.assertEqual(b.rpc("eth_chainId",[]),"0x2")
   with self.assertRaises(RPCFailure) as cm:
    a.rpc("eth_chainId",[])
   self.assertEqual(cm.exception.kind,"AUTHENTICATED_RUN_RU_CAP_REACHED")
   self.assertEqual(shared.attempted_ru,2)
   self.assertEqual(a.attempted+b.attempted,2)

 def test_reserve_prevents_any_paid_calls(self):
  with self.assertRaises(RPCFailure) as cm:
   AuthenticatedBudget({"auth":"authenticated","ru_remaining":899},reserve_floor=900,approved=True)
  self.assertEqual(cm.exception.kind,"MONTHLY_RU_RESERVE_PROTECTED")

 def test_keyless_no_auth_header(self):
  fake=Sequence([Reply({"jsonrpc":"2.0","result":"0x1"})])
  with tempfile.TemporaryDirectory() as folder:
   obj=ReadOnlyRPC(1,folder,api_key="",opener=fake)
   obj.rpc("eth_chainId",[])
   self.assertNotIn("Authorization",fake.headers[0])

 def test_exhausted_budget_terminal(self):
  c=Clock();fake=Sequence([denied(429,{"error":{"code":-32030,"message":"insufficient RU"}})])
  with tempfile.TemporaryDirectory() as folder:
   obj=ReadOnlyRPC(1,folder,api_key="",opener=fake,sleeper=c.sleep)
   with self.assertRaises(RPCFailure) as cm:obj.rpc("eth_chainId",[])
   self.assertEqual(cm.exception.kind,"RU_BUDGET_EXHAUSTED")
   self.assertEqual(obj.attempted,1);self.assertTrue(obj.aborted)

 def test_request_budget_counts_retries(self):
  c=Clock();fake=Sequence([denied(429,{"error":{"code":-32029,"data":{"retry_after_ms":2000}}})])
  with tempfile.TemporaryDirectory() as folder:
   obj=ReadOnlyRPC(1,folder,api_key="",opener=fake,sleeper=c.sleep,max_requests=1)
   with self.assertRaises(RPCFailure) as cm:obj.rpc("eth_chainId",[])
   self.assertEqual(cm.exception.kind,"FIXED_HTTP_ATTEMPT_LIMIT")
   self.assertEqual(len(obj.logs),1)

 def test_live_reads_not_memoized(self):
  fake=Sequence([Reply({"result":"0x10"}),Reply({"result":"0x11"})])
  with tempfile.TemporaryDirectory() as folder:
   obj=ReadOnlyRPC(1,folder,api_key="",opener=fake)
   self.assertEqual(obj.rpc("eth_blockNumber",[]),"0x10")
   self.assertEqual(obj.rpc("eth_blockNumber",[]),"0x11")

 def test_status_bad_key_hard_fails(self):
  fake=Sequence([denied(401,{"error":{"code":-32021}})])
  with self.assertRaises(RPCFailure) as cm:read_key_status("bad-key",opener=fake)
  self.assertEqual(cm.exception.kind,"KEY_STATUS_AUTH_OR_SERVICE_FAILURE")

 def test_header_and_json_retry_delay(self):
  self.assertEqual(parse_retry_seconds({"Retry-After":"9"},{"data":{"retry_after_ms":6000}},now_unix=1000),9)
  self.assertEqual(parse_retry_seconds({},{"data":{"reset":1012}},now_unix=1000),12)

if __name__=="__main__":unittest.main()
