"""Read-only four-date cash replay using the successful PR29 historical executor.
No signing, sending, balances/storage/oracle overrides or live trades.
Cases are retrospectively reward-ranked development data, NOT a holdout.
"""
import sys,pathlib,json,traceback,collections
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'followthrough'))
from cohort_utils import validate_selection,ranked_best
import prefix_finish as P
import run as R
import execute as D
from logic import compensation,native_delta,logbag,normlogs,historical_headroom

C=R.C
OUT=C.OUT
SELECTION=pathlib.Path('cohort/selection.json')
MAX_HEAVY=20
MAX_NEW_REQUESTS=130

def case_label(idx,stage):
    if stage not in ('tier100','tier500','equal_bid','post_original'):
        raise ValueError('unapproved test stage')
    return f'cohort_{idx:02d}_{stage}'

def go():
    OUT.mkdir(parents=True,exist_ok=True)
    study=json.loads(SELECTION.read_text());selection=validate_selection(study)
    report={'research_only':True,'signed_or_sent_transactions':0,
       'income_estimate_or_capture_rate_established':False,
       'selection_rule':study['selection_rule'],'selection':selection,'cases':[],
       'limits':{'max_new_heavy_calls':MAX_HEAVY,'max_new_rpc':MAX_NEW_REQUESTS},
       'warnings':['Reward-ranked retrospective historical development, not a clean holdout',
       'LP receipt is not terminal cash, dollar profit or user income',
       'Matching observed producer compensation is neither necessary nor sufficient for inclusion',
       'Per-event alternate size and route simulations are not independently additive',
       'Synthetic caller gas price zero: historical gas is deducted afterward; upfront ETH needed',
       'The research runner inserts code only at an unused address; no production state changes']}
    C.save('COHORT_REPORT.json',report);r=None
    try:
        C.ALLOWED.update({'eth_simulateV1','debug_traceTransaction','eth_getBlockReceipts'})
        class BoundedRunner(P.Runner):
            def rpc(self,name,method,params):
                key=json.dumps([method,params],sort_keys=True)
                if key not in self.raw_cache and self.n>=MAX_NEW_REQUESTS:
                    raise RuntimeError('research RPC request limit reached')
                return super().rpc(name,method,params)
        r=BoundedRunner()
        runtime=P.build_metered()
        prior=json.loads(pathlib.Path('input_repair/BUILD.json').read_text())
        assert len(prior['source_sha256'])==64
        for idx,case in enumerate(selection):
            item={'id':case['id'],'tx':case['tx'],'date':case['date'],
                  'observed_lp_raw_not_cash':case['reward_lp_raw'],
                  'outcomes':[],'same_bid_execution':None,'post_winner_control':None}
            report['cases'].append(item);C.save('COHORT_REPORT.json',report)
            try:
                rec=r.getreceipt(case['tx'])
                assert int(rec['blockNumber'],16)==case['block'] and rec['status']=='0x1'
                h,prefix,rr=r.prefix(rec)
                assert len(prefix)==int(rec['transactionIndex'],16)
                room=historical_headroom(h,rr)
                assert room>=1_200_000
                item.update(canonical_block_hash=h['hash'],
                    canonical_prefix_transactions=len(prefix),canonical_headroom_gas=room)
                orig=r.rpc('observed_winner_'+str(idx),'debug_traceTransaction',[
                    case['tx'],{'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True}}])
                C.save('traces/cohort_winner_%02d.json'%idx,orig)
                assert not orig.get('error')
                assert int(orig['gasUsed'],16)==int(rec['gasUsed'],16)
                assert collections.Counter(logbag(orig))==collections.Counter(normlogs(rec['logs']))
                bid=compensation(rec,h,native_delta(orig,h['miner'].lower()))
                item.update(observed_winner_total_visible_producer_compensation_wei=str(bid),
                            trace_receipts_exact=True)
                tests=[]
                for mode,name in [(2,'tier100'),(1,'tier500')]:
                    if r.new_heavy>=MAX_HEAVY:
                        raise RuntimeError('heavy-call budget exhausted before simulation')
                    try:
                        job=(1,C.KEEPERS[1],[],0,mode,b'')
                        observed=P.one(r,case_label(idx,name),h,prefix,rr,job,runtime,0)
                        observed['mode']=mode;tests.append((mode,observed))
                        item['outcomes'].append(observed)
                    except Exception as exc:
                        item['outcomes'].append({'mode':mode,'error':repr(exc),'verified_cash':False})
                    C.save('COHORT_REPORT.json',report)
                    if r.stopped:
                        raise RuntimeError('provider denied or rate limited; stop immediately')
                best=ranked_best(tests)
                item['best_tested_mode']=best
                if best is None:
                    item['economics_status']='No validated terminal WETH cash settlement'
                else:
                    best_row=next(x for mode,x in tests if mode==best)
                    net=int(best_row['rows'][0]['net_eth_after_base_fee_wei'])
                    item['best_pre_bid_net_wei']=str(net)
                    item['benchmark_net_wei_if_equal_compensation_and_unchanged_gas']=str(net-bid)
                    if net>0:
                        job=(1,C.KEEPERS[1],[],0,best,b'')
                        try:
                            item['same_bid_execution']=P.one(r,case_label(idx,'equal_bid'),h,prefix,rr,job,runtime,bid)
                        except Exception as exc:
                            item['same_bid_execution']={'error':repr(exc)}
                        C.save('COHORT_REPORT.json',report)
                        if r.stopped:raise RuntimeError('provider denied or rate limited')
                        if r.new_heavy<MAX_HEAVY:
                            try:
                                full=r.rpc('full_header','eth_getBlockByNumber',[h['number'],True])
                                position=int(rec['transactionIndex'],16)
                                assert full['transactions'][position]['hash']==case['tx']
                                item['post_winner_control']=P.one(r,case_label(idx,'post_original'),
                                    h,prefix+[D.ascall(full['transactions'][position])],
                                    rr+[rec],job,runtime,0)
                            except Exception as exc:
                                item['post_winner_control']={'error':repr(exc)}
                    else:
                        item['economics_status']='Pre-bid cash does not cover historical base-fee gas'
            except Exception as exc:
                item['exception']=repr(exc)
                item['traceback']=traceback.format_exc()
            C.save('COHORT_REPORT.json',report)
            if r.stopped:raise RuntimeError('provider denied or rate limited')
            if r.new_heavy>=MAX_HEAVY:break
    except Exception as exc:
        report['run_exception']=repr(exc)
        report['run_traceback']=traceback.format_exc()
    report['usage']={'new_rpc':r.n if r else None,'new_heavy':r.new_heavy if r else None,
                     'provider_stopped':r.stopped if r else None}
    report['all_cases_attempted']=len(report['cases'])==len(selection)
    report['complete_economic_cases']=sum(c.get('best_pre_bid_net_wei') is not None for c in report['cases'])
    C.save('COHORT_REPORT.json',report)
    print(json.dumps({'case_outcomes':[{'id':c['id'],'best_pre_bid_net_wei':c.get('best_pre_bid_net_wei'),
      'benchmark_net_wei':c.get('benchmark_net_wei_if_equal_compensation_and_unchanged_gas'),
      'exception':c.get('exception')} for c in report['cases']],
      'usage':report['usage'],'complete_economic_cases':report['complete_economic_cases'],
      'run_exception':report.get('run_exception')},indent=2),flush=True)
    if report.get('run_exception') or not report['all_cases_attempted'] or report['complete_economic_cases']!=len(selection):
        raise SystemExit('Incomplete economic research; artifact retained. Never report a provider failure as zero profit.')

if __name__=='__main__':go()
