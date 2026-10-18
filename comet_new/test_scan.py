"""Offline ABI, scope and cash-claim controls; does not contact RPC."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scan as R
class TestComet(unittest.TestCase):
 def test_scope(self):
  self.assertEqual(len(R.DEPLOYMENTS[1]),6)
  self.assertEqual(len(R.DEPLOYMENTS[8453]),5)
  self.assertEqual(sum((hi-lo)//9500+1 for v in R.WINDOWS.values() for lo,hi in v),11)
 def test_event_topics_unique(self):
  self.assertEqual(len(R.BUY),66)
  self.assertEqual(len(R.ABS),66)
  self.assertNotEqual(R.BUY,R.ABS)
 def test_buy_event(self):
  w=lambda x:format(x,'064x')
  l={"topics":[R.BUY,"0x"+w(1),"0x"+w(2)],"data":"0x"+w(100)+w(150),"logIndex":"0x0",
     "blockNumber":"0x99","transactionHash":"0x"+"f"*64,"address":"0x"+"e"*40}
  self.assertEqual(R.interpret(l)["base_amount_raw"],"100")
 def test_absorb_event(self):
  w=lambda x:format(x,'064x')
  l={"topics":[R.ABS,"0x"+w(1),"0x"+w(2),"0x"+w(3)],"data":"0x"+w(44)+w(900),"logIndex":"0x0",
     "blockNumber":"0x99","transactionHash":"0x"+"f"*64,"address":"0x"+"e"*40}
  self.assertEqual(R.interpret(l)["usd_value_raw"],"900")
 def test_select_distinct(self):
  e=lambda market,asset,block:{"market":market,"asset":asset,"block":block,"tx":"0x"+format(block,'064x'),"logIndex":0}
  self.assertEqual(len(R.choose([e("a","x",1),e("a","x",1),e("a","x",2),e("b","y",2)])),3)
 def test_no_unsigned_cash_claim(self):
  s=(Path(__file__).parent/"scan.py").read_text()
  self.assertIn('full_cash_execution":False',s)
  self.assertIn('gross_only_no_fees_or_approval',s)
 def test_no_send_calls(self):
  s=(Path(__file__).parent/"scan.py").read_text()
  for word in ("eth_sendTransaction","eth_sendRawTransaction","private_key","wallet_seed"):
   self.assertNotIn(word,s)
if __name__=="__main__":unittest.main()
