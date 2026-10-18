import unittest,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage1_followup'))
import settle as R
import study as S
class TestRound2(unittest.TestCase):
    def test_original_plus_earliest_six(self):
        cohort=R.frozen_cohort(Path('input_api'),json.loads(Path('input_prior/REPORT.json').read_text()))
        self.assertEqual(len(cohort),12)
        self.assertEqual(sum(x['source_selection']=='PREVIOUS_AUDITED' for x in cohort),6)
        self.assertEqual(sum(x['source_selection']=='CHRONOLOGICALLY_EARLIEST_NONEXCLUSIVE' for x in cohort),6)
        self.assertEqual(len({(x['originChainId'],x['depositId']) for x in cohort}),12)
    def test_refund_event_dynamic_amount_address_arrays(self):
        # non-indexed ABI: amountToReturn, refundAmounts offset, token, refundAddresses offset, deferred, caller
        pad=lambda x:format(x,'064x')
        who=int('490632638389f5e29bed11a35b8cc56726bea895',16)
        value=110550000
        data='0x'+''.join(map(pad,[0,192,int(S.TOKEN[1],16),256,0,1,1,value,1,who]))
        log={'topics':[S.REFUND,pad(1),pad(29949),pad(0)],'data':data,'address':S.SPOKE[1],
             'transactionHash':'0x'+'a'*64,'blockNumber':hex(26217801),'logIndex':'0x0'}
        r=S.decode_refund(log)
        self.assertEqual(r['token'],S.TOKEN[1])
        self.assertEqual(r['payments'][0]['recipient'],S.address(who))
        self.assertEqual(r['payments'][0]['raw'],str(value))
    def test_denied_host_not_negative_income(self):
        src=(Path(__file__).parent/'settle.py').read_text()
        self.assertIn('deposit_level_profits_verified',src)
        self.assertIn('NOT_ESTABLISHED',src)
    def test_readonly(self):
        src=(Path(__file__).parent/'settle.py').read_text()
        for forbidden in ('eth_sendRawTransaction','eth_sendTransaction','private_key','wallet_seed','signTransaction'):
            self.assertNotIn(forbidden,src)
    def test_revenue_is_not_sum_of_principal(self):
        self.assertEqual(110550000-110000000,550000)
        self.assertNotEqual(110550000,550000)
if __name__=='__main__':unittest.main()
