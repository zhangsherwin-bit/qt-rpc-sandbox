"""Across Stage1 Round2. Bounded public reads, no transaction submission.
Compare six previously audited fills with six older earliest eligible USDC fills.
Aggregate refund leaves are NOT proof of a deposit's individual repayment.
"""
import collections,datetime as dt,hashlib,json,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage1_followup'))
import study as S
OUT=Path('round2_evidence');OUT.mkdir(exist_ok=True)
def save(x):S.write(OUT,'REPORT.json',x)
def frozen_cohort(inp,prior):
    prev={(x['origin'],x['deposit_id']):x for x in prior['across']['cases']}
    if len(prev)!=6:raise ValueError("Missing the six original complete receipts")
    cohort=[]
    for chain,dest in [(1,8453),(8453,1)]:
        arr=json.loads((inp/f'across/{chain}_{dest}_deposits.json').read_text())
        valid=[]
        for r in arr:
            if r.get('status')!='filled' or not all(r.get(z) for z in ('depositId','fillTx','relayHash','relayer','fillBlockTimestamp','depositBlockTimestamp')):continue
            if r.get('inputToken','').lower()!=S.TOKEN[chain] or r.get('outputToken','').lower()!=S.TOKEN[dest]:continue
            end=r.get('exclusivityDeadline')
            if end and end>=r['fillBlockTimestamp']:continue
            valid.append(r)
        valid.sort(key=lambda z:(z['depositBlockTimestamp'],str(z['depositId'])))
        orig={k[1] for k in prev if k[0]==chain}
        selected=valid[:3]+[r for r in arr if str(r.get('depositId')) in orig]
        if len(selected)!=6:raise ValueError("Incomplete frozen six+six cohort")
        for r in selected:
            x={k:r.get(k) for k in ('depositId','originChainId','destinationChainId','depositBlockNumber','depositBlockTimestamp','fillBlockTimestamp','inputAmount','outputAmount','fillTx','depositTxHash','relayer','relayHash')}
            x['source_selection']='PREVIOUS_AUDITED' if str(r['depositId']) in orig else 'CHRONOLOGICALLY_EARLIEST_NONEXCLUSIVE'
            old=prev.get((chain,str(r['depositId'])))
            if old and old.get('fill'):
                x['fill']=old['fill'];x['canonical_receipt_reused']=True
                x['tx_gas_wei']=str(int(old['transaction_gas_wei'])+int(old.get('transaction_l1_fee_wei','0')))
                x['tx_gas_payer']=old['fill_sender'];x['fills_in_same_tx']=old['fill_tx_event_count']
            x['conditional_max_user_fee_raw']=str(int(r['inputAmount'])-int(r['outputAmount']))
            x['individual_refund_proven']=False
            cohort.append(x)
    if len(cohort)!=12 or len({(x['originChainId'],str(x['depositId'])) for x in cohort})!=12:raise ValueError("Duplicate selection")
    return cohort

def canonical_new_receipts(c,report):
    for x in report['cases']:
        if x.get('fill'):continue
        try:
            rec=c.rpc(x['destinationChainId'],'new_older_fill','eth_getTransactionReceipt',[x['fillTx']])
            if not rec or rec['status']!='0x1':raise ValueError('No successful canonical fill')
            events=[S.decode_fill(l) for l in rec['logs'] if l.get('topics') and l['topics'][0].lower()==S.FILL]
            matches=[e for e in events if e['origin']==x['originChainId'] and e['deposit_id']==str(x['depositId'])]
            if len(matches)!=1:raise ValueError('Missing or ambiguous fill event')
            e=matches[0]
            if e['spoke']!=S.SPOKE[x['destinationChainId']] or int(e['input_raw'])!=int(x['inputAmount']) or int(e['updated_output_raw'])!=int(x['outputAmount']):
                raise ValueError('Mismatch with frozen public order')
            x['fill']=e;x['canonical_receipt_now']=True
            x['tx_gas_payer']=rec['from'].lower()
            x['tx_gas_wei']=str(int(rec['gasUsed'],16)*int(rec['effectiveGasPrice'],16)+int(rec.get('l1Fee','0x0'),16))
            x['fills_in_same_tx']=len(events)
        except Exception as e:x['receipt_error']=repr(e)
        save(report)
        if x['destinationChainId'] in c.denied:break

def scan(c,chain,report,prior):
    rows=[x for x in report['cases'] if x['originChainId']==chain]
    earliest=min(int(x['depositBlockNumber']) for x in rows)
    h=c.rpc(chain,'current_pin','eth_getBlockByNumber',['latest',False]);top=int(h['number'],16)
    stat={'from_block':earliest,'to_block':top,'end_hash':h['hash'],'pages':[],'complete':False,'errors':[]}
    report['chains'][str(chain)]=stat;save(report)
    old=[x for x in prior['across'].get('refund_events',[]) if x['chain']==chain and x['spoke']==S.SPOKE[chain]]
    window=next((x for x in prior['across'].get('windows',[]) if x['chain']==chain),None)
    prior_errors=[x for x in prior['across'].get('errors',[]) if x['chain']==chain]
    if chain==1 and window and not prior_errors:
        intervals=[(earliest,window['from_block']-1),(window['through_block']+1,top)]
        obs=list(old)
        stat['previously_audited_event_count']=len(old)
    else:intervals=[(earliest,top)];obs=[]
    for left,right in intervals:
        for lo in range(left,right+1,9500):
            hi=min(right,lo+9499)
            try:
                logs=c.rpc(chain,'new_refund_leaf_page','eth_getLogs',[{'address':S.SPOKE[chain],
                    'fromBlock':hex(lo),'toBlock':hex(hi),'topics':[[S.REFUND,S.LEGACY_REFUND]]}])
                out=[S.decode_refund(x) for x in logs]
                obs.extend(x for x in out if x)
                stat['pages'].append({'lo':lo,'hi':hi,'events':len(logs)})
            except Exception as exc:
                stat['errors'].append(repr(exc));save(report);return obs
    stat['complete']=not stat['errors'] and bool(stat['pages']) and stat['pages'][-1]['hi']==top
    save(report);return obs

def associate(c,chain,obs,report,prior):
    cases=[x for x in report['cases'] if x['originChainId']==chain and x.get('fill') and x['fill']['repayment_chain']==chain]
    valid={x['fill']['repayment_address'] for x in cases}
    targets=[e for e in obs if e['token']==S.TOKEN[chain] and any(z['recipient'] in valid for z in e['payments'])]
    verified_old={v['tx'] for v in prior['across'].get('verified_receipt_payments',[]) if v['chain']==chain and v.get('status')=='0x1' and all(p['equal'] for p in v['payments'])}
    verified={tx:'CACHED_RECEIPT_CHECKED' for tx in verified_old}
    txs=list(dict.fromkeys(e['tx'] for e in targets))
    for tx in txs:
        if tx in verified:continue
        if sum(s=='NEW_RECEIPT_CHECKED' for s in verified.values())>=10:break
        try:
            receipt=c.rpc(chain,'new_aggregate_refund_receipt','eth_getTransactionReceipt',[tx])
            expected={(e['spoke'],e['token'],p['recipient']) for e in targets if e['tx']==tx and not e['deferred'] for p in e['payments'] if p['recipient'] in valid}
            checks=S.refund_receipt_check(receipt,expected)
            verified[tx]='NEW_RECEIPT_CHECKED' if receipt and receipt['status']=='0x1' and checks and all(v['equal'] for v in checks) else 'NOT_CONFIRMED'
            report['receipt_checks'].append({'tx':tx,'chain':chain,'result':verified[tx],'checks':checks})
        except Exception as exc:verified[tx]='ERROR '+str(exc)[:150]
        save(report)
        if chain in c.denied:break
    for x in cases:
        matches=[]
        for e in targets:
            if e['block']<int(x['depositBlockNumber']):continue
            for p in e['payments']:
                if p['recipient']==x['fill']['repayment_address']:
                    matches.append({'tx':e['tx'],'block':e['block'],'amount_raw':p['raw'],
                        'root':e['root_bundle_id'],'leaf':e['leaf_id'],'deferred':e['deferred'],
                        'exact_input_amount_match':int(p['raw'])==int(x['inputAmount']),
                        'aggregate_transfer_check':verified.get(e['tx'],'NOT_TESTED')})
        x['candidate_aggregate_refunds_after_deposit']=matches
        x['refund_membership_of_this_specific_deposit']='NOT_ESTABLISHED'
        x['deposit_attributed_cash_profit']='NOT_ESTABLISHED'
    stat=report['chains'][str(chain)]
    stat['candidate_refund_leaves']=len(targets)
    stat['aggregate_refund_receipts_verified']=len({tx for tx in txs if verified.get(tx) in ('CACHED_RECEIPT_CHECKED','NEW_RECEIPT_CHECKED')})
    save(report)

def main():
    report={'scope':'Stage1 read-only Across second round: old six + 3 earliest non-exclusive USDC on each origin chain',
      'no_execution_or_signatures':True,'operator_income_proven':False,
      'warning':'Aggregate repayment to a relayer is NOT attributable to a single fill unless the entire bundle membership is reconstructed',
      'cases':[],'chains':{},'receipt_checks':[],'errors':[]}
    save(report);c=S.Client(OUT)
    try:
        prior=json.loads(Path('input_prior/REPORT.json').read_text())
        report['cases']=frozen_cohort(Path('input_api'),prior)
        report['selection_sha256']=hashlib.sha256(json.dumps(report['cases'],sort_keys=True).encode()).hexdigest()
        save(report)
        canonical_new_receipts(c,report)
        for ch in (1,8453):
            try:
                if ch in c.denied:raise RuntimeError('Previous provider denial stops this chain')
                observations=scan(c,ch,report,prior)
                associate(c,ch,observations,report,prior)
            except Exception as e:report['chains'].setdefault(str(ch),{})['error']=repr(e)
            save(report)
    except Exception as e:report['errors'].append(repr(e));report['traceback']=traceback.format_exc()
    report['requests']=c.n;report['denied_chains']=sorted(c.denied)
    report['complete_two_chain_scan']=all(report['chains'].get(str(x),{}).get('complete') for x in (1,8453))
    report['deposit_level_profits_verified']=0
    save(report)
    print(json.dumps({'cases':len(report['cases']),'requests':c.n,'complete_two_chain_scan':report['complete_two_chain_scan'],
      'chains':{k:{'complete':v.get('complete'),'error':v.get('error'),'leaves':v.get('candidate_refund_leaves')} for k,v in report['chains'].items()},
      'errors':report['errors']},indent=2),flush=True)
    if len(report['cases'])!=12 or report['errors']:raise SystemExit('Original frozen sample or attribution analysis failed: inspect raw artifact')
if __name__=='__main__':main()
