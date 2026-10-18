import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import quote as Q
class UniswapQuoteTests(unittest.TestCase):
 def test_exact_fee_quote_encoding(self):
  x=Q.encode(Q.WETH,5*10**18,500)
  self.assertEqual(len(x),2+8+5*64)
  self.assertTrue(x.endswith('0'*64))
 def test_recorded_observed_fill_hashes(self):
  self.assertEqual(len(Q.ONE["orderHash"]),66)
  self.assertEqual(len(Q.TWO["orderHash"]),66)
  self.assertNotEqual(Q.ONE["fill"],Q.TWO["fill"])
 def test_source_gas_not_income(self):
  s=(Path(__file__).parent/"quote.py").read_text()
  for f in ('eth_sendTransaction','eth_sendRawTransaction','wallet_seed','private_key'):
   self.assertNotIn(f,s)
 def test_observed_order_input_bounds(self):
  self.assertLess(Q.ONE["lowIn"],Q.ONE["highIn"])
  self.assertEqual(Q.ONE["amountOut"],5*10**18)
 def test_frozen_old_samples(self):
  self.assertLess(Q.ONE["block"],Q.TWO["block"])
if __name__=="__main__":unittest.main()
