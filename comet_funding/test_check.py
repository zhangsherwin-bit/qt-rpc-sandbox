import unittest,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import check as C
class FundingTests(unittest.TestCase):
    def test_source_exact_success(self):
        request,calls=C.find_case();self.assertEqual(len(calls),5);self.assertEqual(C.uints(calls[3]['returnData']),[405338373])
    def test_quote_tuple_encoding(self):
        x=C.quote_data(174449845338543024,500);self.assertEqual(len(x),330);self.assertEqual(x[:10],'0xbd21704a')
        values=C.uints('0x'+x[10:]);self.assertEqual(values[2],174449845338543024);self.assertEqual(values[3],500)
    def test_cost_exceeds_cash(self):
        r=C.economic_comparison(405338373,411000000);self.assertFalse(r['covers_observed_payment_before_gas']);self.assertEqual(r['remaining_before_network_costs_raw'],'-5661627')
    def test_compare_before_gas_not_final_profit(self):
        self.assertNotIn('profit',C.economic_comparison(100,90))
    def test_reject_bad_ABI(self):
        with self.assertRaises(ValueError):C.uints('0xab')
    def test_four_distinct_fee_tiers(self):self.assertEqual(len(set(C.FEES)),4)
if __name__=='__main__':unittest.main()
