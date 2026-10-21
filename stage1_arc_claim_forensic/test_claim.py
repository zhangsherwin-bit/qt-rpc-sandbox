import unittest
from stage1_arc_claim_forensic.claim import(
 TX,BLOCK,TOKEN_ID,BURN_ASSET,BURN_AMOUNT,RELEASER,
 BURN_TOPIC,CLAIM_TOPIC,TRANSFER_TOPIC,parse_receipt,REQUEST_CAP)
def w(v):return format(int(v),"064x")
def taddr(v):return "0x"+w(int(v,16))
class TestCashLayer(unittest.TestCase):
 def base(self):
  paid=1234000000000000000
  tokenpayout=0
  claimed={"address":RELEASER,
   "topics":[CLAIM_TOPIC,"0x"+w(TOKEN_ID)],
   "data":"0x"+w(paid)+w(tokenpayout)+w(0)+w(int(BURN_ASSET,16))+w(3000)+w(60)+w(0)}
  burn={"address":RELEASER,
   "topics":[BURN_TOPIC,"0x"+w(TOKEN_ID),taddr(BURN_ASSET)],
   "data":"0x"+w(BURN_AMOUNT)}
  transfer={"address":BURN_ASSET,
   "topics":[TRANSFER_TOPIC,taddr("0x"+"12"*20),
      taddr("0x000000000000000000000000000000000000dead")],
   "data":"0x"+w(BURN_AMOUNT)}
  receipt={"transactionHash":TX,"blockNumber":hex(BLOCK),"status":"0x1",
           "gasUsed":"0x186a0","effectiveGasPrice":"0x64",
           "logs":[claimed,burn,transfer]}
  return receipt
 def test_actual_contract_event_parser(self):
  z=parse_receipt(self.base())
  self.assertEqual(z["claims"][0]["payout_native_USDC_wei"],1234000000000000000)
  self.assertEqual(z["claims"][0]["currency0"],"0x"+"0"*40)
  self.assertEqual(z["claims"][0]["currency1"],BURN_ASSET)
  self.assertEqual(z["burn_events"][0]["amount"],BURN_AMOUNT)
  self.assertEqual(z["burn_asset_transfers_to_dead"][0]["amount"],BURN_AMOUNT)
  self.assertEqual(z["gas_native_USDC_wei"],100000*100)
 def test_event_without_erc20_transfer_does_not_prove_burn(self):
  r=self.base();r["logs"].pop()
  z=parse_receipt(r)
  self.assertEqual(len(z["burn_asset_transfers_to_dead"]),0)
  self.assertEqual(z["burn_events"][0]["amount"],BURN_AMOUNT)
 def test_only_original_frozen_event(self):
  r=self.base();r["status"]="0x0"
  with self.assertRaises(ValueError):parse_receipt(r)
 def test_no_ether_value_assumptions(self):
  z=parse_receipt(self.base())
  self.assertNotIn("eth_received_wei",z)
  self.assertEqual(REQUEST_CAP,14)
 def test_bad_claim_abi_is_missing_evidence(self):
  r=self.base();r["logs"][0]["data"]="0x01"
  with self.assertRaises(ValueError):parse_receipt(r)
if __name__=="__main__":unittest.main()
