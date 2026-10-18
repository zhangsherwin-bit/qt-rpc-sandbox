"""Read-only same-state ETH-funding quote. NOT an executed producer payment.
Reproduce the completed cash call, then quote buying the exact observed ETH bid.
Do not substitute parent-block prices or quote gas for a full transaction's gas.
"""
from pathlib import Path
import json,copy,hashlib,time,urllib.request,urllib.error
INPUT=Path('input_cash');OUT=Path('funding_evidence')
QUOTER='0x61ffe014ba17989e743c5f6cb21bf9697530b21e'
USDC='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48';WETH='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
BENEF='0x00000000000000000000000000000000dead8821'
FEES=(100,500,3000,10000)
def pad(x):return format(int(x,16) if isinstance(x,str) else x,'064x')
def quote_data(amount,fee):return '0xbd21704a'+pad(USDC)+pad(WETH)+pad(amount)+pad(fee)+pad(0)
def uints(x):
    if not isinstance(x,str) or not x.startswith('0x') or (len(x)-2)%64:raise ValueError('Invalid ABI')
    return [int(x[i:i+64],16) for i in range(2,len(x),64)]
def find_case():
    for p in sorted((INPUT/'raw').glob('*.json')):
        m=json.loads(p.read_text())
        if m.get('label')=='corrected_exact_prefix_500':
            b=p.with_suffix('.body').read_bytes()
            if hashlib.sha256(b).hexdigest()!=m['sha256']:raise ValueError('Source response digest mismatch')
            req=m['payload'];old=json.loads(b)['result'][0]['calls']
            if req['method']!='eth_simulateV1' or len(old)!=5:raise ValueError('Wrong frozen source')
            if old[-2]['status']!='0x1' or uints(old[-2]['returnData'])!=[405338373]:raise ValueError('Positive calibration missing')
            return req,old
    raise ValueError('Missing successful source case')
def economic_comparison(cash,cost):
    return {'available_USDC_raw':str(cash),'funding_cost_USDC_raw':str(cost),'remaining_before_network_costs_raw':str(cash-cost),'covers_observed_payment_before_gas':cash>=cost}
def main():
    OUT.mkdir(exist_ok=True)
    report={'source_run':39117372686,'source_scenario':'corrected_exact_prefix_500','actual_payment_executed':False,'quote_after_cash_route':True,'capture_or_profit_proven':False,'quotes':[]}
    request,old=find_case();request=copy.deepcopy(request);request['id']=1
    rep=json.loads((INPUT/'REPORT.json').read_text());bid=int(rep['observed_visible_producer_payment_wei'])
    if bid!=174449845338543024:raise ValueError('Observed compensation changed')
    report['observed_bid_wei']=str(bid)
    calls=request['params'][0]['blockStateCalls'][0]['calls']
    assert len(calls)==5
    for fee in FEES:calls.append({'from':BENEF,'to':QUOTER,'input':quote_data(bid,fee),'gas':'0x1e8480','gasPrice':'0x0'})
    body=b'';meta={'payload':request,'status':'UNAVAILABLE','time_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    try:
        req=urllib.request.Request('https://rpc-eth.blockmachine.io',data=json.dumps(request).encode(),headers={'Content-Type':'application/json','User-Agent':'QT-ReadOnly-Comet-Funding-Quote'})
        with urllib.request.urlopen(req,timeout=100) as response:body=response.read(9000001);meta['http_status']=response.status
        if len(body)>9000000:raise ValueError('Response size exceeds budget')
        data=json.loads(body)
        if data.get('error'):raise RuntimeError(str(data['error']))
        cs=data['result'][0]['calls']
        if len(cs)!=9:raise ValueError('Unexpected call count')
        for a,b in zip(cs[:5],old):
            for key in ('status','gasUsed','returnData','logs'):
                if a.get(key)!=b.get(key):raise ValueError('Original cash execution changed: '+key)
        report['all_original_calls_exact']=True
        report['cash_payout_USDC_raw']=str(uints(cs[3]['returnData'])[0])
        for fee,call in zip(FEES,cs[5:]):
            row={'fee':fee,'status':call.get('status'),'error':call.get('error')}
            if call.get('status')=='0x1':
                value=uints(call['returnData']);assert len(value)==4
                row.update(economic_comparison(405338373,value[0]));row['sqrtPriceAfter']=str(value[1])
            report['quotes'].append(row)
        meta['status']='OK';report['complete']=True
    except urllib.error.HTTPError as e:body=e.read(100000);meta['error']=str(e);report['error']=str(e)
    except Exception as e:meta['error']=repr(e);report['error']=repr(e)
    finally:
        meta['sha256']=hashlib.sha256(body).hexdigest();meta['bytes']=len(body)
        (OUT/'rpc.body').write_bytes(body);(OUT/'rpc.meta.json').write_text(json.dumps(meta,indent=2)+'\n')
        (OUT/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
    if not report.get('complete'):raise SystemExit('Funding evidence incomplete; no repeat after provider refusal')
if __name__=='__main__':main()
