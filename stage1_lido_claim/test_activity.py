import unittest
from Crypto.Hash import keccak
from stage1_lido_claim.activity import (
    QUEUE,ZERO,TRANSFER,REQUEST,CLAIM,OFFSETS,WIDTH,MAX_RU,FLOOR,
    parse,classify_payment)
def topic(v):return "0x"+format(int(v),"064x")
def addr(v):return topic(v)
def sig(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
class TestLidoRights(unittest.TestCase):
 def test_abi_against_source(self):
  self.assertEqual(TRANSFER,sig("Transfer(address,address,uint256)"))
  self.assertEqual(REQUEST,sig("WithdrawalRequested(uint256,address,address,uint256,uint256)"))
  self.assertEqual(CLAIM,sig("WithdrawalClaimed(uint256,address,address,uint256)"))
  self.assertEqual(QUEUE,"0x889edc2edab5f40e902b864ad4d7ade8e412f9b1")
 def test_ownership_vs_mint_and_burn(self):
  buyer="0x"+"11"*20;seller="0x"+"22"*20
  base={"transactionHash":"0x"+"aa"*32,"blockNumber":"0x7","logIndex":"0x0","data":"0x"}
  def make(a,b):
   return {**base,"topics":[TRANSFER,topic(int(a,16)),topic(int(b,16)),topic(73)]}
  self.assertEqual(parse(make(ZERO,buyer))["kind"],"mint")
  self.assertEqual(parse(make(seller,ZERO))["kind"],"burn")
  obj=parse(make(seller,buyer))
  self.assertEqual(obj["kind"],"secondary_owner_transfer")
  self.assertEqual(obj["from"],seller)
  self.assertEqual(obj["to"],buyer)
  self.assertEqual(obj["id"],73)
 def test_requested_and_claim_event_no_misprice(self):
  owner="0x"+"44"*20
  l={"topics":[REQUEST,topic(3),topic(int(owner,16)),topic(int(owner,16))],
   "data":"0x"+format(1200,"064x")+format(1180,"064x"),
   "transactionHash":"0x"+"aa"*32,"blockNumber":"0x4","logIndex":"0x1"}
  row=parse(l)
  self.assertEqual(row["amount_steth_raw"],1200)
  self.assertEqual(row["amount_shares_raw"],1180)
  self.assertNotIn("eth_claimed_raw",row)
  cl={**l,"topics":[CLAIM,topic(3),topic(int(owner,16)),topic(int(owner,16))],
      "data":hex(1199)}
  # ABI output data must be 32-byte word: strict parser to reject nonsense
  cl["data"]="0x"+format(1199,"064x")
  self.assertEqual(parse(cl)["eth_claimed_raw"],1199)
 def test_payment_is_hint_not_proof(self):
  a="0x"+"11"*20;b="0x"+"22"*20;token="0x"+"33"*20
  r={"logs":[{"address":token,
       "topics":[TRANSFER,topic(int(a,16)),topic(int(b,16))],
       "data":"0x"+format(1000,"064x")}]}
  self.assertEqual(len(classify_payment(r,b,a)),1)
  self.assertEqual(classify_payment(r,a,b),[])
 def test_no_broad_or_recursive_backfill(self):
  self.assertEqual(len(OFFSETS),4)
  self.assertEqual(WIDTH,250)
  self.assertEqual(MAX_RU,90)
  self.assertEqual(FLOOR,1500)
if __name__=="__main__":unittest.main()
