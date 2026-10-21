"""Pure offline falsification of n-question neg-risk collateral release.
No market prices or books are claimed to be real by these tests.
"""
import unittest
from decimal import Decimal
from stage1_negrisk.screener import (
  depth_cost,candidate_groups,immediate_cash_bounds,MAX_GAMMA,
  MAX_GROUPS,QUANTITIES,MAX_HTTP)
def leg(ident,yes,no,fees=None):
 return {"conditionId":ident,"question":"Candidate "+ident,
  "negRisk":True,"active":True,"closed":False,
  "enableOrderBook":True,"acceptingOrders":True,
  "outcomes":'["Yes","No"]',"clobTokenIds":'["'+yes+'","'+no+'"]',
  "negRiskFeeBips":fees}
def market(q,ask_price,size):
 return {"question":q,"condition_id":q,"depth":{
   "10":depth_cost({"asks":[{"price":str(ask_price),"size":str(size)}]},Decimal("10")),
   "50":depth_cost({"asks":[{"price":str(ask_price),"size":str(size)}]},Decimal("50"))}}
class EconomicTests(unittest.TestCase):
 def test_depth_is_ask_not_bid_mid(self):
  b={"asks":[{"price":"0.51","size":"3"},{"price":"0.55","size":"10"}],
     "bids":[{"price":"0.01","size":"100"}]}
  got=depth_cost(b,Decimal("10"))
  self.assertEqual(Decimal(got["gross_cost_usdc"]),Decimal("5.33"))
 def test_cross_asset_book_has_no_fictional_fill(self):
  self.assertEqual(depth_cost({"asks":[]},Decimal("10"))["reason"],"INSUFFICIENT_ASK_DEPTH")
 def test_min_order_size_blocks_tiny_illustrations(self):
  self.assertEqual(depth_cost({"min_order_size":"20","asks":[{"price":"0.3","size":"100"}]},
                     Decimal("10"))["reason"],"BELOW_EXCHANGE_MIN_SIZE")
 def test_source_groups_not_cross_event_transfer(self):
  events=[{"id":"1","markets":[leg(str(i),"y"+str(i),"n"+str(i))for i in range(3)]},
          {"id":"2","markets":[leg(str(i+3),"y"+str(i+3),"n"+str(i+3))for i in range(3)]}]
  groups=candidate_groups(events)
  self.assertEqual(len(groups),2)
  self.assertEqual(len(groups[0]["sampled_legs"]),3)
  self.assertNotEqual(groups[0]["sampled_legs"][0]["condition_id"],
                      groups[1]["sampled_legs"][0]["condition_id"])
 def test_unflagged_market_cannot_count_as_convertible(self):
  ms=[leg(str(i),"yes","no")for i in range(3)]
  ms[1]["negRisk"]=False
  self.assertEqual(len(candidate_groups([{"id":"1","markets":ms}])),0)
 def test_two_no_collateral_release_positive_only_if_cost_below_one(self):
  a=market("a","0.35",100);b=market("b","0.50",100)
  results=immediate_cash_bounds([a,b],Decimal("10"))
  self.assertEqual(len(results),1)
  r=results[0]
  self.assertEqual(Decimal(r["protocol_convert_collateral_before_fee_usdc"]),Decimal("10"))
  self.assertEqual(Decimal(r["cost_to_acquire_NO_usdc"]),Decimal("8.50"))
  self.assertEqual(Decimal(r["cash_surplus_before_fees_and_execution_usdc"]),Decimal("1.50"))
  self.assertEqual(r["classification"],"POSITIVE_THEORETICAL_COLLATERAL_BOUND_UNEXECUTED")
  self.assertTrue(r["ONCHAIN_ADAPTER_RIGHTS_AND_FEES_NOT_VERIFIED"])
 def test_no_double_count_unused_yes_or_markets(self):
  a=market("a","0.65",100);b=market("b","0.52",100)
  r=immediate_cash_bounds([a,b],Decimal("10"))[0]
  self.assertEqual(r["yes_positions_residual_value_assumed_usdc"],"0")
  self.assertEqual(r["classification"],"NONPOSITIVE_COLLATERAL_BOUND")
 def test_third_no_leg_changes_collateral_but_not_stale_prices(self):
  arr=[market(str(i),"0.31",100) for i in range(3)]
  possibilities=immediate_cash_bounds(arr,Decimal("10"))
  tri=[r for r in possibilities if r["m"]==3]
  self.assertEqual(len(tri),1)
  self.assertEqual(Decimal(tri[0]["cash_surplus_before_fees_and_execution_usdc"]),Decimal("10.70"))
 def test_bounded_fixed_public_data_only(self):
  self.assertEqual(MAX_GAMMA,2)
  self.assertEqual(MAX_GROUPS,3)
  self.assertEqual([str(q) for q in QUANTITIES],["10","50"])
  self.assertEqual(MAX_HTTP,14)
if __name__=="__main__":unittest.main()
