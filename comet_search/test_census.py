"""Pure protocol encoding and cash-measurement controls; no blockchain tests."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import census as S
class TestCensus(unittest.TestCase):
 def test_buy_event_structure(self):
  t=[S.BUY,"0x"+S.pad(3),"0x"+S.pad(4)]
  l={"topics":t,"data":"0x"+S.pad(100000000)+S.pad(123456789),
    "address":"0x"+"1"*40,"transactionHash":"0x"+"a"*64,"blockNumber":"0x100","logIndex":"0x1"}
  x=S.ev(l)
  self.assertEqual((x['base_raw'],x['coll_raw']),('100000000','123456789'))
  self.assertEqual(x['kind'],'buy')
 def test_absorb_is_not_buy(self):
  t=[S.ABSORB,"0x"+S.pad(1),"0x"+S.pad(2),"0x"+S.pad(3)]
  l={"topics":t,"data":"0x"+S.pad(100)+S.pad(200),
    "address":"0x"+"1"*40,"transactionHash":"0x"+"a"*64,"blockNumber":"0x100","logIndex":"0x1"}
  self.assertEqual(S.ev(l)['kind'],'absorb')
 def test_quoter_tuple_encoding(self):
  a='0x'+'1'*40;b='0x'+'2'*40
  x=S.quote_data(a,b,1000,500)
  self.assertTrue(x.startswith('0x'))
  self.assertEqual(len(x),2+8+5*64)
  self.assertFalse('0x0x' in x)
 def test_frozen_markets_multi_chain(self):
  self.assertEqual(len(S.CHAINS['ethereum']['markets']),3)
  self.assertEqual(len(S.CHAINS['base']['markets']),5)
 def test_disjoint_fixed_windows(self):
  a,b=S.CHAINS['ethereum'],S.CHAINS['base']
  self.assertGreater(a['to'],a['from'])
  self.assertGreater(b['to'],b['from'])
  self.assertGreaterEqual(a['to']-a['from'],100000)
 def test_dedupe_market_choice(self):
  cases=[]
  for i in range(9):
   cases.append({'chain':'base','market':'0x'+'1'*40,'tx':"0x"+format(i,'064x'),
       'log_index':i,'block':100+i,'base_raw':str(100+i)})
  picks=S.choose(cases)
  self.assertEqual(len(picks),3)
  self.assertEqual(len({x['tx'] for x in picks}),3)
 def test_no_execution_or_private_key(self):
  s=(Path(__file__).parent/'census.py').read_text()
  for k in ('eth_sendTransaction','eth_sendRawTransaction','private_key','wallet_seed','approve('):
   self.assertNotIn(k,s)
 def test_quote_is_not_cash_execution(self):
  self.assertIn('gross_quote_profit_is_not_cash_profit', (Path(__file__).parent/'census.py').read_text())
if __name__=='__main__':unittest.main()
