import unittest,pathlib,json,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import logic as L
class Controls(unittest.TestCase):
    def source(self):
        for p in [pathlib.Path('comet_flash/CometCashProbe.sol'), pathlib.Path(__file__).parents[2]/'inputs/qt-comet-actual-usdc-payout/source/CometCashProbe.sol']:
            if p.exists():return p.read_text()
        raise AssertionError('Missing exact original research source')
    def test_adds_only_one_frozen_absorb(self):
        s=L.add_absorption(self.source());self.assertEqual(s.count('IComet(COMET).absorb('),1)
        self.assertIn('frozen borrower not eligible',s)
    def test_precedes_financing(self):
        s=L.add_absorption(self.source());self.assertLess(s.index('IComet(COMET).absorb('),s.index('IAavePool(AAVE).flashLoanSimple('))
    def test_reject_changed_source(self):
        with self.assertRaises(ValueError):L.add_absorption(self.source()+' ')
    def test_source_not_repatchable(self):
        with self.assertRaises(ValueError):L.add_absorption(L.add_absorption(self.source()))
    def test_original_repayment_and_caller_guards_retained(self):
        s=L.add_absorption(self.source())
        for term in ['msg.sender==AAVE','initiator==address(this)','amount+premium','unconverted WETH','cash payout mismatched']:
            self.assertIn(term,s)
    def test_preserve_blob_fields(self):
        tx={'from':'a','to':'b','input':'0x','gas':'0x123','maxFeePerGas':'0x2','gasPrice':'0x1','blobVersionedHashes':['h'],'maxFeePerBlobGas':'0x5'}
        x=L.as_call(tx);self.assertEqual(x['blobVersionedHashes'],['h']);self.assertNotIn('gasPrice',x)
    def test_legacy_gasprice(self):self.assertEqual(L.as_call({'gasPrice':'0x7'})['gasPrice'],'0x7')
    def test_reverted_cash_is_not_income(self):
        x={'type':'CALL','from':'a','to':'b','value':'0x10','error':'reverted','calls':[{'type':'CALL','to':'b','value':'0x10'}]}
        self.assertEqual(L.native_delta(x,'b'),0)
    def test_delegatecall_value_not_double_counted(self):
        x={'type':'CALL','from':'a','to':'b','value':'0x10','calls':[{'type':'DELEGATECALL','from':'a','to':'b','value':'0x10'}]}
        self.assertEqual(L.native_delta(x,'b'),16)
    def test_receipt_gas_mismatch_rejected(self):
        self.assertFalse(L.receipt_matches({'status':'0x1','gasUsed':'0x2','logs':[]},{'status':'0x1','gasUsed':'0x3','logs':[]}))
    def test_complete_log_multiset(self):
        l={'address':'0x11','topics':['0x22'],'data':'0x00'}
        self.assertNotEqual(L.bag([l]),L.bag([l,l]))
    def test_revert_log_removed(self):self.assertEqual(L.committed_logs({'error':'reverted','logs':[{}]}),[])
if __name__=='__main__':unittest.main()
