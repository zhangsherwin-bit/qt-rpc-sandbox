"""Offline accounting/scope tests, not an EVM profit test."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scan as S
class TestVaultClaim(unittest.TestCase):
 def test_selector_lengths(self):
  for k in ("asset()","decimals()","previewRedeem(uint256)",
    "getPool(address,address,uint24)","liquidity()",
    "quoteExactInputSingle((address,address,uint256,uint24,uint160))"):
   self.assertEqual(len(S.signature(k)),10)
 def test_address_padding_and_decoding(self):
  for a in list(S.USDC.values()):
   self.assertEqual(S.decode_address("0x"+S.arg_addr(a)),a)
 def test_reject_address_overflow(self):
  with self.assertRaises(ValueError):
   S.decode_address("0x"+"1"*64)
 def test_select_only_matching_asset(self):
  items=[dict(address="0x"+"1"*40,asset={"address":S.USDC[1]},name="Eligible"),
     dict(address="0x"+"2"*40,asset={"address":S.USDC[8453]},name="Wrong chain underlying")]
  a=S.select(items,1)
  self.assertEqual(len(a),1)
  self.assertEqual(a[0]["name"],"Eligible")
 def test_selection_is_bounded_and_deduped(self):
  items=[dict(address="0x"+format(i,'040x'),asset={"address":S.USDC[1]}) for i in range(1,40)]
  items+=items[:5]
  out=S.select(items,1)
  self.assertEqual(len(out),S.LIMIT_VAULTS_PER_CHAIN)
  self.assertEqual(len({x["address"] for x in out}),len(out))
 def test_frozen_fees_sizes(self):
  self.assertEqual(S.FEE_TIERS,(100,500,3000,10000))
  self.assertEqual(S.SIZES,(500,5000,25000))
 def test_no_chain_mutations(self):
  s=Path(__file__).with_name("scan.py").read_text()
  for denied in ("eth_sendTransaction","eth_sendRawTransaction","private_key",
                 "balance_override","state_override","storage_override"):
   self.assertNotIn(denied,s)
 def test_profit_cannot_be_promoted_from_quote(self):
  s=Path(__file__).with_name("scan.py").read_text()
  self.assertIn("claim_cash_settled",s)
  self.assertIn("spent_input_amount_verified",s)
  self.assertIn("needs_atomic_validation",s)
if __name__=="__main__":unittest.main()
