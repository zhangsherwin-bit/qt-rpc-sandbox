import unittest,sys,decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import screen as S
D=decimal.Decimal
class TestNegativeRisk(unittest.TestCase):
 def test_token_id_parser(self):
  self.assertEqual(S.tokenpair({"clobTokenIds":'["11","22"]'}),("11","22"))
 def test_depth_finite(self):
  b={"asks":[{"price":"0.3","size":"4"},{"price":"0.2","size":"2"}],"bids":[{"price":"0.9","size":"3"},{"price":"0.8","size":"3"}]}
  self.assertEqual(S.notional(b,"asks",D(5)),D("1.3"))
  self.assertEqual(S.notional(b,"bids",D(5)),D("4.3"))
  self.assertIsNone(S.notional(b,"bids",D(7)))
 def test_ineligible_placeholder(self):
  e={"negRisk":True,"negRiskAugmented":True,"markets":[{"active":True,"closed":False,"clobTokenIds":'["1","2"]'}]*3}
  self.assertFalse(S.event_select(e))
 def test_no_negative_risk_false_positive(self):
  e={"negRisk":False,"markets":[{"active":True,"closed":False,"clobTokenIds":'["1","2"]'}]*3}
  self.assertFalse(S.event_select(e))
 def test_conservation_required(self):
  m=[{"id":str(i),"active":True,"closed":False,"negRisk":True,"clobTokenIds":f'["{10*i+1}","{10*i+2}"]'} for i in range(3)]
  b={}
  for i in range(3):
   b[str(10*i+1)]={"bids":[{"price":"0.4","size":"10"}]}
   b[str(10*i+2)]={"asks":[{"price":"0.7","size":"10"}]}
  rows=S.calc({"markets":m},b)
  self.assertEqual(sum(r.get("positive",False) for r in rows),len(m))
  del b["21"];self.assertEqual(sum(r.get("positive",False) for r in S.calc({"markets":m},b)),1)
 def test_no_trade_path(self):
  t=(Path(__file__).parent/"screen.py").read_text()
  for bad in ("eth_sendTransaction","eth_sendRawTransaction","private_key","wallet_seed"):self.assertNotIn(bad,t)
if __name__=="__main__":unittest.main()
