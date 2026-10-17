"""Offline research integrity checks. These do not establish chain profitability."""
import sys,json,pathlib,copy,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from cohort_utils import validate_selection,good_execution,ranked_best
ROOT=pathlib.Path(__file__).resolve().parent

class TestCohort(unittest.TestCase):
    def setUp(self): self.data=json.loads((ROOT/'selection.json').read_text())
    def test_selection_four_distinct_days(self): self.assertEqual(len(validate_selection(self.data)),4)
    def test_previous_selected_excluded(self):
        x=copy.deepcopy(self.data);x['cases'][0]['tx']=x['prior_excluded_txs'][0]
        with self.assertRaises(ValueError):validate_selection(x)
    def test_reject_lp_as_cash(self):
        x=copy.deepcopy(self.data);x['tokens_are_not_cash']=False
        with self.assertRaises(ValueError):validate_selection(x)
    def test_duplicate_days_rejected(self):
        x=copy.deepcopy(self.data);x['cases'][0]['date']=x['cases'][1]['date']
        with self.assertRaises(ValueError):validate_selection(x)
    def test_prefix_failure_never_counts_as_cash(self):
        row={'status':'0x1','environment_verified':True,'prefix_exact_match':False,
             'rows':[{'cash_token':'0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2','net_eth_after_base_fee_wei':'123'}]}
        self.assertFalse(good_execution(row))
    def test_rank_by_retained_value_not_gross(self):
        def sample(c):return {'status':'0x1','environment_verified':True,'prefix_exact_match':True,
            'rows':[{'cash_token':'0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2','net_eth_after_base_fee_wei':str(c)}]}
        self.assertEqual(ranked_best([(1,sample(4)),(2,sample(6))]),2)
    def test_incomplete_execution_stays_unresolved(self):
        self.assertIsNone(ranked_best([(1,{'status':'0x0'}),(2,{'error':'provider refused'})]))
    def test_previous_three_remain_excluded(self):self.assertEqual(len(self.data['prior_excluded_txs']),3)
    def test_reserved_october_3_to_9_untouched(self):
        self.assertTrue(all(x['date']<'2026-10-03' for x in self.data['cases']))
    def test_no_wallet_broadcast_in_runner(self):
        runner=(ROOT/'run_cohort.py').read_text()
        for action in ('eth_sendRawTransaction','eth_sendTransaction','private_key','wallet_seed'):
            self.assertNotIn(action,runner)

if __name__=='__main__':unittest.main()
