import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scan as R
class TestYearn(unittest.TestCase):
 def test_kick_topic(self):self.assertEqual(len(R.KICK),66)
 def test_different_assets(self):self.assertNotEqual(R.USDC,R.CRVUSD)
 def test_kick_universe(self):
  xs=R.freeze(Path("input_yearn"))
  self.assertEqual(len(xs),12)
  self.assertTrue(all(x["from"]==R.USDC and x["want"]==R.CRVUSD for x in xs))
  self.assertTrue(all(x["version"]=="1.0.4" for x in xs))
 def test_unique_economic_kicks(self):
  xs=R.freeze(Path("input_yearn"))
  self.assertEqual(len({(x["kick_tx"],x["from"]) for x in xs}),len(xs))
 def test_no_trading_actions(self):
  s=(Path(__file__).parent/"scan.py").read_text()
  for q in ("eth_sendTransaction","eth_sendRawTransaction","private_key","wallet_seed"):
   self.assertNotIn(q,s)
 def test_explicit_no_cash_claim(self):
  s=(Path(__file__).parent/"scan.py").read_text()
  self.assertIn('"full_execution":False',s)
  self.assertIn('"not_executable_or_captured_proof"',s)
if __name__=="__main__":unittest.main()
