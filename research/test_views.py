import unittest
from fractions import Fraction
from unittest.mock import patch
import view_followup as v
class ViewTests(unittest.TestCase):
 def test_selector(self):self.assertEqual(v.calldata('balanceOf(address)',['address'],[v.CORE])[:4].hex(),'70a08231')
 def test_no_transfer(self):
  with self.assertRaises(ValueError):v.calldata('transfer(address,uint256)',['address','uint256'],[v.ORDINARY,1])
 def test_no_liquidation(self):
  with self.assertRaises(ValueError):v.calldata('liquidate()')
 def test_no_redemption(self):
  with self.assertRaises(ValueError):v.calldata('redeem(uint256,address,address)')
 def test_no_transaction_submission(self):
  c=v.Client()
  with self.assertRaises(ValueError):c.request('bad',v.RPC,{'method':'eth_sendRawTransaction'})
  self.assertEqual(c.n,0)
 def test_no_arbitrary_host(self):
  c=v.Client()
  with self.assertRaises(ValueError):c.request('bad','https://example.org/')
  self.assertEqual(c.n,0)
 def test_native_units(self):self.assertEqual(120092835950/10**6,120092.83595)
 def test_encoding_cleanup(self):self.assertEqual(v.clean({'x':(b'\x01',3)}),{'x':['0x01',3]})
 def test_sequence_bound(self):
  # Fixed repay fraction, constant redemption=oracle, no bad debt or dust exception.
  # All figures are normalised by full-debt maximum bonus D*b.
  for i in range(101):
   f=Fraction(i,100)
   for j in range(101):
    t=Fraction(j,100);a=f+(1-f)*t-max(f,t)
    self.assertGreaterEqual(a,0);self.assertLessEqual(a,f*(1-f));self.assertLessEqual(a,Fraction(1,4))
 def test_bound_tight(self):
  f=t=Fraction(1,2);self.assertEqual(f+(1-f)*t-max(f,t),Fraction(1,4))
 def test_no_late_sequence_improvement(self):
  for f in [Fraction(0),Fraction(1,3),Fraction(1)]:self.assertEqual(f+(1-f)-max(f,1),0)
if __name__=='__main__':unittest.main()
