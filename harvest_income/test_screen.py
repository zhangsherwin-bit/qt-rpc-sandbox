import unittest
import screen as s
class Tests(unittest.TestCase):
 def test_small_fee_is_not_whole_yield(self):self.assertEqual(s.rate_budget(1000000,.10,.0005),50)
 def test_missing_apr_is_unknown(self):self.assertIsNone(s.rate_budget(1000000,None,.0005))
 def test_invalid_values(self):
  self.assertIsNone(s.rate_budget(1,float('inf'),.01));self.assertIsNone(s.rate_budget(-1,.1,.1));self.assertIsNone(s.rate_budget(1,.1,2))
 def test_zero_is_valid(self):self.assertEqual(s.rate_budget(0,.1,.0005),0)
 def test_no_transactions(self):
  for method in ('eth_sendRawTransaction','eth_sendTransaction','eth_sign'):self.assertNotIn(method,s.METHODS)
