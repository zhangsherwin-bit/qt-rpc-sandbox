"""Prize is not caller cash until credited rewards are withdrawn as ERC20."""
import unittest
from Crypto.Hash import keccak as reference_keccak
from stage1_prize_cash.scan import (
 CLAIM,WITHDRAW,TRANSFER,DEPLOYED,
 decode_claim,decode_withdraw,check_transfer,BATCH_SIZES,
 RU_BUDGET,MAX_TX_PER_CHAIN)
def w(x):return format(int(x),"064x")
def topicaddr(a):return "0x"+w(int(a,16))
class TestPrize(unittest.TestCase):
 def test_event_topics_are_computed_from_official_abi(self):
  signatures={
   "ClaimedPrize(address,address,address,uint24,uint8,uint32,uint152,uint96,address)":CLAIM,
   "WithdrawRewards(address,address,uint256,uint256)":WITHDRAW,
   "Transfer(address,address,uint256)":TRANSFER}
  for signature, actual in signatures.items():
   h=reference_keccak.new(digest_bits=256)
   h.update(signature.encode())
   self.assertEqual(actual,"0x"+h.hexdigest())
   self.assertEqual(len(actual),66)

 def test_official_deployment_sources(self):
  self.assertEqual(DEPLOYED[8453]["claimer"],"0xcdce635b774de77cdf791647601dba64a75547ba")
  self.assertEqual(DEPLOYED[1]["pool"],"0x7865d01da4c9ba2f69b7879e6d2483ab6b354d95")
 def test_claim_fee_is_internal_credit_not_eth(self):
  fee_recipient="0x"+"11"*20
  l={"topics":[CLAIM,topicaddr("0x"+"22"*20),topicaddr("0x"+"33"*20),
      topicaddr("0x"+"44"*20)],
      "data":"0x"+w(101)+w(2)+w(0)+w(900)+w(70)+w(int(fee_recipient,16)),
      "transactionHash":"0x"+"aa"*32,"blockNumber":"0x2","logIndex":"0x1"}
  r=decode_claim(l)
  self.assertEqual(r["claim_fee_credit_raw"],70)
  self.assertEqual(r["payout_raw"],900)
  self.assertEqual(r["claim_fee_recipient"],fee_recipient)
  self.assertEqual(r["tier"],2)
 def test_withdraw_fee_for_account_to_other_recipient(self):
  account="0x"+"55"*20
  to="0x"+"66"*20
  l={"topics":[WITHDRAW,topicaddr(account),topicaddr(to)],
     "data":"0x"+w(350)+w(400),"transactionHash":"0x"+"aa"*32,
     "blockNumber":"0x5","logIndex":"0x4"}
  r=decode_withdraw(l)
  self.assertEqual(r["amount_raw"],350)
  self.assertEqual(r["account"],account)
  self.assertEqual(r["to"],to)
 def test_terminal_transfer_requires_matching_pool_and_currency(self):
  pool=DEPLOYED[1]["pool"]; token="0x"+"77"*20;to="0x"+"88"*20
  receipt={"logs":[{"address":token,"topics":[TRANSFER,topicaddr(pool),topicaddr(to)],"data":"0x"+w(80)}]}
  self.assertEqual(check_transfer(receipt,token,pool,to),80)
  self.assertEqual(check_transfer(receipt,token,pool,"0x"+"99"*20),0)
 def test_5_fixed_windows_and_budget(self):
  self.assertEqual(BATCH_SIZES,[1,2,4,8])
  self.assertEqual(RU_BUDGET,365)
  self.assertEqual(MAX_TX_PER_CHAIN,7)
if __name__=="__main__":unittest.main()
