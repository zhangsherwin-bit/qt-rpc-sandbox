import pathlib,unittest,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import logic
class TestRepair(unittest.TestCase):
 def test_internal_value_is_not_native_payment(self):
  self.assertEqual(logic.native_delta({'type':'DELEGATECALL','from':'a','to':'b','value':'0x10'},'b'),0)
 def test_reverted_transfer_is_not_payment(self):
  self.assertEqual(logic.native_delta({'type':'CALL','from':'a','to':'b','value':'0x10','error':'revert'},'b'),0)
 def test_nested_native_payment(self):
  c={'type':'CALL','from':'a','to':'b','value':'0x10','calls':[{'type':'CALL','from':'b','to':'c','value':'0x5'}]}
  self.assertEqual(logic.native_delta(c,'b'),11);self.assertEqual(logic.native_delta(c,'c'),5)
 def test_full_compensation(self):
  self.assertEqual(logic.compensation({'effectiveGasPrice':'0xa','gasUsed':'0x64'},{'baseFeePerGas':'0x7'},50),350)
 def test_bad_fee_rejected(self):
  with self.assertRaises(ValueError):logic.compensation({'effectiveGasPrice':'0x1','gasUsed':'0x1'},{'baseFeePerGas':'0x2'},0)
 def test_replay_budget(self):
  self.assertEqual(logic.historical_headroom({'gasLimit':hex(60000000)},[{'gasUsed':hex(58162340)}]),1837660)
 def test_no_fake_block_capacity(self):
  with self.assertRaises(ValueError):logic.historical_headroom({'gasLimit':'0x2'},[{'gasUsed':'0x2'}])
 def test_wrong_source_rejected(self):
  with self.assertRaises(ValueError):logic.transform('pragma solidity 0.8.24;')
 def test_source_transformation(self):
  s=pathlib.Path('input_services/CashProbe.sol').read_text();t=logic.transform(s)
  for e in ['checkedMatrix','checkedExecute','producerPayment','TRI','DIRECT','header mismatch','terminal obligations']:self.assertIn(e,t)
  self.assertEqual(t.count('else if(j.kind==1)'),1)
 def test_source_not_double_applied(self):
  with self.assertRaises(ValueError):logic.transform(logic.transform(pathlib.Path('input_services/CashProbe.sol').read_text()))
 def test_reverted_subcall_logs_not_counted(self):
  c={'to':'a','calls':[{'to':'b','error':'no','logs':[{'topics':['0xaa'],'data':'0x'}]}]}
  self.assertEqual(logic.logbag(c),[])
 def test_normalize_logs(self):
  self.assertEqual(logic.normlogs([{'address':'0xAB','topics':['0xCD'],'data':'0xEF'}]),[('0xab',('0xcd',),'0xef')])
if __name__=='__main__':unittest.main()
