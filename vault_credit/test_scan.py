"""No market claims from absent data; offline scope tests."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scan as S
class TestVaultCredit(unittest.TestCase):
 def test_select_matching_asset(self):
  xs=[{'address':'0x'+'1'*40,'asset':{'address':S.USDC[1]}},
     {'address':'0x'+'2'*40,'asset':{'address':S.USDC[8453]}}]
  self.assertEqual([x['address'] for x in S.pick_vaults(xs,1)],['0x'+'1'*40])
 def test_cross_chain_market_validation(self):
  vault='0x'+'1'*40;m={'collateral_token':'8453:'+vault,'loan_token':'8453:'+S.USDC[8453]}
  self.assertTrue(S.matches_vault_market(m,8453,vault))
  self.assertFalse(S.matches_vault_market(m,1,vault))
 def test_market_id_is_not_profit(self):
  s=(Path(__file__).parent/'scan.py').read_text()
  self.assertIn('liquidation_or_cash_profit_proven',s)
  self.assertIn('unavailable_not_absent',s)
 def test_asset_selector(self):
  self.assertEqual(S.mintoken('8453:0xABCD'),'0xabcd')
 def test_read_only(self):
  s=(Path(__file__).parent/'scan.py').read_text()
  for word in ('eth_sendTransaction','eth_sendRawTransaction','private_key','wallet_seed','balance_override'):
   self.assertNotIn(word,s)
if __name__=='__main__':unittest.main()
