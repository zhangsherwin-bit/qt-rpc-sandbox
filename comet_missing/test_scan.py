import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scan as R
class TestMissing(unittest.TestCase):
 def test_exact_previous_gap(self):
  self.assertEqual(len(R.MARKETS),5)
  self.assertNotIn("USDC",R.MARKETS)
 def test_known_chain(self):
  self.assertIn(1,R.S.RPC)
  self.assertEqual(set(R.MARKETS),set(R.D.SPOKES[1])-{"USDC"})
 def test_quote_not_cash(self):
  s=(Path(__file__).parent/"scan.py").read_text()
  self.assertIn('"no_execution_or_profit":True',s)
 def test_no_sign(self):
  s=(Path(__file__).parent/"scan.py").read_text()
  for k in ("eth_sendRawTransaction","eth_sendTransaction","private_key","wallet_seed"):
   self.assertNotIn(k,s)
if __name__=="__main__":unittest.main()
