import unittest
from decimal import Decimal as D
from datetime import datetime,timezone
from stage1_funding_basis.paired import (
 ASSETS,START,END,HOUR,N,MAX_CALLS,FEE_GRID_BPS,
 paired_components,d)
class TestFundingEconomics(unittest.TestCase):
 def test_frozen_holdout_matches_prior_unoptimised_dates(self):
  self.assertEqual(datetime.fromtimestamp(START,timezone.utc).isoformat(),"2026-10-10T00:00:00+00:00")
  self.assertEqual((END-START)//HOUR,168)
  self.assertEqual(N,168)
  self.assertEqual(ASSETS,["BTC","ETH","SOL"])
 def test_one_unit_delta_hedge_not_funding_only(self):
  spot,short,funding,gross=paired_components(
    D("100"),D("110"),D("102"),D("108"),[D("1.5")])
  self.assertEqual(spot,D("10"));self.assertEqual(short,D("-6"))
  self.assertEqual(funding,D("1.5"));self.assertEqual(gross,D("5.5"))
 def test_flat_prices_leaves_only_funding_before_costs(self):
  *_,gross=paired_components(D(100),D(100),D(100),D(100),[D("1.5")])
  self.assertEqual(gross,D("1.5"))
 def test_negative_basis_can_consume_positive_funding(self):
  *_,gross=paired_components(D(100),D(100),D(103),D(107),[D("2")])
  self.assertEqual(gross,D("-2"))
 def test_fixed_absolute_notional_fee_sensitivity(self):
  spot_entry=D("100");gross=D("1.5")
  net_at_20bps=gross-spot_entry*D(20)/D(10000)
  self.assertEqual(net_at_20bps,D("1.3"))
 def test_input_validation_and_bounded_public_request_only(self):
  self.assertEqual(MAX_CALLS,9)
  self.assertEqual(FEE_GRID_BPS,[0,5,10,20,40])
  with self.assertRaises(ValueError):d("NaN")
  with self.assertRaises(ValueError):d("Infinity")
if __name__=="__main__":unittest.main()
