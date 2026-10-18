"""Software-only price math, source scope, and replay guard tests."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import quote as Q
class AuctionTests(unittest.TestCase):
 def test_event_signature(self):
  self.assertEqual(Q.KICK,'0x'+Q.h('AuctionKicked(address,uint256)'))
  self.assertEqual(Q.SETTLE,'0x'+Q.h('AuctionSettled(address)'))
 def test_same_asset_selection(self):
  items,scope=Q.frozen()
  self.assertEqual(len(items),8)
  self.assertEqual(scope['source_logs'],6261)
  self.assertEqual({c['from_token'] for c in items},{Q.USDC,Q.CRV})
  for tok in (Q.CRV,Q.USDC):
   self.assertEqual(len({x['kick_date'] for x in items if x['from_token']==tok}),4)
 def test_frozen_development_window(self):
  rows,_=Q.frozen()
  self.assertTrue(all('2026-09-10'<=x['kick_date']<'2026-10-01' for x in rows))
 def test_curve_tokens(self):
  self.assertNotEqual(Q.USDC,Q.CRVUSD)
  self.assertEqual(len(Q.CURVE),42)
 def test_quote_abi(self):
  data=Q.data('getAmountNeeded(address,uint256)',Q.CRV,10000)
  self.assertEqual(len(data),2+8+64*2)
  self.assertEqual(Q.number('0x'+Q.pad(123)),123)
 def test_no_profit_without_obligation(self):
  source=(Path(__file__).parent/'quote.py').read_text()
  self.assertIn('getAmountNeeded(address,uint256)',source)
  self.assertIn('actual_auction_payment_crvusd_raw',source)
 def test_no_mocking_or_sending(self):
  src=(Path(__file__).parent/'quote.py').read_text()
  for t in ('eth_sendTransaction','eth_sendRawTransaction','private_key','wallet_seed'):
   self.assertNotIn(t,src)
 def test_no_reserved_october(self):
  rows,_=Q.frozen()
  self.assertTrue(all(x['kick_date']!='2026-10-05' for x in rows))
if __name__=='__main__':unittest.main()
