"""PR29 follow-on: five frozen historical keeper days, complete cash and producer accounting.
Read-only RPC only. All calendar-selected trades are retrospective development data.
"""
import collections,datetime as dt,hashlib,json,pathlib,sys,traceback
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'followthrough'))
import prefix_finish as F
R,D,C,OUT=F.R,F.D,F.C,F.OUT
DAYS=('2026-09-16','2026-09-18','2026-09-21','2026-09-29','2026-09-30')
BASELINES={'0xfd7779247099a7ced3a6480dafd06d3fdf3846b310f30fbfbc82c892cddb0d03','0x46199ad11bfec9b686c6846e05b2665481eb2b96fef71f9ec840cc31c96084cf','0x3bb89f780cb33005531f501446d7f3dbc92017703da9604f07bc5e99f055bf65'}
TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
LP='0x390f3595bca2df7d23783dfd126427cceb997bf4'

def day(x):return dt.datetime.fromtimestamp(int(x['blockTimestamp'],16),dt.timezone.utc).date().isoformat()
def reward(receipt,keeper):
    # Only LP transfers leaving the keeper for a nonzero recipient; burn is NOT income.
    awards=[]
    for x in receipt.get('logs',[]):
        t=x.get('topics',[])
        if x['address'].lower()==LP and len(t)>=3 and t[0].lower()==TRANSFER and t[1][-40:].lower()==keeper[2:].lower() and int(t[2],16)!=0:
            awards.append(int(x['data'],16))
    if len(awards)!=1:raise ValueError('missing or ambiguous actual caller reward transfer')
    return awards[0]

def freeze(events,receipts,keeper):
    e=[x for x in events if x['address'].lower()==keeper.lower()]
    if len(e)!=98 or len(set(x['transactionHash'] for x in e))!=98:raise ValueError('unexpected original census')
    m={r['transactionHash']:r for r in receipts}
    if len(m)!=100:raise ValueError('missing source receipts')
    for x in e:
        r=m[x['transactionHash']]
        if r.get('status')!='0x1' or r.get('blockHash')!=x['blockHash']:raise ValueError('receipt mismatch')
        x['_reward']=reward(r,keeper)
    out=[]
    for d in DAYS:
        c=[x for x in e if day(x)==d and int(x['transactionIndex'],16)<=10 and x['transactionHash'] not in BASELINES]
        if not c:raise ValueError('frozen day unavailable: '+d)
        out.append(min(c,key=lambda x:(-x['_reward'],int(x['blockNumber'],16),x['transactionHash'])))
    if len({x['transactionHash'] for x in out})!=5:raise ValueError('duplicate events')
    return out

def verify_archive(folder):
    count=0
    for meta in folder.glob('raw/*.json'):
        m=json.loads(meta.read_text());body=meta.with_suffix('.body').read_bytes()
        if hashlib.sha256(body).hexdigest()!=m['sha256']:raise ValueError('raw SHA mismatch '+str(meta))
        count+=1
    return count

def net_cash(x):
    if x.get('status')!='0x1' or not x.get('rows'):return None
    return int(x['rows'][0]['net_eth_after_base_fee_wei'])

def main(check=False):
    events=json.loads(pathlib.Path('input_census/keeper_events.json').read_text());recs=json.loads(pathlib.Path('input_census/SERVICE_RECEIPTS.json').read_text());keeper=C.KEEPERS[1]
    selected=freeze(events,recs,keeper)
    selection=[dict(date=day(x),tx=x['transactionHash'],block=int(x['blockNumber'],16),transaction_index=int(x['transactionIndex'],16),reward_LP_raw=str(x['_reward'])) for x in selected]
    if check:
        print(json.dumps({'census_keeper_events':98,'census_receipts':len(recs),'reward_is_actual_non_burn_LP_transfer':True,'frozen':selection},indent=2));return
    OUT.mkdir(exist_ok=True)
    report={'prior_completed_PR29_run':39051620147,'original_census_run':39016955510,'type':'retrospective development, not live or holdout','frozen':selection,'outcomes':[],'signed_or_sent':0,'notes':['no principal supplied to research executor','zero-priced synthetic caller with base-fee gas deducted separately','observed winner producer payment is not minimum or sufficient bid','different reset-state variants are not additive','5 early-block events selected by LP reward amount, not trade profit']}
    r=None
    try:
        report['prior_verified_raw_count']=sum(verify_archive(pathlib.Path(x)) for x in ('input_census','input_services','input_repair'))
        C.ALLOWED.update({'eth_simulateV1','debug_traceTransaction','eth_getBlockReceipts'})
        r=F.Runner();assert r.rpc('chain','eth_chainId',[])=='0x1'
        runtime=F.build_metered();C.save('FROZEN_SELECTION.json',selection)
        for i,x in enumerate(selected):
            row={'date':day(x),'tx':x['transactionHash'],'reward_LP_raw':str(x['_reward']),'mode_results':[],'complete':False}
            try:
                receipt=r.getreceipt(x['transactionHash']);header,prefix,prefix_receipts=r.prefix(receipt)
                row['headroom_gas']=F.historical_headroom(header,prefix_receipts)
                trace=r.rpc(f'cohort_winner_{i}','debug_traceTransaction',[x['transactionHash'],{'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True}}])
                C.save(f'traces/winner_{i}.json',trace)
                if trace.get('error') or int(trace['gasUsed'],16)!=int(receipt['gasUsed'],16) or collections.Counter(R.logbag(trace))!=collections.Counter(R.normlogs(receipt['logs'])):raise ValueError('original trace does not match receipt')
                transfer=F.native_delta(trace,header['miner'].lower());bid=F.compensation(receipt,header,transfer)
                row.update(original_winner_direct_payment_wei=str(transfer),original_winner_total_visible_producer_payment_wei=str(bid))
                for mode in (1,4):
                    try:
                        sim=F.one(r,f'cohort_{i}_mode_{mode}',header,prefix,prefix_receipts,(1,keeper,[],0,mode,b''),runtime,0)
                        cash=net_cash(sim);row['mode_results'].append({'mode':mode,'execution_status':sim.get('status'),'gas_used':sim.get('gas_used'),'cash_after_basefee_wei':str(cash) if cash is not None else None,'equal_visible_payment_arithmetic_wei':str(cash-bid) if cash is not None else None,'error':sim.get('error')})
                    except Exception as e:row['mode_results'].append({'mode':mode,'unresolved':repr(e)})
                    C.save('SUMMARY.json',report|{'outcomes':report['outcomes']+[row]})
                    if r.stopped:raise RuntimeError('provider access denied / rate limited')
                viable=[v for v in row['mode_results'] if v.get('equal_visible_payment_arithmetic_wei') is not None and int(v['equal_visible_payment_arithmetic_wei'])>0]
                if viable:
                    best=max(viable,key=lambda x:int(x['equal_visible_payment_arithmetic_wei']))
                    try:
                        sim=F.one(r,f'cohort_{i}_equal_visible_payment',header,prefix,prefix_receipts,(1,keeper,[],0,best['mode'],b''),runtime,bid)
                        row['equal_payment_execution']={'status':sim.get('status'),'gas':sim.get('gas_used'),'rows':sim.get('rows'),'error':sim.get('error')}
                    except Exception as e:row['equal_payment_execution_unresolved']=repr(e)
                else:row['equal_payment_execution']={'not_run':True,'reason':'both variants fail to exceed total observed producer compensation; no winning-bid inference'}
                row['complete']=all(v.get('execution_status') in ('0x0','0x1') for v in row['mode_results']) and 'equal_payment_execution_unresolved' not in row
            except Exception as e:row['unresolved']=repr(e)
            report['outcomes'].append(row);C.save('SUMMARY.json',report)
            if r.stopped:break
    except Exception as e:
        report['error']=repr(e);report['traceback']=traceback.format_exc()
    report['heavy_calls']=r.new_heavy if r else 0;report['requests']=r.n if r else 0
    report['complete']=len(report['outcomes'])==len(DAYS) and all(x['complete'] for x in report['outcomes'])
    C.save('SUMMARY.json',report)
    print(json.dumps({'complete':report['complete'],'requests':report['requests'],'heavy_calls':report['heavy_calls'],'outcomes':report['outcomes'],'error':report.get('error')},indent=2),flush=True)
    if not report['complete']:raise SystemExit('Partial provider or execution evidence, not zero profit')
if __name__=='__main__':main('--check-only' in sys.argv)
