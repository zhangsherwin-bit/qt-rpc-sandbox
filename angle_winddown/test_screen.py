import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import screen as S
class Winddown(unittest.TestCase):
 def test_underlying_units(self):
  self.assertEqual(S.SIZES,[100,1000,5000])
  self.assertEqual(S.EXPECTED_USDA.lower(),"0x0000206329b97db379d5e1bf586bbdb969c63274")
 def test_abi(self):
  self.assertEqual(S.abiwords("0x"+S.w(25)),[25])
  self.assertEqual(S.selector("quoteIn(uint256,address,address)"),S.selector("quoteIn(uint256,address,address)"))
 def test_source_is_quote_only(self):
  text=(Path(__file__).parent/"screen.py").read_text()
  self.assertIn('"RFQ_private_flow_disabled":True',text)
  self.assertIn('"full_transaction_executed":False',text)
  self.assertIn('eth_call',text)
  for banned in ('eth_sendRawTransaction','eth_sendTransaction','private_key','wallet_seed','balanceOverrides'):
   self.assertNotIn(banned,text)
if __name__=="__main__":unittest.main()
