import unittest,tempfile,pathlib
from eth_abi import encode
from unittest.mock import patch
from midnight_codec import *
from collect import legal_cash_sizes,Client,WAD,O,maximum_lif

def fixture():
 return {'chain_id':8453,'midnight':CORE,'loan_token':USDC,'collaterals':[{'token':USDC,'lltv':str(915*10**15),'liquidation_cursor':str(3*10**17),'oracle':ZERO}], 'maturity':2000,'rcf_threshold':'0','enter_gate':ZERO,'liquidator_gate':ZERO}
def mtuple(m):
 return (m['chain_id'],CORE,USDC,[(c['token'],int(c['lltv']),int(c['liquidation_cursor']),c['oracle']) for c in m['collaterals']],m['maturity'],int(m['rcf_threshold']),ZERO,ZERO)
class Checks(unittest.TestCase):
 def test_known_selector(self):self.assertEqual(selector('balanceOf(address)'),'0x70a08231')
 def test_market_abi(self):
  m=fixture();self.assertEqual(word(32)+market_body(m),encode([MARKET],[mtuple(m)]))
 def test_market_id(self):
  m=fixture();expected=keccak256(b'\xff'+bytes.fromhex(CORE[2:])+bytes(32)+keccak256(bytes.fromhex('600b380380600b5f395ff3')+encode([MARKET],[mtuple(m)])))
  self.assertEqual(market_id(m),'0x'+expected.hex())
 def test_liquidation_abi(self):
  m=fixture();data=run_liquidation(m,0,CALLER,0,100,False)
  self.assertEqual(data[10:],encode([MARKET,'uint256','address','uint256','uint256','bool'],[mtuple(m),0,CALLER,0,100,False]).hex())
 def test_offer_abi(self):
  m=fixture();o={'market':m,'buy':False,'maker':CALLER,'start':1,'expiry':1999,'tick':6000,'group':'0x'+'11'*32,'callback':ZERO,'callback_data':'0xabcdef','receiver_if_maker_is_seller':CALLER,'ratifier':ZERO,'reduce_only':False,'max_units':'1000','max_assets':'0','continuous_fee_cap':'10'}
  tup=(mtuple(m),False,CALLER,1,1999,6000,bytes.fromhex('11'*32),ZERO,bytes.fromhex('abcdef'),CALLER,ZERO,False,1000,0,10)
  self.assertEqual(run_take(o,'0xaabb',999)[10:],encode([OFFER,'bytes','uint256'],[tup,bytes.fromhex('aabb'),999]).hex())
 def test_healthy_not_candidate(self):
  self.assertEqual(legal_cash_sizes(fixture(),800,{0:1000},{0:O},1000)[0],[])
 def test_post_maturity_strict_boundary(self):
  m=fixture();self.assertEqual(legal_cash_sizes(m,800,{0:1000},{0:O},2000)[0],[])
  self.assertTrue(legal_cash_sizes(m,800,{0:1000},{0:O},2001)[0])
 def test_bad_debt_rejected(self):
  self.assertEqual(legal_cash_sizes(fixture(),2000,{0:1000},{0:O},1000)[1],'bad_debt_unsupported')
 def test_health_recovery_limit(self):
  m=fixture();sizes,_=legal_cash_sizes(m,916,{0:1000},{0:O},1000)
  self.assertTrue(sizes);self.assertLess(max(x[2] for x in sizes),100)
 def test_missing_price_not_zero(self):
  with self.assertRaises(ValueError):legal_cash_sizes(fixture(),916,{0:1000},{},1000)
 def test_core_mismatch(self):
  m=fixture();m['midnight']=ZERO
  with self.assertRaises(ValueError):market_id(m)
 def test_rpc_send_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=Client(pathlib.Path(tmp),10)
   with self.assertRaises(ValueError):c.rpc('eth_sendRawTransaction',[])
 def test_external_host_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=Client(pathlib.Path(tmp),10)
   with self.assertRaises(ValueError):c.request('https://example.com')
 def test_unavailable_not_zero(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=Client(pathlib.Path(tmp),10)
   with patch('urllib.request.urlopen',side_effect=OSError('offline test')),patch('time.sleep'):
    with self.assertRaises(ValueError):c.view(CORE,'withdrawable(bytes32)',['0x'+'00'*32],'latest')
   self.assertIn('error',c.records[0])
if __name__=='__main__':unittest.main()
