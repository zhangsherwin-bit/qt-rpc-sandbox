import unittest
from stage1_convex_native_trace.trace import (
  ACCOUNT,EXPECTED_WETH_WITHDRAW,EXPECTED_GAS,
  ARCHIVED_END_BLOCK_DELTA,collect_value_transfers
)
GROSS_RECEIVED=EXPECTED_WETH_WITHDRAW
# The shortfall is inferred from before/after balance; not assumed to be a bribe.
IMPLIED_OUT=GROSS_RECEIVED-EXPECTED_GAS-ARCHIVED_END_BLOCK_DELTA
class TestNativeAccounting(unittest.TestCase):
 def test_exact_wei_reconciliation_if_transfer_explains_shortfall(self):
  frame={"type":"CALL","from":ACCOUNT,"to":ACCOUNT,"value":"0x0","calls":[
    {"type":"DELEGATECALL","from":ACCOUNT,"to":"0x"+"aa"*20,"value":"0x0","calls":[
      {"type":"CALL","from":"0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
       "to":ACCOUNT,"value":hex(GROSS_RECEIVED)},
      {"type":"CALL","from":ACCOUNT,"to":"0x"+"bb"*20,
       "value":hex(IMPLIED_OUT)}]}]}
  r=collect_value_transfers(frame,ACCOUNT)
  self.assertEqual(r["native_account_internal_received_wei"],GROSS_RECEIVED)
  self.assertEqual(r["native_account_internal_sent_wei"],IMPLIED_OUT)
  self.assertEqual(r["net_internal_native_value_wei"]-EXPECTED_GAS,ARCHIVED_END_BLOCK_DELTA)
 def test_ignore_delegatecall_apparent_nontransfer(self):
  fake={"type":"DELEGATECALL","from":ACCOUNT,"to":"0x"+"11"*20,
        "value":hex(50),"calls":[]}
  r=collect_value_transfers(fake,ACCOUNT)
  self.assertEqual(r["net_internal_native_value_wei"],0)
 def test_exclude_self_call_top_level_to_prevent_double_count(self):
  frame={"type":"CALL","from":ACCOUNT,"to":ACCOUNT,
         "value":hex(GROSS_RECEIVED),"calls":[]}
  r=collect_value_transfers(frame,ACCOUNT)
  self.assertEqual(len(r["account_relevant_value_transfers"]),0)
 def test_do_not_count_traced_reverted_branch(self):
  frame={"type":"CALL","from":ACCOUNT,"to":"0x"+"22"*20,
         "value":hex(100),"error":"execution reverted"}
  self.assertEqual(collect_value_transfers(frame,ACCOUNT)["native_account_internal_sent_wei"],0)
 def test_recursion_and_frame_count_cap(self):
  frame={"type":"CALL","from":ACCOUNT,"to":ACCOUNT,"value":"0x0",
         "calls":[{"type":"CALL","from":"0x"+"22"*20,"to":ACCOUNT,"value":hex(33)}]}
  r=collect_value_transfers(frame,ACCOUNT)
  self.assertEqual(r["trace_total_frames"],2)
  self.assertEqual(r["native_account_internal_received_wei"],33)
if __name__=="__main__":unittest.main()
