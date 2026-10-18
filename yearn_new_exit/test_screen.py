import unittest,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import screen as S
class Tests(unittest.TestCase):
 def test_real_census_first_middle_last(self):
  logs=json.loads(Path('input/ALL_LOGS.json').read_text())
  auctions=json.loads(Path('input/AUCTIONS.json').read_text())
  rows=S.select({'logs':logs,'auctions':auctions})
  self.assertEqual(len(rows),6)
  self.assertEqual(sum(x['asset']=='RSUP' for x in rows),3)
  self.assertEqual(sum(x['asset']=='DOLA' for x in rows),3)
  self.assertEqual(len({x['tx'] for x in rows}),6)
 def test_event_sigs(self):
  self.assertEqual(S.TRANSFER,S.h('Transfer(address,address,uint256)'))
  self.assertEqual(S.SEL,S.h('AuctionSettled(address)'))
  self.assertEqual(S.KICK,S.h('AuctionKicked(address,uint256)'))
 def test_exact_tuple_selector(self):
  self.assertEqual(len(S.h('quoteExactInputSingle((address,address,uint256,uint24,uint160))')),66)
 def test_positive_quote_is_not_cash(self):
  x=(Path(__file__).parent/'screen.py').read_text()
  self.assertIn('"not_complete_atomic_settlement":True',x)
 def test_no_signer(self):
  x=(Path(__file__).parent/'screen.py').read_text()
  for v in ('eth_sendRawTransaction','eth_sendTransaction','private_key','wallet_seed','personal_sign'):
   self.assertNotIn(v,x)
 def test_receipt_replay_required(self):
  x=(Path(__file__).parent/'screen.py').read_text()
  self.assertIn("receipt_checked",x)
  self.assertIn("No uniquely attributable crvUSD payment",x)
if __name__=='__main__':unittest.main()
