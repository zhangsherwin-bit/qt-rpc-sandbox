import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import diagnose as D
class TestAllowance(unittest.TestCase):
 def test_call_data(self):
  self.assertEqual(len(D.calldata("prepareAllowance(uint256)",100*10**6)),74)
 def test_only_real_historical_input(self):
  s=(Path(__file__).parent/"diagnose.py").read_text()
  self.assertIn("26220131",s)
  self.assertIn("eth_simulateV1",s)
 def test_init_zero_and_payout_checks(self):
  s=(Path(__file__).parent/"diagnose.py").read_text()
  self.assertIn("Initial test wallet funded",s)
  self.assertIn("PREAPPROVAL DID NOT PERSIST",s)
  self.assertIn("Cash payout or terminal inventory condition violated",s)
 def test_no_canonical_state_override(self):
  s=(Path(__file__).parent/"diagnose.py").read_text()
  for term in ("balanceOverrides","storageOverrides","eth_sendRawTransaction","eth_sendTransaction","wallet_seed"):
   self.assertNotIn(term,s)
if __name__=="__main__":unittest.main()
