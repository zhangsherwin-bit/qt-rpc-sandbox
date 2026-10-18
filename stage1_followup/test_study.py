import unittest,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import study as S

def abi(w):return '0x'+''.join(S.enc(x) for x in w)
def refund(amount=50,deferred=False):
    a='0x'+'12'*20;t=S.TOKEN[1];sp=S.SPOKE[1]
    return {'topics':[S.REFUND,S.enc(1),S.enc(2),S.enc(3)],'data':abi([0,192,int(t,16),256,int(deferred),1,1,amount,1,int(a,16)]),'address':sp,'transactionHash':'0x'+'ff'*32,'blockNumber':'0x123','logIndex':'0x1'}

class AuditTests(unittest.TestCase):
    def test_keccak_empty(self):self.assertEqual(S.topic(''),'0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470')
    def test_transfer_selector(self):self.assertEqual(S.selector('balanceOf(address)'),'0x70a08231')
    def test_filled_relay_topic(self):self.assertEqual(S.FILL,'0x44b559f101f8fbcc8a0ea43fa91a05a729a5ea6e14a7c75aa750374690137208')
    def test_signed_reserves(self):self.assertEqual(S.scalar(abi([2**256-123]),True),-123)
    def test_unsigned_reserves(self):self.assertEqual(S.scalar(abi([5])),5)
    def test_reject_bad_words(self):
        for bad in ('0x1',None,'0xyz'):
            with self.assertRaises(ValueError):S.words(bad)
    def test_reject_non_evm_address(self):
        with self.assertRaises(ValueError):S.address(2**160)
    def test_decode_refund(self):
        r=S.decode_refund(refund());self.assertEqual(r['payments'],[{'recipient':'0x'+'12'*20,'raw':'50'}]);self.assertFalse(r['deferred'])
    def test_deferred_not_cash(self):
        r=refund(deferred=True);t={(S.SPOKE[1],S.TOKEN[1],'0x'+'12'*20)}
        x=S.refund_receipt_check({'logs':[r]},t)[0];self.assertFalse(x['equal']);self.assertEqual(x['expected_raw'],'0')
    def test_transfer_verified(self):
        r=refund();a='0x'+'12'*20;t={(S.SPOKE[1],S.TOKEN[1],a)}
        transfer={'topics':[S.TRANSFER,'0x'+S.enc(S.SPOKE[1]),'0x'+S.enc(a)],'data':abi([50]),'address':S.TOKEN[1]}
        self.assertTrue(S.refund_receipt_check({'logs':[r,transfer]},t)[0]['equal'])
    def test_extra_transfer_does_not_become_profit(self):
        r=refund();a='0x'+'12'*20;t={(S.SPOKE[1],S.TOKEN[1],a)}
        transfer={'topics':[S.TRANSFER,'0x'+S.enc(S.SPOKE[1]),'0x'+S.enc(a)],'data':abi([100]),'address':S.TOKEN[1]}
        self.assertFalse(S.refund_receipt_check({'logs':[r,transfer]},t)[0]['equal'])
    def test_bad_offsets(self):
        r=refund();w=S.words(r['data']);w[1]=1;r['data']=abi(w)
        with self.assertRaises(ValueError):S.decode_refund(r)
    def test_source_chain_and_repayment_not_assumed_equal(self):
        w=[int(S.TOKEN[1],16),int(S.TOKEN[8453],16),100,99,42161,10000,9000,0,1,2,0,3,0,98,0]
        log={'topics':[S.FILL,'0x'+S.enc(1),'0x'+S.enc(999),'0x'+S.enc(7)],'data':abi(w),'address':S.SPOKE[8453],'transactionHash':'0x'+'11'*32,'blockNumber':'0x1'}
        r=S.decode_fill(log);self.assertEqual(r['repayment_chain'],42161);self.assertEqual(r['updated_output_raw'],'98');self.assertEqual(r['recipient'],S.address(2));self.assertEqual(r['updated_recipient'],S.address(3))
    def test_unapproved_method_stops_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            c=S.Client(Path(d))
            with self.assertRaises(ValueError):c.rpc(1,'bad','eth_sendRawTransaction',[])
            self.assertEqual(c.n,0)
    def test_unbounded_log_range_stops(self):
        with tempfile.TemporaryDirectory() as d:
            c=S.Client(Path(d))
            with self.assertRaises(ValueError):c.rpc(1,'bad','eth_getLogs',[{'address':S.SPOKE[1],'fromBlock':'0x0','toBlock':hex(10000)}])
    def test_request_budget(self):
        with tempfile.TemporaryDirectory() as d:
            c=S.Client(Path(d));c.n=240
            with self.assertRaises(RuntimeError):c.rpc(1,'limit','eth_chainId',[])
    def test_denied_provider_no_retry(self):
        with tempfile.TemporaryDirectory() as d:
            c=S.Client(Path(d));c.denied.add(8453)
            with self.assertRaises(RuntimeError):c.rpc(8453,'limit','eth_chainId',[])
    def test_no_execution_methods_in_allowlist(self):self.assertEqual(S.ALLOWED,{'eth_chainId','eth_blockNumber','eth_getBlockByNumber','eth_getCode','eth_getLogs','eth_call','eth_getTransactionReceipt'})
if __name__=='__main__':unittest.main()
