"""Offline bounding, inventory, and exact denomination checks."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import screen as S
class TestCometMarket(unittest.TestCase):
 def test_all_exact_market_count(self):
  self.assertEqual(sum(map(len,S.SPOKES.values())),11)
 def test_uniqueness(self):
  alladd=[v for d in S.SPOKES.values() for v in d.values()]
  self.assertEqual(len(set(alladd)),11)
 def test_base_amounts(self):
  self.assertEqual(S.choose_size("USDC",10**6),[100*10**6,1000*10**6,10000*10**6])
  self.assertEqual(S.choose_size("WETH",10**18),[10**17,10**18,10**19])
 def test_pub_safety(self):
  s=(Path(__file__).parent/"screen.py").read_text()
  for bad in ("eth_sendRawTransaction","eth_sendTransaction","personal_sign","private_key","wallet_seed"):
   self.assertNotIn(bad,s)
 def test_quotes_not_trades(self):
  s=(Path(__file__).parent/"screen.py").read_text()
  self.assertIn('"no_execution_or_income":True',s)
  self.assertIn('"complete_cash_execution":False',s)
 def test_chain_identity(self):
  self.assertEqual(set(S.SPOKES),{1,8453})
if __name__=="__main__":unittest.main()
