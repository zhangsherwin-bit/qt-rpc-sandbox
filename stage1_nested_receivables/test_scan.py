"""No-network ABI and rights falsification for stream and token-bound accounts."""
import unittest
from Crypto.Hash import keccak
from stage1_nested_receivables.scan import (
 SABLIER,TBA_REGISTRY,ZERO,TRANSFER,S_CANCEL,S_WITHDRAW,S_RENOUNCE,TBA_CREATED,
 WINDOW,OFFSETS,parse_sablier,parse_tba)
def w(n):return format(int(n),"064x")
def top(n):return "0x"+w(n)
def hash(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
class TestTimedNestedRights(unittest.TestCase):
 def test_official_source_ABI(self):
  self.assertEqual(TRANSFER,hash("Transfer(address,address,uint256)"))
  self.assertEqual(S_CANCEL,hash("CancelLockupStream(uint256,address,address,address,uint128,uint128)"))
  self.assertEqual(S_WITHDRAW,hash("WithdrawFromLockupStream(uint256,address,address,uint128)"))
  self.assertEqual(S_RENOUNCE,hash("RenounceLockupStream(uint256)"))
  self.assertEqual(TBA_CREATED,hash("ERC6551AccountCreated(address,address,bytes32,uint256,address,uint256)"))
  self.assertEqual(TBA_REGISTRY,"0x000000006551c19487814612e58fe06813775758")
  self.assertEqual(WINDOW,950)
  self.assertEqual(len(OFFSETS),3)
 def test_stream_transfer_is_not_necessarily_sale(self):
  a="0x"+"11"*20;b="0x"+"22"*20
  base={"transactionHash":"0x"+"ef"*32,"blockNumber":"0x6","logIndex":"0x4","data":"0x"}
  def evt(src,dst):return {**base,"topics":[TRANSFER,top(int(src,16)),top(int(dst,16)),top(444)]}
  self.assertEqual(parse_sablier(evt(ZERO,a))["kind"],"mint")
  self.assertEqual(parse_sablier(evt(a,ZERO))["kind"],"burn")
  self.assertEqual(parse_sablier(evt(a,b))["kind"],"secondary_owner_transfer")
 def test_sender_cancellation_right_is_distinct_from_recipient_balance(self):
  a="0x"+"11"*20;b="0x"+"22"*20;c="0x"+"33"*20
  e={"transactionHash":"0x"+"ef"*32,"blockNumber":"0x6","logIndex":"0x4",
     "topics":[S_CANCEL,top(int(a,16)),top(int(b,16)),top(int(c,16))],
     "data":"0x"+w(7)+w(300)+w(200)}
  q=parse_sablier(e)
  self.assertEqual(q["kind"],"stream_cancel")
  self.assertEqual(q["sender_refund_raw"],"300")
  self.assertEqual(q["recipient_receivable_raw"],"200")
  self.assertEqual(q["stream_id"],7)
 def test_renounce_can_alter_future_claim_risk(self):
  e={"transactionHash":"0x"+"ef"*32,"blockNumber":"0x6","logIndex":"0x4",
     "topics":[S_RENOUNCE,top(44)],"data":"0x"}
  self.assertEqual(parse_sablier(e)["kind"],"renounced_cancel_right")
 def test_tba_account_is_a_right_not_a_sale(self):
  implementation="0x"+"11"*20;token="0x"+"22"*20;acct="0x"+"33"*20
  e={"transactionHash":"0x"+"ef"*32,"blockNumber":"0x6","logIndex":"0x4",
     "topics":[TBA_CREATED,top(int(implementation,16)),top(int(token,16)),top(934)],
     "data":"0x"+w(int(acct,16))+w(123)+w(1)}
  x=parse_tba(e)
  self.assertEqual(x["account"],acct)
  self.assertEqual(x["token_id"],934)
  self.assertEqual(x["chain_id"],1)
  self.assertEqual(x["implementation"],implementation)
 def test_reject_fake_registry_array(self):
  e={"topics":[TBA_CREATED,top(1),top(2),top(3)],"data":"0x",
     "transactionHash":"0x"+"ef"*32,"blockNumber":"0x6","logIndex":"0x4"}
  with self.assertRaises(ValueError):parse_tba(e)
if __name__=="__main__":unittest.main()
