import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import quote as Q
class GSMTests(unittest.TestCase):
 def test_selector(self):self.assertEqual(len(Q.sig("getAvailableLiquidity()")),10)
 def test_addresses(self):
  self.assertEqual(len(Q.GHO),42);self.assertEqual(len(Q.USDC),42)
  self.assertEqual(len({x['address'] for x in Q.MODULES}),1)
 def test_abi(self):
  self.assertEqual(Q.words("0x"+Q.u(7)+Q.u(4)),[7,4])
  self.assertEqual(len(Q.u(100)),64)
 def test_snapshot_and_size(self):
  self.assertEqual(len(Q.BLOCKS),2);self.assertEqual(Q.AMOUNTS,[100,1000,10000,100000])
 def test_safety(self):
  t=(Path(__file__).parent/"quote.py").read_text()
  for x in ("eth_sendRawTransaction","eth_sendTransaction","private_key","wallet_seed"):self.assertNotIn(x,t)
  self.assertIn('"full_atomic_cash_execution":False',t)
if __name__=="__main__":unittest.main()
