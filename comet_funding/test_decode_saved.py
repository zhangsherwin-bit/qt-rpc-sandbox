import unittest,pathlib,sys,copy
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import decode_saved as D
class SavedGuardTests(unittest.TestCase):
    def row(self):return {'blockHash':'old','address':'a','topics':['topic'],'data':'data','logIndex':'0x1'}
    def test_accept_only_enclosing_block_hash(self):
        a=self.row();b={**a,'blockHash':'new'}
        self.assertEqual(D.check_logs([a],[b],'old','new'),1)
    def test_reject_changed_cash_log(self):
        a=self.row();b={**a,'blockHash':'new','data':'changed'}
        with self.assertRaises(ValueError):D.check_logs([a],[b],'old','new')
    def test_reject_changed_order(self):
        a=self.row();b={**a,'logIndex':'0x2','data':'second'}
        with self.assertRaises(ValueError):D.check_logs([a,b],[{**b,'blockHash':'new'},{**a,'blockHash':'new'}],'old','new')
    def test_reject_missing_log(self):
        with self.assertRaises(ValueError):D.check_logs([self.row()],[],'old','new')
    def test_reject_changed_log_identity(self):
        a=self.row();b={**a,'blockHash':'new','address':'other'}
        with self.assertRaises(ValueError):D.check_logs([a],[b],'old','new')
    def test_reject_hash_inconsistent_with_block(self):
        with self.assertRaises(ValueError):D.check_logs([self.row()],[self.row()],'old','new')
    def test_saved_data_resolves_failure_without_more_RPC(self):
        r=D.decode(pathlib.Path('input_cash'),pathlib.Path('input_failed'))
        self.assertEqual(r['best_quote']['funding_cost_USDC_raw'],'411702771')
        self.assertEqual(r['best_quote']['remaining_before_network_costs_raw'],'-6364398')
        self.assertFalse(r['actual_producer_payment_executed'])
if __name__=='__main__':unittest.main()
