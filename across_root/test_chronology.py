import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import chronology as C
class ChronologyTests(unittest.TestCase):
 def test_historical_anchor_order(self):self.assertLess(C.DEPOSIT_BLOCK,C.REFUND_BLOCK)
 def test_same_exact_recipient_amount(self):
  self.assertEqual(C.REFUND_AMOUNT_RAW,110550000)
  self.assertEqual(C.REPAYMENT_ADDRESS,'0x490632638389f5e29bed11a35b8cc56726bea895')
 def test_two_topics(self):
  self.assertEqual(len(C.RELAY),66);self.assertEqual(len(C.PROPOSE),66)
 def test_no_repeated_transfer_or_trade(self):
  src=(Path(__file__).parent/'chronology.py').read_text()
  for denied in ('eth_sendRawTransaction','eth_sendTransaction','wallet_seed','private_key'):self.assertNotIn(denied,src)
 def test_refund_before_complete_proof(self):
  self.assertIn("deposit_level_refund_attribution_proven':False",(Path(__file__).parent/'chronology.py').read_text())
if __name__=='__main__':unittest.main()
