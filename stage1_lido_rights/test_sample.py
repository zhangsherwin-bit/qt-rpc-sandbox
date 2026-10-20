"""Offline external-source rights and ABI tests. Absolutely no network usage."""
import unittest
from Crypto.Hash import keccak
from stage1_lido_rights.sample import (QUEUE,ZERO,TRANSFER,GET_STATUS,decode_transfer,
  status_arg,decode_one_status,receipt_simple,MAX_RU,PROTECTED_RU,WINDOW_BLOCKS,END_OFFSETS)
def h(a):
 return "0x"+format(int(a,16),"064x")
def w(i):
 return format(int(i),"064x")
class RightsGateTests(unittest.TestCase):
 def logs(self,from_,to,token_id=312):
  return {"topics":[TRANSFER,h(from_),h(to),"0x"+w(token_id)],
          "address":QUEUE,"transactionHash":"0x"+"ab"*32,
          "blockNumber":"0x1100","logIndex":"0x3"}
 def test_lido_official_address_and_event(self):
  self.assertEqual(QUEUE,"0x889edc2edab5f40e902b864ad4d7ade8e412f9b1")
  sig=keccak.new(digest_bits=256);sig.update(b"Transfer(address,address,uint256)")
  self.assertEqual(TRANSFER,"0x"+sig.hexdigest())
 def test_erc721_transfer_is_not_mint_or_burn(self):
  first="0x"+"11"*20;second="0x"+"22"*20
  self.assertEqual(decode_transfer(self.logs(first,second))["kind"],"TRANSFER_NONZERO")
  self.assertEqual(decode_transfer(self.logs(ZERO,first))["kind"],"MINT")
  self.assertEqual(decode_transfer(self.logs(first,ZERO))["kind"],"BURN")
  self.assertEqual(decode_transfer(self.logs(first,first))["kind"],"SELF")
 def test_wrong_asset_emitter_rejected(self):
  log=self.logs("0x"+"11"*20,"0x"+"22"*20)
  log["address"]="0x"+"99"*20
  with self.assertRaises(ValueError):decode_transfer(log)
 def test_exact_abi_dynamic_array_of_struct(self):
  owner="0x"+"42"*20
  words=[32,1,10**19,9*10**18,int(owner,16),1780000000,1,0]
  st=decode_one_status("0x"+"".join(w(n) for n in words))
  self.assertEqual(st["amount_steth_wei"],str(10**19))
  self.assertEqual(st["owner"],owner)
  self.assertTrue(st["finalized"])
  self.assertFalse(st["claimed"])
  self.assertTrue(status_arg(312).startswith(GET_STATUS))
 def test_mismatch_owner_stays_observed_transfer_not_sale(self):
  o=decode_transfer(self.logs("0x"+"11"*20,"0x"+"22"*20))
  tx={"hash":o["tx"],"from":o["from"],"to":"0x"+"33"*20,"value":"0x0"}
  rc={"transactionHash":o["tx"],"status":"0x1","gasUsed":"0x5208",
      "effectiveGasPrice":"0x12a05f200","logs":[]}
  out=receipt_simple(o,tx,rc,{"owner":o["from"]})
  self.assertFalse(out["status_owner_matches_nonzero_transferee_at_block_end"])
  self.assertIn("NOT proof",out["interpretation"])
 def test_budget_and_frozen_sampling(self):
  self.assertEqual(MAX_RU,135)
  self.assertEqual(PROTECTED_RU,1500)
  self.assertEqual(len(END_OFFSETS),6)
  self.assertEqual(WINDOW_BLOCKS,160)
  self.assertEqual(len(set(END_OFFSETS)),6)
if __name__=="__main__":unittest.main()
