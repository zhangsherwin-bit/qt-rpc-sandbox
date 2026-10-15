import unittest
from unittest.mock import patch
import public_economics as p
class TestEconomics(unittest.TestCase):
 def test_no_broadcast(self):
  with self.assertRaises(ValueError):p.request('bad',p.RPC,{'jsonrpc':'2.0','method':'eth_sendRawTransaction','params':[]})
 def test_no_foreign_host(self):
  with self.assertRaises(ValueError):p.request('bad','https://unapproved.invalid/')
 def test_no_graphql_mutation(self):
  with self.assertRaises(ValueError):p.request('bad',p.API+'/graphql',{'query':'mutation { anything }'})
 def test_integer_lif_and_recovery(self):
  w=10**18; l=p.lif(('x',915*w//1000,3*w//10,'o'))
  self.assertEqual(l,1026167265264238070)
  limit=p.ceil(40*w*w,w*w-l*(915*w//1000))
  self.assertEqual(limit,656)
  self.assertEqual(limit*l//w-limit,17)
 def test_calldata(self):
  self.assertEqual(p.data('balanceOf(address)',['address'],[p.USDC])[:10],'0x70a08231')
  self.assertEqual(len(p.data('balanceOf(address)',['address'],[p.USDC])),74)
 def test_missing_data_not_zero(self):
  with self.assertRaises(ValueError):p.words(b'')
  with patch.object(p,'request',return_value={'error':{'code':-1}}):
   with self.assertRaises(ValueError):p.rpc('missing','eth_call',[])
if __name__=='__main__':unittest.main()
