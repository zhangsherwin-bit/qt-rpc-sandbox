import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import screen as S
class TestSiloResearch(unittest.TestCase):
 def test_no_implementation_hypothesis_as_profit(self):
  src=(Path(__file__).parent/'screen.py').read_text()
  self.assertIn('"profit_usd_is_indexer_estimate":True',src)
  self.assertIn('"no_execution_or_capture":True',src)
 def test_only_readonly_methods(self):
  src=(Path(__file__).parent/'screen.py').read_text()
  for cmd in ('eth_sendTransaction','eth_sendRawTransaction','wallet_seed','private_key'):
   self.assertNotIn(cmd,src)
 def test_scalar_type_resolution(self):
  self.assertEqual(S.objfield({'kind':'NON_NULL','ofType':{'kind':'OBJECT','name':'Foo'}}),'Foo')
  self.assertEqual(S.objfield({'kind':'LIST','ofType':{'kind':'OBJECT','name':'Bar'}}),'Bar')
 def test_api_host(self):self.assertEqual(S.API,"https://api-v3.silo.finance")
 def test_rpc_scope(self):self.assertEqual(set(S.RPC),{1,8453})
if __name__=="__main__":unittest.main()
