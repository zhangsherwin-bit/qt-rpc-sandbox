import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import quoted_cash as C
class MultiHopTests(unittest.TestCase):
 def test_real_cases(self):
  self.assertEqual(len(C.CASES),3)
  self.assertEqual(len(set(e["tx"] for e in C.CASES)),3)
  self.assertTrue(all(e["debt"]>0 and e["collateral"]>0 for e in C.CASES))
 def test_two_hop_abi(self):
  path=C.dynamic_path([C.WETH,C.USDC,C.WBTC],[500,3000])
  self.assertEqual(len(path),66)
  self.assertEqual(path[:20],bytes.fromhex(C.WETH[2:]))
  self.assertEqual(path[20:23],b'\x00\x01\xf4')
  self.assertEqual(path[-20:],bytes.fromhex(C.WBTC[2:]))
 def test_bounded(self):
  self.assertEqual(C.FEES,[100,500,3000])
 def test_no_trade(self):
  src=(Path(__file__).parent/"quoted_cash.py").read_text()
  self.assertIn('"actual_cash_execution":False',src)
  for word in ("eth_sendRawTransaction","eth_sendTransaction","balanceOverrides","storageOverrides","private_key"):
   self.assertNotIn(word,src)
if __name__=="__main__":unittest.main()
