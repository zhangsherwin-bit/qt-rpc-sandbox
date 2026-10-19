import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import screen as X

class FluidTests(unittest.TestCase):
 def test_liquidation_abi(self):
  addr="0x"+"12"*20
  values=[int(addr,16),int("0x"+"11"*20,16),int("0x"+"22"*20,16),0,0,100,107,101,108,1]
  raw="0x"+"".join(X.u(v) for v in values)
  x=X.decode_liquidation(raw,addr)
  self.assertTrue(x["liquidatable_now"])
  self.assertTrue(x["absorb_available"])
  self.assertEqual(int(x["max_debt_in_raw"]),100)
  self.assertEqual(int(x["max_collateral_out_raw"]),107)
 def test_no_inventory(self):
  addr="0x"+"12"*20
  raw="0x"+"".join(X.u(v) for v in [int(addr,16),0,0,0,0,0,0,0,0,0])
  self.assertFalse(X.decode_liquidation(raw,addr)["liquidatable_now"])
 def test_exact_selection(self):
  lst=["0x"+f"{i:040x}" for i in range(100)]
  chosen=X.selection(lst)
  self.assertLessEqual(len(chosen),30)
  self.assertEqual(chosen[0]["index"],0)
  self.assertEqual(chosen[-1]["index"],99)
  self.assertEqual(len(set(x["index"] for x in chosen)),len(chosen))
 def test_pair_envelope(self):
  self.assertEqual({x["chain"] for x in X.ANCHORS},{1,8453})
  self.assertEqual(X.FEE_TIERS,[500,3000])
 def test_no_new_money_or_trading(self):
  s=(Path(__file__).parent/"screen.py").read_text()
  for word in ("eth_sendRawTransaction","eth_sendTransaction","private_key","balanceOverrides","storageOverrides","wallet_seed"):
   self.assertNotIn(word,s)
  self.assertIn('"no_transaction_or_profit_claim":True',s)
if __name__=="__main__":unittest.main()
