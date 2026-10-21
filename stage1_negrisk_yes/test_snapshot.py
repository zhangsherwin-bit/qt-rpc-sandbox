import unittest
from decimal import Decimal as D
from stage1_negrisk_yes.snapshot import (LEGS,SIZES,MAX_HTTP,quote,settlement)
def b(ask,bid,size="100"):
 return {"asks":[{"price":str(ask),"size":size}],
         "bids":[{"price":str(bid),"size":size}],
         "min_order_size":"5"}
class TestLogicalCash(unittest.TestCase):
 def test_competing_books_must_pay_ask_to_buy_no_and_receive_bid_to_sell_yes(self):
  v=b("0.7","0.3")
  self.assertEqual(quote(v,"buy",D(10))["cash_usdc"],"7.0")
  self.assertEqual(quote(v,"sell",D(10))["cash_usdc"],"3.0")
 def test_complementary_yes_bid_can_rescue_negative_no_only(self):
  asks=[quote(b(".7",".2"),"buy",D(10))]*3
  bids=[quote(b(".8",".5"),"sell",D(10))]*3
  x=settlement(asks,bids,D(10),(0,1))
  self.assertEqual(x["no_ask_cost_usdc"],"14.0")
  self.assertEqual(x["collateral_release_usdc"],"10")
  self.assertEqual(x["residual_yes_real_book_bid_usdc"],"5.0")
  self.assertEqual(x["cash_before_conversion_fee_and_trading_cost"],"1.0")
  self.assertEqual(x["classification"],"POSITIVE_CONDITIONAL_BOOK_BOUND")
  self.assertTrue(x["not_proof_of_same_onchain_negrisk_market"])
 def test_all_no_has_no_residual_yes_to_sell(self):
  asks=[quote(b(".7",".5"),"buy",D(10))]*3
  bids=[quote(b(".8",".5"),"sell",D(10))]*3
  x=settlement(asks,bids,D(10),(0,1,2))
  self.assertEqual(x["residual_yes_indices"],[])
  self.assertEqual(x["residual_yes_real_book_bid_usdc"],"0")
  self.assertEqual(x["classification"],"NONPOSITIVE_CONDITIONAL_BOOK_BOUND")
 def test_no_ask_depth_missing_is_not_zero_cost(self):
  asks=[quote({"asks":[]},'buy',D(10))]*3
  bids=[quote(b(".8",".5"),"sell",D(10))]*3
  self.assertEqual(settlement(asks,bids,D(10),(0,1))["classification"],"NOT_FILLABLE_NO_DEPTH")
 def test_yes_bid_depth_missing_does_not_assume_free_sale(self):
  asks=[quote(b(".7",".5"),"buy",D(10))]*3
  bids=[quote({"bids":[]},'sell',D(10))]*3
  self.assertEqual(settlement(asks,bids,D(10),(0,1))["classification"],"NOT_FILLABLE_YES_BID_DEPTH")
 def test_source_is_one_three_question_event_fixed(self):
  self.assertEqual(len(LEGS),3)
  self.assertEqual(SIZES,[D(10),D(50)])
  self.assertEqual(MAX_HTTP,6)
if __name__=="__main__":unittest.main()
