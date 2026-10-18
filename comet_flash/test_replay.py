"""Offline regression controls; on-chain cash must separately pass real simulation."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import replay as R
class TestFlash(unittest.TestCase):
 def test_pinned_market_and_case(self):
  self.assertEqual(R.BLOCK,25984761)
  self.assertEqual(R.AMOUNT,9346567826)
  self.assertEqual(R.OBS_COLL,4138078068736368148)
 def test_frozen_original_receipt(self):
  row=R.sourced_case()
  self.assertEqual(row['asset'],R.WETH)
  self.assertTrue(row['receipt_verified'])
  self.assertEqual(row['block'],R.BLOCK)
 def test_erc20_transfer_event(self):
  self.assertEqual(R.TRANSFER,'0x'+R.k('Transfer(address,address,uint256)'))
 def test_calldata(self):
  self.assertEqual(len(R.method('run(uint256,uint24,uint256)',R.AMOUNT,500,1000000)),2+8+64*3)
 def test_payout_does_not_use_mocked_funds(self):
  s=Path('comet_flash/CometCashProbe.sol').read_text()
  self.assertIn('flashLoanSimple',s)
  self.assertIn('buyCollateral(WETH,0,amount,address(this))',s)
  self.assertIn('amount+premium+minProfit',s)
  self.assertIn('IERC20(USDC).balanceOf(BENEF)==pre+cashOut',s)
 def test_no_simulated_liquidity_override(self):
  s=(Path(__file__).parent/'replay.py').read_text()
  self.assertIn("stateOverrides':{PROBE:{'code':code}",s)
  for bad in ("balanceOverrides","storageOverrides","eth_sendTransaction","eth_sendRawTransaction","wallet_seed","private_key"):
   self.assertNotIn(bad,s)
 def test_output_must_be_real_transfer(self):
  s=(Path(__file__).parent/'replay.py').read_text()
  self.assertIn('cash transfer not proven',s.lower())
  self.assertIn('rollback_verified',s)
 def test_reserved_october_not_used(self):
  self.assertTrue(R.BLOCK<26093737)
if __name__=='__main__':unittest.main()
