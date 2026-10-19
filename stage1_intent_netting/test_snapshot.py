import unittest
from stage1_intent_netting.snapshot import (
    normalize_order,all_nonnegative_inventory,evaluate,net,SOURCES
)
A="0x"+"11"*20;B="0x"+"22"*20;C="0x"+"33"*20
def make(ident,chain,typ,coin,other,input_amount,output_amount,fee=0):
    return {"orderId":ident,"type":typ,"chainId":chain,"orderStatus":"open",
      "input":{"token":coin,"startAmount":str(input_amount),"endAmount":str(input_amount)},
      "outputs":[{"token":other,"startAmount":str(output_amount),"endAmount":str(output_amount)},
         *([{"token":other,"startAmount":str(fee),"endAmount":str(fee),"isFeeOutput":True}] if fee else [])]}
class TestNetting(unittest.TestCase):
 def test_true_opposing_orders_positive_residuals(self):
  xs=[normalize_order(make("a",8453,"Dutch_V3",A,B,110,100),8453,"Dutch_V3"),
      normalize_order(make("b",8453,"Dutch_V3",B,A,110,100),8453,"Dutch_V3")]
  self.assertTrue(all_nonnegative_inventory(xs))
  self.assertEqual(net(xs),{A:10,B:10})
  self.assertEqual(evaluate(xs)["conservative_envelope_pass_pair"],1)
 def test_protocol_fee_outputs_break_illusion(self):
  xs=[normalize_order(make("a",8453,"Dutch_V3",A,B,110,100,30),8453,"Dutch_V3"),
      normalize_order(make("b",8453,"Dutch_V3",B,A,110,100),8453,"Dutch_V3")]
  self.assertEqual(xs[0]["fee_outputs_count"],1)
  self.assertFalse(all_nonnegative_inventory(xs))
  self.assertEqual(evaluate(xs)["conservative_envelope_pass_pair"],0)
 def test_token_mismatch_not_par_value(self):
  xs=[normalize_order(make("a",1,"Dutch_V2",A,B,100,90),1,"Dutch_V2"),
      normalize_order(make("b",1,"Dutch_V2",B,C,95,85),1,"Dutch_V2")]
  self.assertFalse(all_nonnegative_inventory(xs))
 def test_three_asset_cycle_cash_envelope(self):
  xs=[normalize_order(make("a",1,"Dutch_V2",A,B,110,100),1,"Dutch_V2"),
      normalize_order(make("b",1,"Dutch_V2",B,C,110,100),1,"Dutch_V2"),
      normalize_order(make("c",1,"Dutch_V2",C,A,110,100),1,"Dutch_V2")]
  self.assertEqual(evaluate(xs)["conservative_envelope_pass_cycle"],1)
 def test_must_be_open_matching_chain(self):
  o=make("z",8453,"Dutch_V3",A,B,100,100)
  self.assertIsNone(normalize_order(o,1,"Dutch_V2"))
  o["orderStatus"]="filled"
  self.assertIsNone(normalize_order(o,8453,"Dutch_V3"))
 def test_wrong_input_decimals_never_use_float(self):
  o=make("big",8453,"Dutch_V3",A,B,10**23,10**20)
  r=normalize_order(o,8453,"Dutch_V3")
  self.assertEqual(r["conservative_input_raw"],10**23)
 def test_source_order_is_predeclared(self):
  self.assertEqual(SOURCES,[(1,'Dutch_V2'),(8453,'Dutch_V3')])
if __name__=="__main__":unittest.main()
