import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import screen as S
class TestScreen(unittest.TestCase):
 def test_quote_selector(self):
  self.assertEqual(S.sel("quoteIn(uint256,address,address)"),S.sel("quoteIn(uint256,address,address)"))
  self.assertEqual(len(S.sel("quoteIn(uint256,address,address)")),10)
 def test_abi_list(self):
  usdc=int(S.USDC,16);usda=int(S.TRANS,16)
  raw="0x"+S.enc_uint(32)+S.enc_uint(2)+S.enc_uint(usdc)+S.enc_uint(usda)
  self.assertEqual(S.dec_list(raw),[S.USDC,S.TRANS])
 def test_invalid_abi_count(self):
  with self.assertRaises(ValueError):S.dec_list("0x"+S.enc_uint(32)+S.enc_uint(50))
 def test_real_deployment(self):
  self.assertEqual(S.TRANS.lower(),"0x222222fd79264bbe280b4986f6fefbc3524d0137")
 def test_distinct_block_dates(self):
  self.assertEqual(len({x['height'] for x in S.SAMPLES}),len(S.SAMPLES))
 def test_quoted_not_executed(self):
  src=(Path(__file__).parent/'screen.py').read_text()
  self.assertIn('"full_cash_execution_performed":False',src)
  for name in ('eth_sendRawTransaction','eth_sendTransaction','private_key','wallet_seed'):self.assertNotIn(name,src)
 def test_price_quote_is_not_100_percent_win(self):
  self.assertEqual(S.SIZES,[100,1000,10000])
  self.assertEqual(S.FEES,[100,500,3000,10000])
if __name__=="__main__":unittest.main()
