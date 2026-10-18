"""Offline correction of PR51's saved quote-result guard. NO new network calls.
Appending quotation calls changes the synthetic block hash. We allow precisely that
metadata change, require each log's hash to match its enclosing simulated block,
and retain every other log field, exact order, multiplicity, gas and cash result.
Canonical request block context and original first five calls remain identical.
"""
from pathlib import Path
from copy import deepcopy
import json,hashlib
import check as C
BODY_SHA='6ed2f1abc44e77aaff895d1e56627a7aabda0509b6970e7da2b7696ab63cbc8b'

def load(p):return json.loads(p.read_text())
def check_logs(before,after,old_hash,new_hash):
    if len(before)!=len(after):raise ValueError('Log count changed')
    changed=0
    for a,b in zip(before,after):
        if a.get('blockHash')!=old_hash or b.get('blockHash')!=new_hash:
            raise ValueError('Log hash inconsistent with enclosing synthetic block')
        if {k:v for k,v in a.items() if k!='blockHash'}!={k:v for k,v in b.items() if k!='blockHash'}:
            raise ValueError('Log data, identity, order or non-hash metadata changed')
        changed+=int(a['blockHash']!=b['blockHash'])
    return changed

def decode(source,failed):
    C.INPUT=source
    request,old=C.find_case()
    m=load(failed/'rpc.meta.json');body=(failed/'rpc.body').read_bytes()
    digest=hashlib.sha256(body).hexdigest()
    if digest!=m['sha256'] or digest!=BODY_SHA or len(body)!=m['bytes']:
        raise ValueError('Saved quote body hash or length mismatch')
    block=json.loads(body)['result'][0];calls=block['calls']
    if len(calls)!=9:raise ValueError('Expected five original and four quotation calls')
    new_request=deepcopy(m['payload']);new_request['params'][0]['blockStateCalls'][0]['calls']=new_request['params'][0]['blockStateCalls'][0]['calls'][:5]
    if new_request['method']!=request['method'] or new_request['params']!=request['params']:
        raise ValueError('Canonical state, code override, execution envelope or original calls changed')
    contexts=load(source/'cases/corrected_exact_prefix_500.json')
    expected=contexts['header']
    for k in ('number','timestamp','gasLimit','baseFeePerGas','miner','mixHash','parentHash'):
        if block[k]!=expected[k]:raise ValueError('Canonical header changed '+k)
    old_hash=next(l['blockHash'] for c in old for l in c.get('logs',[]))
    changed=0
    for a,b in zip(old,calls[:5]):
        for k in set(a)|set(b):
            if k!='logs' and a.get(k)!=b.get(k):raise ValueError('Original call changed '+k)
        changed+=check_logs(a.get('logs',[]),b.get('logs',[]),old_hash,block['hash'])
    report=load(source/'REPORT.json');bid=int(report['observed_visible_producer_payment_wei'])
    if bid!=174449845338543024:raise ValueError('Unexpected observed producer compensation')
    cash=C.uints(calls[3]['returnData'])[0]
    rows=[]
    appended=m['payload']['params'][0]['blockStateCalls'][0]['calls'][5:]
    for fee,call,envelope in zip(C.FEES,calls[5:],appended):
        if envelope['to']!=C.QUOTER or envelope['input']!=C.quote_data(bid,fee):
            raise ValueError('Quote target, input/output direction, amount or fee mismatch')
        q={'fee':fee,'status':call.get('status'),'error':call.get('error')}
        if call.get('status')=='0x1':
            values=C.uints(call['returnData'])
            if len(values)!=4:raise ValueError('Quoter output ABI mismatch')
            q.update(C.economic_comparison(cash,values[0]))
        rows.append(q)
    successes=[q for q in rows if q['status']=='0x1']
    best=min(successes,key=lambda q:int(q['funding_cost_USDC_raw'])) if successes else None
    return {'scope':'Reanalysis of already-returned same-state quote; zero new RPC requests',
        'source_run':39117372686,'failed_parser_run':39118164784,
        'exact_request_and_original_execution_preserved':True,
        'only_per_log_difference':'blockHash of the enclosing synthetic block',
        'logs_reconciled_with_new_synthetic_hash':changed,'saved_response_sha256':digest,
        'cash_payout_raw':str(cash),'observed_producer_payment_wei':str(bid),'quotes':rows,
        'best_quote':best,'cash_net_profit_proven':False,'actual_producer_payment_executed':False,
        'candidate_base_fee_cost_wei':str(int(calls[3]['gasUsed'],16)*int(expected['baseFeePerGas'],16)),
        'limitations':['Quoter output is not an executed ETH purchase or producer payment.',
        'The observed producer payment is a benchmark, not a necessary or sufficient winning bid.',
        'A negative cash-minus-bid-funding amount is before additional network, funding and inclusion costs.']}

def main():
    result=decode(Path('input_cash'),Path('input_failed'))
    out=Path('funding_decode_evidence');out.mkdir(exist_ok=True)
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
