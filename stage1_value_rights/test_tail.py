import unittest
from stage1_value_rights.tail_forensics import (
 TARGETS,CRV,BOOSTER,WETH,TRANSFER,count_frozen_reward,
 native_transfers,token_flows,MAX_RU,FLOOR)
from qt_rpc.client import request_units
def taddr(a):return "0x"+a[2:].rjust(64,"0")
def transfer(token,a,b,qty):
 return {"address":token,"topics":[TRANSFER,taddr(a),taddr(b)],"data":hex(qty)}
class TestTypedRightsTail(unittest.TestCase):
 def test_two_distinct_frozen_recipients_and_budget(self):
  self.assertEqual(len(TARGETS),2)
  self.assertNotEqual(TARGETS[0]["recipient"],TARGETS[1]["recipient"])
  self.assertEqual(TARGETS[0]["crv_wei"],385298381897244354451)
  self.assertEqual(TARGETS[1]["crv_wei"],164154511351069237764)
  self.assertEqual(MAX_RU,115)
  self.assertEqual(FLOOR,1500)
  self.assertEqual(request_units("debug_traceTransaction",["0xabc",{}]),25)
 def test_exact_contractual_reward_and_token_exit(self):
  addr=TARGETS[0]["recipient"];r=TARGETS[0]["crv_wei"];pool="0x"+"aa"*20
  rc={"logs":[transfer(CRV,BOOSTER,addr,r),transfer(CRV,addr,pool,r),
              transfer(WETH,pool,addr,234)]}
  self.assertEqual(count_frozen_reward(rc,addr),r)
  self.assertEqual(token_flows(rc,{addr})[addr].get(CRV),None)
  self.assertEqual(token_flows(rc,{addr})[addr][WETH],"234")
 def test_no_reward_without_correct_beneficiary(self):
  other="0x"+"aa"*20
  rc={"logs":[transfer(CRV,BOOSTER,other,TARGETS[0]["crv_wei"])]}
  self.assertEqual(count_frozen_reward(rc,TARGETS[0]["recipient"]),0)
 def test_block_recipient_transfer_is_distinct_from_gas(self):
  addr=TARGETS[0]["recipient"];miner="0x"+"77"*20
  trace={"type":"CALL","from":addr,"to":addr,"value":"0x0",
    "calls":[{"type":"CALL","from":WETH,"to":addr,"value":hex(1000)},
             {"type":"CALL","from":addr,"to":miner,"value":hex(800)}]}
  res=native_transfers(trace,{addr},miner)
  self.assertEqual(res["net_native_flow_by_address"][addr]["native_net_wei"],"200")
  self.assertEqual(res["net_native_flow_by_address"][addr]["native_sent_to_block_fee_recipient_wei"],"800")
 def test_invalid_trace_revert_does_not_count(self):
  addr=TARGETS[0]["recipient"];miner="0x"+"77"*20
  trace={"type":"CALL","from":addr,"to":addr,"value":"0x0",
    "calls":[{"type":"CALL","from":addr,"to":miner,"value":hex(120),
      "error":"execution reverted"}]}
  res=native_transfers(trace,{addr},miner)
  self.assertEqual(res["net_native_flow_by_address"][addr]["native_net_wei"],"0")
if __name__=="__main__":unittest.main()