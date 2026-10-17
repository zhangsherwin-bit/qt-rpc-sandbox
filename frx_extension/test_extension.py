import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parent/'run.py'
s=importlib.util.spec_from_file_location('probe',p);r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
class TestPlan(unittest.TestCase):
 def test_cases_fixed(self):
  self.assertEqual(r.SIZES,(500,5000,20000,50000));self.assertEqual(r.plan()['simulation_calls'],10)
 def test_amount_encoding(self):
  x=r.encode_uints('2d29a47b',20000*10**6,r.RESERVE,r.MINIMUM)
  self.assertEqual(len(x),2+8+3*64);self.assertEqual(int(x[10:74],16),20000000000)
 def test_negative_rejected(self):
  with self.assertRaises(ValueError):r.encode_uints('2d29a47b',-1)
 def test_large_rejected(self):
  with self.assertRaises(ValueError):r.encode_uints('2d29a47b',2**256)
 def test_exact_width(self):
  self.assertEqual(r.words('0x'+format(12,'064x'),1),(12,))
  with self.assertRaises(ValueError):r.words('0x00',1)
 def test_no_send_method(self):
  self.assertFalse(any('send' in m.lower() for m in r.ALLOWED))
  with self.assertRaises(ValueError):r.rpc('bad','eth_sendRawTransaction',[])
 def test_revert_and_no_hidden_initial_cash(self):
  h={'number':'0x5','timestamp':'0x7'};a=(1,5,7,0,0,0,0,0,0);data='0x'+''.join(format(x,'064x') for x in a)
  env={'status':'0x1','returnData':data};failure={'status':'0x0','gasUsed':'0x123','error':{'message':'not profitable'}}
  result=r.evaluate([env,failure,env],h,1)
  self.assertTrue(result['rollback_verified']);self.assertIsNone(result['paid_cash_raw'])
  bad={'status':'0x1','returnData':'0x'+''.join(format(x,'064x') for x in (1,5,7,0,1,0,0,0,0))}
  with self.assertRaises(ValueError):r.evaluate([bad,failure,bad],h,1)
 def test_revert_balance_change_rejected(self):
  h={'number':'0x5','timestamp':'0x7'}
  def env(q):return {'status':'0x1','returnData':'0x'+''.join(format(x,'064x') for x in (1,5,7,0,0,0,0,0,q))}
  with self.assertRaises(ValueError):r.evaluate([env(0),{'status':'0x0','gasUsed':'0x1'},env(1)],h,1)
 def test_transfer_filter(self):
  addr=lambda x:'0x'+x[2:].rjust(64,'0')
  l={'address':r.USDC,'topics':[r.TRANSFER,addr(r.MORPHO),addr(r.PROBE)],'data':'0x1'}
  self.assertEqual(r.token_transfers([l],r.USDC),[(r.MORPHO.lower(),r.PROBE.lower(),1)])
  self.assertEqual(r.token_transfers([l],r.REDEEM),[])
 def test_frozen_source_and_no_funding(self):
  self.assertEqual(len(r.SOURCE_SHA),64);self.assertEqual(len(r.RUNTIME_SHA),64)
  self.assertTrue(r.plan()['no_production_storage_or_balance_overrides'])
if __name__=='__main__':unittest.main()
