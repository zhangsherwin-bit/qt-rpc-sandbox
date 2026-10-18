import unittest,json,pathlib
from decimal import Decimal as D
from public_screen import allowed,depth,pair,RPC,DATES
class Tests(unittest.TestCase):
 def book(self,a='.52',b='.48',q='1000'):
  return {'market':'m','neg_risk':False,'min_order_size':'5','asks':[{'price':a,'size':q}],'bids':[{'price':b,'size':q}]}
 def test_no_broadcast(self):self.assertFalse(allowed(RPC,{'jsonrpc':'2.0','method':'eth_sendRawTransaction'}))
 def test_no_simulation_override_method(self):self.assertFalse(allowed(RPC,{'jsonrpc':'2.0','method':'eth_simulateV1'}))
 def test_no_generic_endpoint(self):self.assertFalse(allowed('https://example.com/markets',None))
 def test_public_books(self):self.assertTrue(allowed('https://clob.polymarket.com/books',[]))
 def test_no_order(self):self.assertFalse(allowed('https://clob.polymarket.com/order',[]))
 def test_sort_buy(self):self.assertEqual(depth([{'price':'.9','size':'5'},{'price':'.1','size':'5'}],5,True),D('.5'))
 def test_sort_sell(self):self.assertEqual(depth([{'price':'.1','size':'5'},{'price':'.9','size':'5'}],5,False),D('4.5'))
 def test_insufficient_depth(self):self.assertIsNone(depth([{'price':'.1','size':'1'}],5,True))
 def test_costs_not_midpoints(self):self.assertEqual(pair(self.book(),self.book())[0]['buy_both_gross'],'-0.20')
 def test_synthetic_positive_not_cash(self):
  x=pair(self.book('.48'),self.book('.49'))[0];self.assertEqual(x['buy_both_gross'],'0.15');self.assertFalse(x['cash_execution']);self.assertTrue(x['fees_excluded'])
 def test_condition_mismatch(self):
  x=self.book();x['market']='different'
  with self.assertRaises(ValueError):pair(x,self.book())
 def test_neg_risk_excluded(self):
  x=self.book();x['neg_risk']=True
  with self.assertRaises(ValueError):pair(x,self.book())
 def test_unknown_type_excluded(self):
  x=self.book();del x['neg_risk']
  with self.assertRaises(ValueError):pair(x,self.book())
 def test_minimum_quantity(self):
  x=self.book();x['min_order_size']='50';self.assertEqual(len(pair(x,x)),1)
 def test_reserved_dates_untouched(self):self.assertTrue(all(x<'2026-10-03' for x in DATES))
 def test_precise_quoter_tuple(self):
  t=(pathlib.Path(__file__).parent/'public_screen.py').read_text();self.assertIn('quoteExactInputSingle((address,address,uint256,uint24,uint160))',t)
if __name__=='__main__':unittest.main()
