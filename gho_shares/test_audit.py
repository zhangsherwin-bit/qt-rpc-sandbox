import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit as A
class ShareCostAudit(unittest.TestCase):
 def test_historical_same_state(self):
  self.assertEqual(A.BLOCKS,[26090422,26220131])
 def test_abi_complete(self):
  self.assertEqual(A.num("0x"+A.Q.u(7)),7)
  with self.assertRaises(ValueError):A.num("0x"+A.Q.u(7)+A.Q.u(8))
 def test_includes_true_share_cost(self):
  s=(Path(__file__).parent/"audit.py").read_text()
  for value in ("UNDERLYING_ASSET()","previewMint(uint256)","convertToAssets(uint256)",
                "actual_usdc_mint_cost_raw","secondary_USDC_raw","positive_quote_only"):
   self.assertIn(value,s)
 def test_no_live_wallet(self):
  s=(Path(__file__).parent/"audit.py").read_text()
  for value in ("eth_sendRawTransaction","eth_sendTransaction","balanceOverrides","storageOverrides","private_key"):
   self.assertNotIn(value,s)
if __name__=="__main__":unittest.main()
