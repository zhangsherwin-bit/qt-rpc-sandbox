"""Keyless Cork Phoenix source/rights activity screen offline regression."""
import unittest
from Crypto.Hash import keccak
from stage1_cork_rights.public_probe import (
 POOL,WHITELIST,MARKET,SWAP,MODIFY,TOPICS,OFFSETS,WINDOW,
 SELECTOR_MARKET,SELECTOR_WHITELIST,parse,market_result,number
)
def word(n): return format(int(n),"064x")
def indexed_address(a):return "0x"+word(int(a,16))
class TestCorkRights(unittest.TestCase):
 def test_source_pinned_addresses(self):
  self.assertEqual(POOL,"0xccccccccccccfae2ee43f0e727a8c2969d74b9ec")
  self.assertEqual(WHITELIST,"0xccccccccccc6e38a2772eb42d2f408eeb89cb0ee")
 def test_exact_event_topics_and_function_selectors(self):
  src={
   "MarketCreated(bytes32,address,address,uint256,address,address,address)":MARKET,
   "PoolSwap(bytes32,address,address,uint256,uint256,uint256,uint256,bool)":SWAP,
   "PoolModifyLiquidity(bytes32,address,address,uint256,uint256,bool)":MODIFY,
  }
  for signature,t in src.items():
   h=keccak.new(digest_bits=256);h.update(signature.encode())
   self.assertEqual(t,"0x"+h.hexdigest())
   self.assertEqual(len(t),66)
  for name,selector in [("market(bytes32)",SELECTOR_MARKET),
                         ("isMarketWhitelistEnabled(bytes32)",SELECTOR_WHITELIST)]:
   h=keccak.new(digest_bits=256);h.update(name.encode())
   self.assertEqual(selector,"0x"+h.hexdigest()[:8])
 def test_three_indexed_event_topics_parse(self):
  claim="0x"+"ab"*32;sender="0x"+"12"*20;owner="0x"+"45"*20
  log={"topics":[MARKET,claim,indexed_address(sender),indexed_address(owner)],
       "address":POOL,"transactionHash":"0x"+"cc"*32,"blockNumber":"0x20","logIndex":"0x3"}
  result=parse(log)
  self.assertEqual(result["kind"],"MarketCreated")
  self.assertEqual(result["market_id"],claim)
  self.assertEqual(result["block"],32)
  log["address"]=WHITELIST
  with self.assertRaises(ValueError):parse(log)
 def test_market_static_struct_decode_preserves_expiry_and_addresses(self):
  ca="0x"+"12"*20;ref="0x"+"34"*20;oracle="0x"+"56"*20
  fields=[int(ca,16),int(ref,16),1785000000,10**17,10**18,23,234,int(oracle,16)]
  market=market_result("0x"+"".join(word(v) for v in fields))
  self.assertEqual(market["collateral"],ca)
  self.assertEqual(market["reference"],ref)
  self.assertEqual(market["expiry_timestamp"],1785000000)
  self.assertEqual(market["rate_oracle"],oracle)
  self.assertEqual(market["rate_min"],10**17)
 def test_invalid_market_output_rejected(self):
  with self.assertRaises(ValueError):market_result("0x00")
 def test_frozen_sources_keyless_throttle(self):
  self.assertEqual(len(OFFSETS),6)
  self.assertEqual(WINDOW,100)
  self.assertEqual(len(TOPICS),3)
  self.assertGreater(min(OFFSETS),100)
  self.assertEqual(number("0x10"),16)
if __name__=="__main__":unittest.main()
