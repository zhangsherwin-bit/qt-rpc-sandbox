"""Offline ABI and economic consistency checks for Uniswap Firepit entitlement."""
import unittest
from Crypto.Hash import keccak as h
from stage1_firepit.screen import (
  JAR,FIREPIT,UNI,DEAD,ASSETS,RELEASED,TRANSFER,
  WINDOW,OFFSETS,MAX_RU,RESERVE_RU,decode_released,process,word)
def topic(x):return "0x"+word(x)
def sig(s):
 k=h.new(digest_bits=256);k.update(s.encode());return "0x"+k.hexdigest()
class TestFeeRelease(unittest.TestCase):
 def test_official_fixed_release_abi(self):
  self.assertEqual(RELEASED,sig("Released(uint256,address,address[])"))
  self.assertEqual(TRANSFER,sig("Transfer(address,address,uint256)"))
  self.assertEqual(JAR,"0xf38521f130fccf29db1961597bc5d2b60f995f85")
  self.assertEqual(FIREPIT,"0x0d5cd355e2abeb8fb1552f56c965b867346d6721")
  self.assertEqual(len(OFFSETS),4)
  self.assertEqual(MAX_RU,170)
  self.assertEqual(RESERVE_RU,1500)
 def test_decode_dynamic_array_up_to_20(self):
  a=ASSETS["WETH"];b=ASSETS["USDC"];recipient="0x"+"ab"*20
  rec={"transactionHash":"0x"+"ac"*32,"blockNumber":"0x10","logIndex":"0x2",
       "topics":[RELEASED,topic(17),topic(int(recipient,16))],
       "data":"0x"+word(32)+word(2)+word(int(a,16))+word(int(b,16))}
  found=decode_released(rec)
  self.assertEqual(found["assets"],[a.lower(),b.lower()])
  self.assertEqual(found["recipient"],recipient)
  self.assertEqual(found["nonce"],17)
  self.assertEqual(found["block"],16)
 def test_reject_too_many_assets(self):
  rec={"transactionHash":"0x"+"ab"*32,"blockNumber":"0x10","logIndex":"0x0",
       "topics":[RELEASED,topic(1),topic(1)],"data":"0x"+word(32)+word(21)}
  with self.assertRaises(ValueError):decode_released(rec)
 def test_erc20_burn_not_release_pnl(self):
  sender="0x"+"ad"*20;recipient="0x"+"ab"*20
  release={"tx":"0x"+"ee"*32,"block":12,"nonce":5,"recipient":recipient,"assets":[ASSETS["WETH"]]}
  tx={"hash":release["tx"],"from":sender,"to":FIREPIT}
  rc={"status":"0x1","blockNumber":"0xc","transactionHash":release["tx"],
       "gasUsed":"0x5208","effectiveGasPrice":"0x3b9aca00",
       "logs":[
         {"address":UNI,"topics":[TRANSFER,topic(int(sender,16)),topic(int(DEAD,16))],"data":hex(4000*10**18)},
         {"address":ASSETS["WETH"],"topics":[TRANSFER,topic(int(JAR,16)),topic(int(recipient,16))],"data":hex(8*10**18)}
       ]}
  result=process(release,rc,tx)
  self.assertEqual(result["payer_from_ERC20_burn_events_wei"][sender],str(4000*10**18))
  self.assertEqual(result["received_from_jar_ERC20_raw"][ASSETS["WETH"]],str(8*10**18))
  self.assertTrue(result["cash_profit_after_bid_unknown"])
 def test_wrong_recipient_does_not_get_payout(self):
  sender="0x"+"ad"*20;recipient="0x"+"ab"*20
  release={"tx":"0x"+"ee"*32,"block":12,"nonce":5,"recipient":recipient,"assets":[ASSETS["WETH"]]}
  tx={"hash":release["tx"],"from":sender,"to":FIREPIT}
  rc={"status":"0x1","blockNumber":"0xc","transactionHash":release["tx"],
       "gasUsed":"0x1","effectiveGasPrice":"0x1",
       "logs":[{"address":ASSETS["WETH"],
       "topics":[TRANSFER,topic(int(JAR,16)),topic(int(sender,16))],"data":hex(8*10**18)}]}
  self.assertEqual(process(release,rc,tx)["received_from_jar_ERC20_raw"],{})
 def test_asset_list_is_not_total_jar(self):
  self.assertLessEqual(len(ASSETS),20)
  self.assertTrue(all(len(v)==42 for v in ASSETS.values()))
  self.assertLess(WINDOW,10000)
if __name__=="__main__":unittest.main()
