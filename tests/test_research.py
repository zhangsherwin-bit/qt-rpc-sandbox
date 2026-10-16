import importlib.util,unittest,json,tempfile
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/'src'/'research.py'
spec=importlib.util.spec_from_file_location('research',p);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class TestResearch(unittest.TestCase):
 def test_selector(self):
  self.assertEqual(r.call('balanceOf(address)',r.CORE)[:10],'0x70a08231')
  self.assertEqual(len(r.call('redeem(uint256,address,address)',1,r.CORE,r.CORE)),202)
 def test_only_read_rpc(self):
  with self.assertRaises(ValueError):r.rpc(r.BASE,'forbidden','eth_sendRawTransaction',[])
 def test_endpoint_allowlist(self):
  with self.assertRaises(ValueError):r.rpc('https://other.invalid','x','eth_call',[])
 def test_abi_single_entry(self):
  payload=r.multi_payload([(r.CORE,'0x12345678')]);b=bytes.fromhex(payload[10:])
  self.assertEqual(r.num(b,0),32);self.assertEqual(r.num(b,32),1);self.assertEqual(r.num(b,64),32)
  self.assertEqual(r.addr(r.num(b,96)),r.CORE)
  self.assertEqual(r.num(b,128),1);self.assertEqual(r.num(b,160),96);self.assertEqual(r.num(b,192),4)
  self.assertEqual(b[224:228],bytes.fromhex('12345678'))
 def test_multi_return_true_false(self):
  tails=[]
  for ok,data in [(1,b'abc'),(0,b'')]:tails.append(r.word(ok)+r.word(64)+r.word(len(data))+data+b'\0'*((-len(data))%32))
  raw='0x'+(r.word(32)+r.word(2)+r.word(64)+r.word(64+len(tails[0]))+b''.join(tails)).hex()
  self.assertEqual(r.decode_multi(raw),[(True,'0x616263'),(False,'0x')])
 def test_missing_not_zero(self):
  self.assertIsNone(r.simple({'a':{'ok':False,'raw':'0x'}},'a'))
  self.assertEqual(r.simple({'a':{'ok':True,'integer':'0'}},'a'),0)
 def test_word_bounds(self):
  with self.assertRaises(ValueError):r.num(b'123',0)
 def test_bad_address(self):
  with self.assertRaises(ValueError):r.addr(2**160)
if __name__=='__main__':unittest.main()
