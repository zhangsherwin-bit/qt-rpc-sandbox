"""Read-only causal chronology of one apparently matching Across refund leaf.
Tests whether the root could even contain the deposit, NOT profitability or attribution.
"""
import json,sys,traceback,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage1_followup'))
import study as S
OUT=Path('chronology_evidence');OUT.mkdir(exist_ok=True)
SPOKE=S.SPOKE[1];HUB='0xc186fa914353c44b2e33ebe05f21846f1048beda'
RELAY='0xc86ba04c55bc5eb2f2876b91c438849a296dbec7b08751c3074d92e04f0a77af'
PROPOSE='0x3185fa6fac8e91dc65e7424a8081c73353151d2715bddb71db0982c1fe4c0fd4'
DEPOSIT_BLOCK=26217472;REFUND_BLOCK=26217801;ROOT_ID=29949
REFUND_TX='0x66671a695ed305d93d765e7fda246e465c16581305920cfde5e09e42c7d8a30b'
REPAYMENT_ADDRESS='0x490632638389f5e29bed11a35b8cc56726bea895'
REFUND_AMOUNT_RAW=110550000
def save(d):S.write(OUT,'REPORT.json',d)
def stamp(x):return datetime.datetime.fromtimestamp(int(x,16),datetime.timezone.utc).isoformat()
def main():
    r={'scope':'Chronology of Across refund leaf 29949 vs deposit 4791754',
       'no_signing_or_trading':True,'deposit_block':DEPOSIT_BLOCK,
       'refund_block':REFUND_BLOCK,'root_id':ROOT_ID,
       'deposit_level_refund_attribution_proven':False}
    c=S.Client(OUT);save(r)
    try:
        assert int(c.rpc(1,'verify_ethereum','eth_chainId',[]),16)==1
        dep=c.rpc(1,'deposit_header','eth_getBlockByNumber',[hex(DEPOSIT_BLOCK),False])
        refund=c.rpc(1,'refund_header','eth_getBlockByNumber',[hex(REFUND_BLOCK),False])
        r['deposit_timestamp_utc']=stamp(dep['timestamp'])
        r['refund_timestamp_utc']=stamp(refund['timestamp'])
        r['seconds_between_deposit_and_payment']=int(refund['timestamp'],16)-int(dep['timestamp'],16)
        val=c.rpc(1,'liveness','eth_call',[{'to':HUB,'data':'0x6ad0690a'},hex(DEPOSIT_BLOCK)])
        r['hub_liveness_seconds_at_deposit']=int(val,16)
        r['post_deposit_duration_is_less_than_liveness']=r['seconds_between_deposit_and_payment']<r['hub_liveness_seconds_at_deposit']
        relayed=c.rpc(1,'look_for_root_relay','eth_getLogs',[{'address':SPOKE,'fromBlock':hex(26208000),
           'toBlock':hex(REFUND_BLOCK),'topics':[RELAY,'0x'+format(ROOT_ID,'064x')]}])
        r['relayed_root_events']=[{'block':int(e['blockNumber'],16),'tx':e['transactionHash'],
              'relayer_refund_root':e['topics'][2],
              'slow_relay_root':e['data']} for e in relayed]
        for x in r['relayed_root_events']:
            if x['block']>REFUND_BLOCK:raise ValueError('root relayed after refund')
            proposal=c.rpc(1,'root_proposal_current','eth_getLogs',[{'address':HUB,'fromBlock':hex(26210000),
               'toBlock':hex(REFUND_BLOCK),'topics':[PROPOSE,None,x['relayer_refund_root']]}])
            if not proposal:
                proposal=c.rpc(1,'root_proposal_previous','eth_getLogs',[{'address':HUB,'fromBlock':hex(26200000),
                    'toBlock':hex(26209999),'topics':[PROPOSE,None,x['relayer_refund_root']]}])
            x['proposal_events']=[{'block':int(e['blockNumber'],16),'tx':e['transactionHash']} for e in proposal]
            x['proposal_predates_deposit']=bool(proposal) and all(int(e['blockNumber'],16)<DEPOSIT_BLOCK for e in proposal)
        rec=c.rpc(1,'actual_refund_receipt','eth_getTransactionReceipt',[REFUND_TX])
        assert rec['status']=='0x1' and int(rec['blockNumber'],16)==REFUND_BLOCK
        leaves=[S.decode_refund(e) for e in rec['logs'] if e.get('topics') and e['topics'][0].lower() in (S.REFUND,S.LEGACY_REFUND)]
        matches=[(leaf,p) for leaf in leaves for p in leaf['payments'] if leaf['root_bundle_id']==ROOT_ID
                and leaf['token']==S.TOKEN[1] and p['recipient']==REPAYMENT_ADDRESS]
        r['matching_aggregate_payment']=[{'amount_raw':p['raw'],'leaf':leaf['leaf_id']} for leaf,p in matches]
        r['matches_11055_exactly']=len(matches)==1 and int(matches[0][1]['raw'])==REFUND_AMOUNT_RAW
        r['receipt_delivery_checks']=S.refund_receipt_check(rec,{(leaf['spoke'],leaf['token'],p['recipient']) for leaf,p in matches})
        r['no_deposit_level_profit_claim']=True
    except Exception as exc:r['error']=repr(exc);r['traceback']=traceback.format_exc()
    r['requests']=c.n;r['denied_chain']=sorted(c.denied)
    save(r)
    print(json.dumps({k:v for k,v in r.items() if k not in ('traceback','relayed_root_events')},indent=2),flush=True)
    if r.get('error'):raise SystemExit('Chronology incomplete; raw evidence saved')
if __name__=='__main__':main()
