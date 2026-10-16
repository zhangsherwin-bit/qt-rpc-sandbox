import unittest
from unittest.mock import patch
from eth_abi import encode
import run as m
class TestViews(unittest.TestCase):
 def setUp(self):m.BLOCK='0x123'
 def test_missing_is_unknown(self):
  with patch.object(m,'rpc',return_value='0x'):self.assertTrue(m.view('n',m.VAULT,'totalAssets()')['unavailable'])
 def test_actual_zero_preserved(self):
  with patch.object(m,'rpc',return_value='0x'+encode(['uint256'],[0]).hex()):self.assertEqual(m.view('n',m.VAULT,'totalAssets()'),0)
 def test_denied_permission_is_false(self):
  with patch.object(m,'rpc',return_value='0x'+encode(['bool'],[False]).hex()):self.assertIs(m.view('n',m.VAULT,'canReceiveShares(address)',['address'],[m.PROBE],('bool',)),False)
 def test_no_transaction_methods(self):
  with self.assertRaises(ValueError):m.rpc('n','eth_sendRawTransaction',[])
 def test_erc20_selector(self):self.assertEqual(m.data('balanceOf(address)',['address'],[m.CORE])[:10],'0x70a08231')
if __name__=='__main__':unittest.main()
