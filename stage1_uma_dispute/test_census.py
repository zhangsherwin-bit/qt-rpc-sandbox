import unittest
from stage1_uma_dispute.census import (
    parse_assertion,COHORTS,CHAINS,query_for,ROWS_PER_QUERY,MAX_POSTS)

def fake(asserter="0x"+"aa"*20,disputer=None,recipient=None,bond="10000000",
         payout=None,resolution=None,settled=None):
 return {"id":"0x"+"01"*32,"assertionId":"0x"+"01"*32,
  "asserter":asserter,"disputer":disputer,"settlementRecipient":recipient,
  "currency":"0x"+"cc"*20,"bond":bond,"settlementPayout":payout,
  "settlementResolution":resolution,"settlementTimestamp":settled,
  "assertionTimestamp":"1780000000","assertionBlockNumber":"24000000",
  "disputeTimestamp":"1780100000" if disputer else None,
  "escalationManager":"0x"+"00"*20}
class TestDispute(unittest.TestCase):
 def test_dispute_winner_raw_cash_is_payout_less_bond(self):
  d="0x"+"bb"*20
  v=parse_assertion(fake(disputer=d,recipient=d,payout="19500000",settled="1780400000",resolution=False))
  self.assertEqual(v["settlement_winner"],"DISPUTER")
  self.assertEqual(v["dispute_realized_raw"],9500000)
 def test_losing_disputer_bond_is_locked_then_forfeited(self):
  a="0x"+"aa"*20;d="0x"+"bb"*20
  v=parse_assertion(fake(disputer=d,recipient=a,payout="19500000",settled="1780400000",resolution=True))
  self.assertEqual(v["dispute_realized_raw"],-10000000)
 def test_unopposed_never_claimed_disputer_income(self):
  v=parse_assertion(fake(recipient="0x"+"aa"*20,payout="10000000",settled="1780400000",resolution=True))
  self.assertEqual(v["settlement_winner"],"UNOPPOSED")
  self.assertIsNone(v["dispute_realized_raw"])
 def test_pending_kept_separate_from_losses(self):
  v=parse_assertion(fake(disputer="0x"+"bb"*20))
  self.assertEqual(v["settlement_winner"],"DISPUTED_NOT_SETTLED")
  self.assertIsNone(v["dispute_realized_raw"])
 def test_fixed_cohort_and_bounded_selection(self):
  self.assertEqual(len(COHORTS),3)
  self.assertEqual(len(CHAINS),4)
  self.assertEqual(ROWS_PER_QUERY,120)
  self.assertEqual(MAX_POSTS,12)
  self.assertIn("assertionTimestamp_gte",query_for(COHORTS[1]))
  self.assertNotIn("where:{",query_for(COHORTS[0]))
if __name__=="__main__":unittest.main()
