import unittest
from stage1_convex_forensic.receipt import (
    TX,BLOCK,ACTOR,BOOSTER,CRV,WETH,TRANSFER,WITHDRAW,
    EXPECTED_CRV,EXPECTED_WETH,EXPECTED_GAS,verify_tx
)
POOL="0x919fa96e88d67499339577fa202345436bcdaf79"
def w(v):return "0x"+format(int(v),"064x")
def topic(a):return w(int(a,16))
class TestCashForensics(unittest.TestCase):
 def event(self,contract,topics,amount):
  return {"address":contract,"topics":topics,"data":w(amount)}
 def sample(self):
  tx={"hash":TX,"blockNumber":hex(BLOCK),"from":ACTOR,"to":ACTOR,"transactionIndex":"0x0"}
  receipt={"transactionHash":TX,"blockNumber":hex(BLOCK),"status":"0x1",
           "gasUsed":hex(769480),"effectiveGasPrice":hex(68381913),"logs":[
            self.event(CRV,[TRANSFER,topic(BOOSTER),topic(ACTOR)],EXPECTED_CRV),
            self.event(CRV,[TRANSFER,topic(ACTOR),topic(POOL)],EXPECTED_CRV),
            self.event(WETH,[TRANSFER,topic(POOL),topic(ACTOR)],EXPECTED_WETH),
            self.event(WETH,[WITHDRAW,topic(ACTOR)],EXPECTED_WETH)
           ]}
  return tx,receipt
 def test_matching_actual_archive_amounts(self):
  tx,rc=self.sample()
  r=verify_tx(tx,rc)
  self.assertTrue(r["closed_token_accounting"])
  self.assertEqual(r["crv_booster_to_actor_wei"],EXPECTED_CRV)
  self.assertEqual(r["weth_in_to_actor_wei"],EXPECTED_WETH)
  self.assertEqual(r["weth_out_including_unwrap_wei"],EXPECTED_WETH)
  self.assertEqual(r["gas_wei"],EXPECTED_GAS)
  self.assertEqual(r["receipt_earned_eth_minus_gas_wei"],11326465741570036)
 def test_not_earned_if_booster_reward_goes_to_other_address(self):
  tx,rc=self.sample()
  rc["logs"][0]["topics"][2]=topic("0x"+"55"*20)
  r=verify_tx(tx,rc)
  self.assertFalse(r["closed_token_accounting"])
  self.assertFalse(r["original_receipt_matches_archive"])
 def test_reject_failed_receipt(self):
  tx,rc=self.sample()
  rc["status"]="0x0"
  with self.assertRaises(ValueError):verify_tx(tx,rc)
 def test_reject_wrong_block_or_tx(self):
  tx,rc=self.sample()
  tx["blockNumber"]=hex(BLOCK-1)
  with self.assertRaises(ValueError):verify_tx(tx,rc)
 def test_first_in_block_assumption(self):
  tx,rc=self.sample()
  tx["transactionIndex"]="0x1"
  with self.assertRaises(ValueError):verify_tx(tx,rc)
 def test_weth_transfer_without_unwrap_is_not_native_cash(self):
  tx,rc=self.sample()
  rc["logs"][-1]["topics"][1]=topic("0x"+"44"*20)
  r=verify_tx(tx,rc)
  self.assertFalse(r["closed_token_accounting"])
if __name__=="__main__":unittest.main()
