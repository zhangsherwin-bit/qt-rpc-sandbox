import unittest
from stage1_payfirst_burn.scan import(
 SOURCES,TOKENS_BURNED,THRESHOLD_SELECTOR,parse_burn_event,
 OFFSETS,WIDTH,CAP_RPC_REQUESTS)
from Crypto.Hash import keccak
def topic(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
def w(x):return format(int(x),"064x")
class TestBurn(unittest.TestCase):
 def test_contract_event_signature(self):
  self.assertEqual(TOKENS_BURNED,topic("TokensBurned(uint256,address,uint256)"))
  self.assertEqual(THRESHOLD_SELECTOR,topic("minCurrency1BurnAmount()")[:10])
 def test_burn_event_is_claim_cost_not_claimant_income(self):
  t="0x"+"22"*20
  e=parse_burn_event({"topics":[TOKENS_BURNED,"0x"+w(55),"0x"+w(int(t,16))],
    "data":"0x"+w(500000*10**18),"transactionHash":"0x"+"aa"*32,"blockNumber":"0x100"})
  self.assertEqual(e["token_id"],"55")
  self.assertEqual(e["burned_token"],t)
  self.assertEqual(e["burn_amount_raw"],str(500000*10**18))
  self.assertNotIn("claim_payout",e)
 def test_two_distinct_network_native_assets(self):
  self.assertEqual([s["chain_id"] for s in SOURCES],[4663,5042])
  self.assertEqual(SOURCES[0]["native"],"ETH")
  self.assertIn("USDC",SOURCES[1]["native"])
 def test_no_authenticated_key_or_many_requests(self):
  self.assertEqual(OFFSETS,[250,15000,60000])
  self.assertEqual(WIDTH,450)
  self.assertEqual(CAP_RPC_REQUESTS,19)
 def test_wrong_abi_bad(self):
  with self.assertRaises(ValueError):
   parse_burn_event({"topics":[],"data":"0x"})
if __name__=="__main__":unittest.main()
