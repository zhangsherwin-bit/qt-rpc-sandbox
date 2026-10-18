import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import discover as E
class Euler(unittest.TestCase):
 def test_real_event_signature(self):
  self.assertEqual(len(E.keccak_hex('Liquidate(address,address,address,uint256,uint256)')),66)
 def test_address_abi(self):
  a='0x'+'22'*20;self.assertEqual(E.decode_abi_address('0x'+'0'*24+a[2:]),a)
 def test_invalid_padding(self):
  with self.assertRaises(ValueError):E.decode_abi_address('0x'+'ff'*32)
 def test_distinct_historical_windows(self):
  self.assertEqual(len(E.BLOCKS),3)
  self.assertTrue(all(hi-lo<10000 for lo,hi in E.BLOCKS))
  self.assertLess(E.BLOCKS[0][1],E.BLOCKS[1][0])
  self.assertLess(E.BLOCKS[1][1],E.BLOCKS[2][0])
 def test_capped_vaults(self):
  self.assertLessEqual(E.MAX_SELECTED,6)
  self.assertLessEqual(E.MAX_REQUESTS,130)
 def test_no_trading_keys(self):
  s=(Path(__file__).parent/'discover.py').read_text()
  for v in ('eth_sendRawTransaction','eth_sendTransaction','wallet_seed','private_key','personal_sign','storageOverrides'):
   self.assertNotIn(v,s)
 def test_indicative_only(self):
  s=(Path(__file__).parent/'discover.py').read_text()
  self.assertIn('"no_fills_or_cash_profit_tested":True',s)
  self.assertIn('postblock_same_asset_cash_preview_raw',s)
if __name__=='__main__':unittest.main()
