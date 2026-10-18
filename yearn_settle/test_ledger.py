import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ledger as L
class YearnLedgerTests(unittest.TestCase):
 def test_frozen_12_settlements(self):
  xs=L.freeze(Path('input_yearn'))
  self.assertEqual(len(xs),12)
  self.assertEqual(len({x['settle_tx'] for x in xs}),12)
  self.assertTrue(all(x['age_seconds']>0 for x in xs))
 def test_positive_amount_is_not_profit(self):
  self.assertEqual((3000*10**6)-(2999*10**18)//10**12,1000000)
 def test_refund_token_addresses_match(self):
  self.assertEqual(len(L.FROM),42)
  self.assertNotEqual(L.FROM,L.WANT)
 def test_no_live_actions(self):
  s=(Path(__file__).parent/'ledger.py').read_text()
  for bad in ('eth_sendTransaction','eth_sendRawTransaction','wallet_seed','private_key'):
   self.assertNotIn(bad,s)
 def test_explicit_no_profit_claim(self):
  self.assertIn('cash_profit_verified":False',(Path(__file__).parent/'ledger.py').read_text())
if __name__=='__main__':unittest.main()
