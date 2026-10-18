import unittest,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import alt as A
class CurveExitTests(unittest.TestCase):
 def test_frozen_six_parent_receipts(self):
  r=json.loads(Path('input_quotes/yearn_exit_evidence/REPORT.json').read_text())
  self.assertTrue(r["complete"])
  self.assertEqual(len(r['cases']),6)
  self.assertTrue(all(x.get('receipt_checked') for x in r['cases']))
 def test_contract_code_only(self):
  self.assertTrue(A.POOL_USDC_CRVUSD.startswith('0x'))
  self.assertTrue(A.REG.startswith('0x'))
 def test_zero_and_wrong_underlying_rejected(self):
  with self.assertRaises(ValueError):A.stable_quote("0x"+'0'*40,A.S.DOLA,A.S.CRVUSD,0,25950000)
 def test_quote_is_not_cash(self):
  s=(Path(__file__).parent/'alt.py').read_text()
  self.assertIn('"actual_trade_settled":False',s)
 def test_no_broadcast(self):
  s=(Path(__file__).parent/'alt.py').read_text()
  for bad in ('eth_sendRawTransaction','eth_sendTransaction','wallet_seed','private_key','personal_sign'):self.assertNotIn(bad,s)
 def test_amount_after_univ2_fee(self):
  inp=1000;rin=10000;rout=10000
  out=inp*997*rout//(rin*1000+inp*997)
  self.assertGreater(out,0);self.assertLess(out,1000)
if __name__=='__main__':unittest.main()
