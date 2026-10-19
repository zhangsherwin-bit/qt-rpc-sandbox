"""Offline tests, built from UMA's published ABI and Convex ERC20 interface."""
import unittest
from stage1_contrarian.census import (
    SETTLED, DISPUTED, TRANSFER, CONVEX_BOOSTER,
    UMA_OOV3, parse_settled, parse_disputed, parse_crv_transfer, decode_assertion,
    windows, addrword, EARMARK_SELECTOR, MAX_AUTH_RU)
def word(v):
 return format(v,"064x")
def topic_address(a):
 return "0x"+word(int(a,16))
class ContractTest(unittest.TestCase):
 def test_oracles_from_official_deployments(self):
  self.assertEqual(UMA_OOV3[1],"0xfb55f43fb9f48f63f9269db7dde3bbbe1ebdc0de")
  self.assertEqual(UMA_OOV3[8453],"0x2abf1bd76655de80edb3086114315eec75af500c")
 def test_exact_disputed_event_abi(self):
  caller="0x"+"aa"*20;disputer="0x"+"bb"*20
  r=parse_disputed({"topics":[DISPUTED,"0x"+"ab"*32,topic_address(caller),topic_address(disputer)],
    "blockNumber":"0x1","logIndex":"0x2","transactionHash":"0x"+"cc"*32})
  self.assertEqual(r["disputer"],disputer)
  self.assertEqual(r["kind"],"disputed")
 def test_settlement_abi_and_no_proposer_bounty_assumption(self):
  caller="0x"+"55"*20;winner="0x"+"66"*20
  log={"topics":[SETTLED,"0x"+"ab"*32,topic_address(winner)],
   "data":"0x"+word(1)+word(0)+word(int(caller,16)),
   "blockNumber":"0x15","logIndex":"0x1","transactionHash":"0x"+"cc"*32,
   "address":UMA_OOV3[1]}
  r=parse_settled(log)
  self.assertTrue(r["disputed"]);self.assertFalse(r["settlementResolution"])
  self.assertEqual(r["bondRecipient"],winner)
  self.assertEqual(r["settleCaller"],caller)
 def test_bond_payout_reference(self):
  B=1000
  burned=500000000000000000
  net=2*B-B*burned//10**18-B
  self.assertEqual(net,500)
  self.assertEqual(2*B-B*burned//10**18,1500)
 def test_decode_struct_16_words_not_dynamic(self):
  v=[0]*16
  v[5]=int("11"*20,16);v[8]=int("22"*20,16)
  v[13]=765000;v[15]=int("33"*20,16);v[7]=1
  decoded=decode_assertion("0x"+"".join(word(n) for n in v))
  self.assertEqual(decoded["bond_raw"],765000)
  self.assertEqual(decoded["disputer"],"0x"+"33"*20)
  self.assertTrue(decoded["settled"])
 def test_booster_transfer(self):
  receiver="0x"+"44"*20;amount=777
  l={"topics":[TRANSFER,topic_address(CONVEX_BOOSTER),topic_address(receiver)],
     "data":"0x"+word(amount),"transactionHash":"0x"+"aa"*32,
     "blockNumber":"0x123","logIndex":"0x2",
     "address":"0xd533a949740bb3306d119cc777fa900ba034cd52"}
  row=parse_crv_transfer(l)
  self.assertEqual(row["amount_wei"],amount)
  self.assertEqual(row["to"],receiver)
  self.assertEqual(EARMARK_SELECTOR[0:2],"0x")
 def test_windows_safe_disjoint_and_budget(self):
  a=windows(1_000_000)
  self.assertEqual(len(a),4)
  self.assertEqual(MAX_AUTH_RU,430)
  for x in a:self.assertEqual(x["end"]-x["start"]+1,7000)
  for v,w in zip(a,a[1:]):self.assertGreater(v["start"],w["end"])
if __name__=="__main__":unittest.main()
