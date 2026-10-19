import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import census as C
class TestFluidEvents(unittest.TestCase):
 def test_fixed_window(self):
  self.assertEqual(C.WINDOW,57000)
  self.assertEqual(len(range(C.START,C.END+1,C.BLOCK_STEP)),6)
 def test_selector(self):self.assertEqual(len(C.EVENT),66)
 def test_decode(self):
  from fluid_stage1 import screen as S
  vault="0x"+"12"*20
  actor=int("0x"+"13"*20,16);receiver=int("0x"+"14"*20,16)
  log={"topics":[C.EVENT],"address":vault,"data":"0x"+"".join(S.u(v) for v in [actor,124,100,receiver]),
       "transactionHash":"0x"+"33"*32,"blockNumber":hex(C.END),"logIndex":"0x2"}
  row=C.event_decode(log,{vault})
  self.assertEqual(int(row["collateral_raw"]),124)
  self.assertEqual(int(row["debt_raw"]),100)
  self.assertEqual(row["gross_profit_USDC"],"UNKNOWN")
 def test_no_signing(self):
  s=(Path(__file__).parent/"census.py").read_text()
  for x in ("eth_sendRawTransaction","eth_sendTransaction","private_key","balanceOverrides","storageOverrides"):
   self.assertNotIn(x,s)
if __name__=="__main__":unittest.main()
