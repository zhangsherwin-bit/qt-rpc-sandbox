"""Offline controls for the new direct-producer-payment historical replay."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import check as C
class TestNativeBid(unittest.TestCase):
 def test_four_fee_pools(self):
  self.assertEqual(C.BASE_FEE_VARIANTS,(100,500,3000,10000))
 def test_bid_matches_canonical_winner(self):
  self.assertEqual(C.BID,174449845338543024)
 def test_historical_case_fixed(self):
  self.assertEqual(C.F.ORIGINAL_TX,"0x9a710e9b980957f1418a3578d6601b5e85e4ef0784c42e97cdbf7fe864bd9a4a")
  self.assertEqual(C.F.AMOUNT,9346567826)
 def test_selector_and_logged_event(self):
  self.assertEqual(len(C.EVENT),66)
  self.assertEqual(len(C.F.method("run(uint256,uint24,bool)",C.F.AMOUNT,500,1)),2+8+3*64)
 def test_environment_wrong_length_rejected(self):
  with self.assertRaises(ValueError):C.env_words({"status":"0x1","returnData":"0x"+'00'*32})
 def test_revert_environment_rejected(self):
  with self.assertRaises(ValueError):C.env_words({"status":"0x0","returnData":"0x"})
 def test_no_real_trading_methods(self):
  text=(Path(__file__).parent/'check.py').read_text()
  for bad in ("eth_sendRawTransaction","eth_sendTransaction","personal_sign","wallet_seed","private_key"):
   self.assertNotIn(bad,text)
 def test_production_state_not_overridden(self):
  text=(Path(__file__).parent/'check.py').read_text()
  self.assertNotIn("balanceOverrides",text)
  self.assertNotIn("storageOverrides",text)
 def test_native_exact_output_and_final_eth(self):
  sol=(Path(__file__).parent/'CometNativeBidProbe.sol').read_text()
  for token in ("exactOutputSingle","IWETHD(WETH).withdraw(left)","block.coinbase","BENEF).call{value:beneficiaryWei}"):
   self.assertIn(token,sol)
 def test_decoded_env_balance_comparison(self):
  src=(Path(__file__).parent/'check.py').read_text()
  self.assertIn('if a[7:9]!=b[7:9]:',src)
  self.assertNotIn('if after[7:9]!=before[7:9]:',src)
  a=list(range(11));b=a.copy();self.assertEqual(a[7:9],b[7:9]);b[7]+=1;self.assertNotEqual(a[7:9],b[7:9])
 def test_production_addresses_frozen(self):
  self.assertEqual(C.F.COMET.lower(),"0xc3d688b66703497daa19211eedff47f25384cdc3")
if __name__=='__main__':unittest.main()
