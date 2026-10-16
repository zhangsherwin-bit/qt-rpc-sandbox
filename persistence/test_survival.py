import copy
import unittest
from unittest.mock import patch
from eth_abi import encode
import run_survival as m

def blob(values):return '0x'+encode(['uint256']*len(values),values).hex()
class TestSurvival(unittest.TestCase):
 def fixture(self):
  h={'number':'0x64','timestamp':'0x100','baseFeePerGas':'0x1'}
  before=[1,100,256,0,0,0,0,0,0]
  v=[m.PRINCIPAL,500_000_000,400_000,499_600_000,m.RESERVE,20_500*10**18]
  after=before.copy();after[7]=m.RESERVE;after[8]=v[3]
  calls=[{'status':'0x1','returnData':blob(before)},{'status':'0x1','gasUsed':hex(1_000_000),'returnData':blob(v)},{'status':'0x1','returnData':blob(after)}]
  return h,calls
 def test_cash_closure(self):
  h,c=self.fixture();r=m.check_success(c,h);self.assertTrue(r['cash_and_repayment_verified']);self.assertTrue(r['reserve_covers_base_fee'])
 def test_prefunding_rejected(self):
  h,c=self.fixture();c[0]['returnData']=blob([1,100,256,0,1,0,0,0,0])
  with self.assertRaises(AssertionError):m.check_success(c,h)
 def test_wrong_chain_rejected(self):
  h,c=self.fixture();c[0]['returnData']=blob([8453,100,256,0,0,0,0,0,0])
  with self.assertRaises(AssertionError):m.check_success(c,h)
 def test_missing_payout_rejected(self):
  h,c=self.fixture();c[2]['returnData']=blob([1,100,256,0,0,0,0,m.RESERVE,0])
  with self.assertRaises(AssertionError):m.check_success(c,h)
 def test_wrong_repayment_rejected(self):
  h,c=self.fixture();c[1]['returnData']=blob([m.PRINCIPAL-1,500_000_000,400_000,499_600_000,m.RESERVE,20_500*10**18])
  with self.assertRaises(AssertionError):m.check_success(c,h)
 def test_revert_rollback(self):
  h,c=self.fixture();c[1]={'status':'0x0','gasUsed':hex(800_000),'returnData':'0x','error':{'message':'not profitable'}};c[2]=copy.deepcopy(c[0]);self.assertTrue(m.check_success(c,h)['rollback_verified'])
 def test_insufficient_gas_reserve_is_flagged(self):
  h,c=self.fixture();h['baseFeePerGas']=hex(10**12);r=m.check_success(c,h);self.assertFalse(r['reserve_covers_base_fee'])
 def test_no_send_method(self):
  with self.assertRaises(ValueError):m.rpc('reject','eth_sendRawTransaction',[])
 def test_frozen_scope(self):
  self.assertEqual(m.OFFSETS,(1,2,4,8,16,32,64));self.assertEqual(m.PRINCIPAL,20_000_000_000);self.assertEqual(m.WINNER_BLOCK,25643399)
if __name__=='__main__':unittest.main()
