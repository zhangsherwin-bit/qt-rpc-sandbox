import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scan as S
class TestActiveClaim(unittest.TestCase):
 def test_select_market(self):
  m=[{"marketId":"x","lltv":"0.8","loanAsset":{"address":S.LOANS[8453]["USDC"]},
      "collateralAsset":{"address":"0x"+"1"*40,"symbol":"Vault"},
      "state":{"borrowAssetsUsd":"100000","collateralAssetsUsd":"130000"}}]
  self.assertEqual(len(S.select(m,8453)),1)
  self.assertEqual(S.select(m,8453)[0]["collateral"],"0x"+"1"*40)
 def test_no_self_collateral(self):
  a=S.LOANS[8453]["USDC"]
  m=[{"loanAsset":{"address":a},"collateralAsset":{"address":a},"state":{"borrowAssetsUsd":"3000"}}]
  self.assertEqual(S.select(m,8453),[])
 def test_reject_nonborrowed(self):
  m=[{"loanAsset":{"address":S.LOANS[1]["WETH"]},"collateralAsset":{"address":"0x"+"3"*40},
      "state":{"borrowAssetsUsd":"0"}}]
  self.assertEqual(S.select(m,1),[])
 def test_decode_address(self):
  a=S.LOANS[1]["USDC"];self.assertEqual(S.address("0x"+a[2:].zfill(64)),a)
 def test_bounded_market_selection(self):
  a=S.LOANS[8453]["USDC"]
  markets=[{"loanAsset":{"address":a},"collateralAsset":{"address":"0x"+format(i,'040x')},
      "state":{"borrowAssetsUsd":"999"}} for i in range(1,100)]
  self.assertEqual(len(S.select(markets,8453)),24)
 def test_no_pretend_profit(self):
  s=Path(__file__).with_name("scan.py").read_text()
  self.assertIn('profit_or_liquidation_executed',s)
  self.assertIn('eligibility_verified',s)
 def test_no_signing_or_write(self):
  s=Path(__file__).with_name("scan.py").read_text()
  for v in ("eth_sendTransaction","eth_sendRawTransaction","private_key","wallet_seed","state_override"):
   self.assertNotIn(v,s)
if __name__=="__main__":unittest.main()
