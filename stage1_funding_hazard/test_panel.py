import unittest
from decimal import Decimal
from datetime import datetime,timezone
from stage1_funding_hazard.panel import (
 COINS,WINDOWS,MAX_REQUESTS,millis,funding_rows,analyse,markov_assessment)
class TestFundingEvidence(unittest.TestCase):
 def test_frozen_source_and_calendar(self):
  self.assertEqual(COINS,["BTC","ETH","SOL"])
  self.assertEqual(MAX_REQUESTS,6)
  self.assertEqual(len(WINDOWS),2)
  for _,a,b in WINDOWS:
   self.assertEqual(millis(b)-millis(a),168*3600000)
 def test_only_rate_history_not_real_trading_cash(self):
  start=millis(WINDOWS[0][1]);end=millis(WINDOWS[0][2])
  rows=[{"time":start+3600000*h,"fundingRate":"0.00001"}for h in range(168)]
  result=analyse(rows,start,end)
  self.assertTrue(result["complete"])
  self.assertEqual(Decimal(result["sum_of_rates_short_perp_percent_of_notional"]),
                   Decimal("0.16800"))
 def test_duplicate_hour_must_mark_incomplete(self):
  a,b=millis(WINDOWS[0][1]),millis(WINDOWS[0][2])
  rows=[{"time":a,"fundingRate":"0.00001"},{"time":a,"fundingRate":"0.00009"}]
  got=analyse(rows,a,b)
  self.assertFalse(got["complete"])
  self.assertEqual(got["data"]["duplicates"],1)
 def test_cannot_treat_missing_time_as_zero_funding(self):
  a,b=millis(WINDOWS[0][1]),millis(WINDOWS[0][2])
  rows=[{"time":a,"fundingRate":"0.00003"}]
  got=analyse(rows,a,b)
  self.assertEqual(got["observed_hours"],1)
  self.assertFalse(got["complete"])
 def test_markov_vs_baseline_separate_and_forward(self):
  a=millis(WINDOWS[0][1]);b=millis(WINDOWS[1][1])
  train={a//3600000+i:Decimal("0.00001") if i%2==0 else Decimal("-0.00001")
         for i in range(168)}
  held={b//3600000+i:Decimal("0.00001") if i%2==0 else Decimal("-0.00001")
        for i in range(168)}
  x=markov_assessment(train,held,a,b)
  self.assertLess(x["markov_holdout_logloss"],x["baseline_holdout_logloss"])
  self.assertTrue(x["FUNDING_SUM_IS_NOT_TRADING_PNL"])
 def test_rate_outliers_do_not_become_fictitious_profit(self):
  a,b=millis(WINDOWS[0][1]),millis(WINDOWS[0][2])
  sample=[{"time":a,"fundingRate":"NaN"},{"time":a+3600000,"fundingRate":"3.0"}]
  x=analyse(sample,a,b)
  self.assertEqual(x["data"]["invalid"],2)
  self.assertFalse(x["complete"])
if __name__=="__main__":unittest.main()
