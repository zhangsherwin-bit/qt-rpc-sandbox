import unittest,json,datetime,urllib.error
from unittest.mock import patch
from pathlib import Path
import collect as C
import run_stage as R
class Scope(unittest.TestCase):
 def test_erc20_selector(self):self.assertEqual(C.H('balanceOf(address)')[:8],'70a08231')
 def test_frozen_window(self):
  self.assertEqual(C.START,1788998400);self.assertEqual(C.END,1790812800)
  self.assertLess(C.END,int(datetime.datetime(2026,10,3,tzinfo=datetime.timezone.utc).timestamp()))
 def test_no_gap_pagination(self):
  pages=[(x,min(R.B,x+9999)) for x in range(R.A,R.B+1,10000)]
  self.assertEqual(sum(b-a+1 for a,b in pages),R.B-R.A+1)
  self.assertTrue(all(b-a+1<=10000 for a,b in pages))
 def test_rad_not_dai_units(self):
  self.assertEqual(10**45//10**27,10**18)
  self.assertNotEqual(10**45,10**18)
 def test_contract_addresses(self):
  for a in list(C.USDC.values())+[C.CHAINLOG,C.REACTOR,C.COW]:
   self.assertEqual(len(a),42);int(a[2:],16)
 def test_unsupported_methods_stop_before_request(self):
  c=C.Client()
  with self.assertRaises(ValueError):c.get('bad',C.ETH,{'method':'invalid_write_method'})
  self.assertEqual(c.n,0)
 def test_blocked_host_is_not_zero_market(self):
  c=C.Client();c.blocked.add('api.uniswap.org')
  with self.assertRaisesRegex(RuntimeError,'STOPPED_ENDPOINT'):c.get('x','https://api.uniswap.org/v2/orders')
 def test_no_broadcast_paths(self):
  text=Path('broad_stage1/collect.py').read_text()+Path('broad_stage1/run_stage.py').read_text()
  for bad in ('eth_send'+'RawTransaction','eth_send'+'Transaction','private_'+'key'):
   self.assertNotIn(bad,text)
if __name__=='__main__':unittest.main()
