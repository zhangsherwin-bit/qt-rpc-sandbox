import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import check as C
class TestClaimEligibility(unittest.TestCase):
 def test_market_scope_exact(self):
  self.assertEqual(len(C.MARKETS),3)
  self.assertEqual({v["name"] for v in C.MARKETS},{"yoETH_WETH_Base","sUSDX_USDC_Base","USD3_USDC_Ethereum"})
 def test_cash_preview_not_proven_redeem(self):
  s=(Path(__file__).parent/"check.py").read_text()
  self.assertIn("cash_profit_established",s)
  self.assertIn("Positive previewRedeem is NOT instant cash",s)
 def test_hashes_and_addresses(self):
  for m in C.MARKETS:
   self.assertEqual(len(m["id"]),66)
   self.assertEqual(len(m["vault"]),42)
   self.assertEqual(len(m["loan"]),42)
 def test_erc20_encoding(self):
  self.assertEqual(C.a(C.MARKETS[0]["vault"]),"0"*24+C.MARKETS[0]["vault"][2:])
 def test_actual_decimals(self):
  s=(Path(__file__).parent/"check.py").read_text()
  self.assertIn('decimals=parse_uint(dec["return"])',s)
 def test_no_broadcasts(self):
  s=(Path(__file__).parent/"check.py").read_text()
  for disallow in ("eth_sendRawTransaction","eth_sendTransaction","wallet_seed","private_key","state_override"):
   self.assertNotIn(disallow,s)
if __name__=="__main__":unittest.main()
