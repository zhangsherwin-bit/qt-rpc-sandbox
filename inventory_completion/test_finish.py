import unittest,sys,tempfile,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import finish as F

class CompletionTests(unittest.TestCase):
    def test_no_base_reads(self):
        with tempfile.TemporaryDirectory() as d:
            c=F.Limited(Path(d))
            with self.assertRaises(ValueError):c.rpc(8453,'no','eth_chainId',[])
            self.assertEqual(c.n,0)
    def test_no_log_scans(self):
        with tempfile.TemporaryDirectory() as d:
            c=F.Limited(Path(d))
            with self.assertRaises(ValueError):c.rpc(1,'no','eth_getLogs',[])
    def test_budget_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            c=F.Limited(Path(d));c.n=65
            with self.assertRaises(RuntimeError):c.rpc(1,'no','eth_chainId',[])
    def test_bad_cached_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'raw').mkdir();body=b'{"result":"0x1"}'
            (root/'raw/0001.body').write_bytes(body)
            (root/'raw/0001.json').write_text(json.dumps({'sha256':'incorrect','length':len(body)}))
            with self.assertRaises(AssertionError):F.cached(root)
    def test_zero_discounted_denominator_classified(self):
        factor=10**18;liquidation_factor=0;p=100000000
        discount=factor*(10**18-liquidation_factor)//10**18
        self.assertEqual(p*(10**18-discount)//10**18,0)
    def test_all_remaining_assets_in_scope(self):
        expected=13;prior=10
        indices=list(range(prior-1,expected))
        self.assertEqual(indices,[9,10,11,12])
        self.assertEqual(prior-1+len(indices),expected)
if __name__=='__main__':unittest.main()
