"""Offline checks of the frozen observation sample and reward accounting."""
import json,pathlib,unittest
import replicate as R

ROOT=pathlib.Path(__file__).resolve().parents[1]
EXPECTED={
 '2026-09-16':'0x15534588816de3dab27ea8999c3fd107aeeae1d6fcd3a521c079fc0eb34c54a9',
 '2026-09-18':'0x9e6953eccc7e9d7dfff408a8eb96535ea55d0e4a34de4968074f0ad50c093e49',
 '2026-09-21':'0x1ddfb99ea1354998f5f471fb8b646a495aac8e94e18aeb040cf32663d642a705',
 '2026-09-29':'0xc615763bfddfda7c77b882442233e907dbb40503f1792eb341a279bd8d2fb634',
 '2026-09-30':'0x94b2aa0a54d69a2c2ff92dedbda32d2e3b68ae8607a37bbe878e2d40e36ad3cc',
}
class CorpusChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.events=json.loads((ROOT/'input_census/keeper_events.json').read_text())
  cls.receipts=json.loads((ROOT/'input_census/SERVICE_RECEIPTS.json').read_text())
  cls.winners=R.freeze(cls.events,cls.receipts,R.C.KEEPERS[1])
 def test_source_integrity(self):
  self.assertEqual(len(self.events),100);self.assertEqual(len(self.receipts),100)
 def test_exact_fixed_dates_and_hashes(self):
  self.assertEqual({R.day(x):x['transactionHash'] for x in self.winners},EXPECTED)
 def test_no_reuse_of_pr29_control_transactions(self):
  self.assertTrue(all(x['transactionHash'] not in R.BASELINES for x in self.winners))
 def test_small_prefix_positions(self):
  self.assertTrue(all(int(x['transactionIndex'],16)<=10 for x in self.winners))
 def test_rewards_are_token_transfers_not_keeper_operation_values(self):
  for x in self.winners:
   self.assertGreater(x['_reward'],0)
   self.assertNotEqual(x['_reward'],int(x['data'],16))
 def test_burn_not_a_caller_reward(self):
  first=next(x for x in self.receipts if x['transactionHash']=='0xfd7779247099a7ced3a6480dafd06d3fdf3846b310f30fbfbc82c892cddb0d03')
  self.assertEqual(R.reward(first,R.C.KEEPERS[1]),41106263736922787)
 def test_no_duplicate_issuer_or_receipt(self):
  self.assertEqual(len({x['transactionHash'] for x in self.events}),100)
  self.assertEqual(len({x['transactionHash'] for x in self.receipts}),100)
 def test_unsupported_positive_claim_disallowed(self):
  self.assertIsNone(R.net_cash({'status':'0x0','rows':[]}))
  self.assertIsNone(R.net_cash({'status':'0x1','rows':[]}))
 def test_cash_after_gas_is_not_gross(self):
  self.assertEqual(R.net_cash({'status':'0x1','rows':[{'net_eth_after_base_fee_wei':'-21'}]}),-21)
 def test_no_historical_payload_rewriting(self):
  self.assertEqual(len(R.DAYS),5)
  self.assertTrue(all(R.day(x) in R.DAYS for x in self.winners))
if __name__=='__main__':unittest.main()
