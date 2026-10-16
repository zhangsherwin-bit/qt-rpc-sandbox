"""Offline guards and exact arithmetic, not trading experiments."""
import copy,pathlib,tempfile,unittest
from unittest.mock import patch
from codec import *
from run import Client,rows,valid_offer,legal_cash_sizes
M={'chain_id':8453,'market_id':'0x6cb9f4a081803895ee5f8cb611c9a7ad7ccadd88d8a8343f478d9e5646efecac','loan_token':USDC,'maturity':1795791600,'rcf_threshold':'3000000000','enter_gate':ZERO,'liquidator_gate':ZERO,'collaterals':[{'token':USDC,'lltv':'980000000000000000','liquidation_cursor':'300000000000000000','oracle':'0x4429112b3C00b40Cf295db81cfcdE39d7d5ADC1d'},{'token':'0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf','lltv':'860000000000000000','liquidation_cursor':'300000000000000000','oracle':'0x663BECd10daE6C4A3Dcd89F1d76c1174199639B9'}]}
class Guards(unittest.TestCase):
 def test_keccak(self):self.assertEqual(keccak256(b'').hex(),'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470')
 def test_selector(self):self.assertEqual(selector('balanceOf(address)'),'0x70a08231')
 def test_actual_market_id(self):self.assertEqual(market_id(M),M['market_id'])
 def test_market_change(self):
  m=copy.deepcopy(M);m['maturity']+=1;self.assertNotEqual(market_id(m),M['market_id'])
 def test_wrong_core(self):
  with self.assertRaises(ValueError):market_id(dict(M,midnight=ZERO))
 def test_wrong_uint(self):
  with self.assertRaises(ValueError):word(-1)
 def test_wrong_return(self):
  with self.assertRaises(ValueError):decode_words('0x00')
 def test_missing_book_not_empty(self):
  with self.assertRaises(ValueError):rows(None)
 def test_warning_positive_size(self):
  raw={'offer':{'market':dict(M,midnight=CORE),'buy':False},'market_id':M['market_id'],'units':'1000000','warning':{'code':'MAKER_LIQUIDITY'}};self.assertTrue(valid_offer(raw,M))
 def test_transaction_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   c=Client(pathlib.Path(d),10)
   with self.assertRaises(ValueError):c.rpc('eth_sendRawTransaction',[])
   self.assertEqual(c.count,0)
 def test_wrong_host(self):
  with tempfile.TemporaryDirectory() as d,patch('urllib.request.urlopen') as request:
   c=Client(pathlib.Path(d),10)
   with self.assertRaises(ValueError):c.request('https://unapproved.example/')
   request.assert_not_called()
 def test_exact_recovery_cap(self):
  m=copy.deepcopy(M);m['collaterals']=m['collaterals'][:1];m['rcf_threshold']='0'
  sizes,_=legal_cash_sizes(m,980000040,{0:1000000000},{0:10**36},m['maturity']-1);self.assertEqual(sizes[0][2],2840)
 def test_dust_exception(self):
  m=copy.deepcopy(M);m['collaterals']=m['collaterals'][:1]
  sizes,_=legal_cash_sizes(m,980000040,{0:1000000000},{0:10**36},m['maturity']-1);self.assertEqual(sizes[0][2],980000040)
 def test_bad_debt(self):
  self.assertEqual(legal_cash_sizes(M,1100000000,{0:1000000000},{0:10**36},M['maturity']+3600)[1],'bad_debt_unsupported')
 def test_maturity_strict(self):
  self.assertEqual(legal_cash_sizes(M,900000000,{0:1000000000},{0:10**36},M['maturity'])[0],[])
  self.assertTrue(legal_cash_sizes(M,900000000,{0:1000000000},{0:10**36},M['maturity']+1)[0])
 def test_mixed_shock(self):
  a={0:1000000000,1:100000000};m=copy.deepcopy(M);m['rcf_threshold']='0'
  self.assertFalse(legal_cash_sizes(m,1450000000,a,{0:10**36,1:10*10**36},m['maturity']-1)[0])
  self.assertTrue(legal_cash_sizes(m,1450000000,a,{0:10**36,1:5*10**36},m['maturity']-1)[0])
 def test_unknown_oracle(self):
  with self.assertRaises(ValueError):legal_cash_sizes(M,1,{0:1},{},M['maturity']-1)
 def test_liquidation_abi(self):
  words_=decode_words('0x'+run_liquidation(M,0,CALLER,123,True)[10:]);self.assertEqual(words_[:6],[192,0,int(CALLER,16),0,123,1])
if __name__=='__main__':unittest.main()
