import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import replay as F

class TestFiveRealEvents(unittest.TestCase):
 def test_five_unique_real_vaults(self):
  self.assertEqual(len(F.SOURCE),5)
  self.assertEqual(len(set(x["vault"] for x in F.SOURCE)),5)
  self.assertEqual(len(set(x["tx"] for x in F.SOURCE)),5)
 def test_historical_frozen_events(self):
  self.assertEqual([x["block"] for x in F.SOURCE],
                   [26171577,26175052,26193309,26194906,26194919])
  for x in F.SOURCE:
   self.assertEqual(len(x["tx"]),66)
   self.assertGreater(x["event_debt_raw"],0)
 def test_cash_is_quote_only(self):
  s=(Path(__file__).parent/"replay.py").read_text()
  self.assertIn('"cash_profit_proven":False',s)
  self.assertIn('"gross_positive_quote_only"',s)
  self.assertIn("producer payment",s)
 def test_only_read_methods(self):
  s=(Path(__file__).parent/"replay.py").read_text()
  for bad in ("eth_sendTransaction","eth_sendRawTransaction","private_key",
              "stateOverrides","storageOverrides","balanceOverrides"):
   self.assertNotIn(bad,s)
if __name__=="__main__":unittest.main()
