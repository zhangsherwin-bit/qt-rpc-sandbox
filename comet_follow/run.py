"""Bounded historical Comet absorb->buy->cash challenge. No live transactions.
Adds the previously omitted legitimate absorption of ONE already-observed borrower.
No fabricated balances, permissions, prices, times or production code. Only unused
research-executor code is inserted in read-only eth_simulateV1.
"""
import sys,json,time,hashlib,traceback,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'comet_flash'))
import replay as F
from logic import add_absorption,as_call,receipt_matches,native_delta,committed_logs,bag,BORROWER
OUT=Path('follow_evidence');OUT.mkdir(exist_ok=True);F.OUT=OUT
MAX_CALLS=70;START=time.monotonic()
def save(name,value):F.save(name,value)
class Reader:
    def __init__(self):self.n=0;self.heavy=0;self.last=-1e9;self.denied=False;self.cache={}
    def call(self,label,method,params):
        allowed={'eth_chainId','eth_getCode','eth_getBlockByNumber','eth_getTransactionReceipt','eth_call','eth_simulateV1','debug_traceTransaction'}
        if method not in allowed or self.denied:raise ValueError('Method disallowed or provider stopped')
        key=json.dumps([method,params],sort_keys=True)
        if key in self.cache:return self.cache[key]
        if self.n>=MAX_CALLS or time.monotonic()-START>1100:raise RuntimeError('Research budget reached')
        if method in ('eth_simulateV1','debug_traceTransaction'):
            if self.heavy>=8:raise RuntimeError('Eight heavy requests maximum')
            time.sleep(max(0,70-(time.monotonic()-self.last)));self.last=time.monotonic();self.heavy+=1
        else:time.sleep(1.5)
        self.n+=1;body=b'';request={'jsonrpc':'2.0','id':self.n,'method':method,'params':params}
        meta={'label':label,'payload':request,'status':'UNKNOWN','endpoint':F.RPC}
        try:
            req=urllib.request.Request(F.RPC,data=json.dumps(request).encode(),headers={'Content-Type':'application/json','User-Agent':'QT-ReadOnly-Inventory-Followthrough'})
            with urllib.request.urlopen(req,timeout=90) as resp:meta['http_status']=resp.status;body=resp.read(9000001)
            if len(body)>9000000:raise ValueError('Body exceeds cap')
            data=json.loads(body)
            if data.get('error'):
                meta['rpc_error']=data['error'];msg=str(data['error']).lower()
                if any(x in msg for x in ['rate limit','client adjustable limit','access denied','unauthorized']):self.denied=True
                raise RuntimeError(str(data['error']))
            if 'result' not in data:raise ValueError('RPC omitted result')
            meta['status']='OK';self.cache[key]=data['result'];return data['result']
        except urllib.error.HTTPError as exc:
            body=exc.read(100000);meta['error']=str(exc)
            if exc.code in (401,403,429):self.denied=True
            raise
        except Exception as exc:meta['error']=repr(exc);raise
        finally:
            meta['sha256']=hashlib.sha256(body).hexdigest();meta['bytes']=len(body)
            (OUT/'raw').mkdir(exist_ok=True);(OUT/f'raw/{self.n:03d}.body').write_bytes(body);save(f'raw/{self.n:03d}.json',meta)

def query(r,b,sig,args=()):
    return F.words(r.call(sig,'eth_call',[{'to':F.COMET,'data':F.method(sig,*args)},hex(b)]))[0]
def header(r,b,full=False):
    return r.call('canonical_header','eth_getBlockByNumber',[hex(b),full])
def environment(h):
    return {'number':h['number'],'time':h['timestamp'],'gasLimit':h['gasLimit'],'baseFeePerGas':h['baseFeePerGas'],'feeRecipient':h['miner'],'prevRandao':h['mixHash']}
def simulate(r,label,h,calls,code):
    p=header(r,int(h['number'],16)-1)
    assert p['hash']==h['parentHash']
    return r.call(label,'eth_simulateV1',[{'blockStateCalls':[{'blockOverrides':environment(h),'stateOverrides':{F.PROBE:{'code':code}},'calls':calls}], 'validation':False,'traceTransfers':False},p['number']])[0]['calls']
def test(r,label,h,prefix,receipts,fee,code):
    def call(data,gas):return {'from':F.BENEF,'to':F.PROBE,'input':data,'gas':hex(gas),'gasPrice':'0x0'}
    env=call(F.method('env()'),200000)
    action=call(F.method('run(uint256,uint24,uint256)',F.AMOUNT,fee,1000000),4500000)
    used=sum(int(q['gasUsed'],16) for q in receipts)
    assert int(h['gasLimit'],16)-used>=4900000
    calls=simulate(r,label,h,prefix+[env,action,env],code)
    if len(calls)!=len(prefix)+3 or not all(receipt_matches(c,q) for c,q in zip(calls[:len(prefix)],receipts)):
        raise ValueError('Historical prefix does not reproduce original receipts')
    a,t,z=calls[-3:]
    if a.get('status')!='0x1' or z.get('status')!='0x1':raise ValueError('Environment call failed')
    before,after=F.words(a['returnData']),F.words(z['returnData'])
    expected=[1,int(h['number'],16),int(h['timestamp'],16),int(h['baseFeePerGas'],16)]
    if len(before)!=9 or len(after)!=9 or before[:4]!=expected or after[:4]!=expected:raise ValueError('Noncanonical environment')
    if any(before[4:]):raise ValueError('Nonzero research starting balances')
    row={'label':label,'fee':fee,'block':int(h['number'],16),'prefix_transactions':len(prefix),'prefix_exact':True,'environment_exact':True,'status':t.get('status'),'gas_used':int(t['gasUsed'],16),'base_fee_cost_wei':str(int(t['gasUsed'],16)*expected[3]),'cash_before_gas_and_bid_raw':str(after[6]),'explicit_bid_paid_wei':'0'}
    if t['status']=='0x1':
        returned=F.words(t['returnData'])
        assert len(returned)==1 and returned[0]==after[6] and returned[0]>=1000000
        assert after[4:6]==[0,0] and after[7:]==[0,0]
        paid=sum(int(l['data'],16) for l in t.get('logs',[]) if l['address'].lower()==F.USDC and l['topics'][0].lower()==F.TRANSFER and l['topics'][2][-40:].lower()==F.BENEF[2:])
        if paid!=returned[0]:raise ValueError('USDC payout event mismatch')
        row['cash_paid_verified']=True
    else:
        row['error']=t.get('error');row['rollback_verified']=before[4:]==after[4:]
        if not row['rollback_verified']:raise ValueError('Economic failure changed balances')
    save('cases/'+label+'.json',{'header':h,'calls':calls,'result':row});return row

def main():
    report={'scope':'ONE frozen historical Comet borrower; corrected complete pathway and controls','retrospective':True,'trading_or_signing':False,'opportunity_capture_proven':False,'new_executions':[],'matched_bid_execution':False,'complete':False}
    r=Reader();save('REPORT.json',report)
    try:
        assert r.call('chain','eth_chainId',[])=='0x1'
        h=header(r,F.BLOCK,True);record=r.call('original_receipt','eth_getTransactionReceipt',[F.ORIGINAL_TX])
        pos=int(record['transactionIndex'],16);assert pos==2 and h['transactions'][pos]['hash']==F.ORIGINAL_TX
        prefix=[as_call(t) for t in h['transactions'][:pos]]
        receipts=[r.call('prefix_receipt','eth_getTransactionReceipt',[t['hash']]) for t in h['transactions'][:pos]]
        original_call=as_call(h['transactions'][pos])
        report['historical_winner_receipt']=record;report['borrower']=BORROWER
        for b in [F.BLOCK-2,F.BLOCK-1,F.BLOCK]:
            row={'block':b}
            for sig,args in [('getCollateralReserves(address)',(int(F.WETH,16),)),('isLiquidatable(address)',(int(BORROWER,16),)),('getReserves()',()),('targetReserves()',())]:
                row[sig]=str(query(r,b,sig,args))
            report.setdefault('original_inventory_and_health',[]).append(row)
        F.pending_codes(r)
        original=Path('comet_flash/CometCashProbe.sol').read_text();patched=add_absorption(original)
        save('original_source.json',{'content':original,'sha256':hashlib.sha256(original.encode()).hexdigest()})
        try:
            Path('comet_flash/CometCashProbe.sol').write_text(patched);code=F.compile_contract()
        finally:Path('comet_flash/CometCashProbe.sol').write_text(original)
        calibration=simulate(r,'canonical_winner_calibration',h,prefix+[original_call],code)
        if len(calibration)!=pos+1 or not all(receipt_matches(x,y) for x,y in zip(calibration,receipts+[record])):raise ValueError('Full original winner calibration failed')
        report['original_winner_calibrated']=True;save('calibration.json',{'calls':calibration,'receipts':receipts+[record]})
        trace=r.call('winner_full_cash_trace','debug_traceTransaction',[F.ORIGINAL_TX,{'tracer':'callTracer','tracerConfig':{'withLog':True},'timeout':'40s'}]);save('winner_trace.json',trace)
        assert not trace.get('error') and int(trace['gasUsed'],16)==int(record['gasUsed'],16) and bag(committed_logs(trace))==bag(record['logs'])
        basefee=int(h['baseFeePerGas'],16);tip=int(record['effectiveGasPrice'],16)-basefee
        if tip<0:raise ValueError('Negative observed priority fee')
        direct=native_delta(trace,h['miner']);comp=direct+tip*int(record['gasUsed'],16)
        report['observed_visible_producer_payment_wei']=str(comp);report['observed_direct_payment_wei']=str(direct)
        variants=[('corrected_exact_prefix_500',h,prefix,receipts,500),('corrected_exact_prefix_3000',h,prefix,receipts,3000),('corrected_block_start',h,[],[],500),('corrected_previous_block',header(r,F.BLOCK-1),[],[],500),('corrected_after_winner',h,prefix+[original_call],receipts+[record],500)]
        for label,head,calls,recs,fee in variants:
            try:report['new_executions'].append(test(r,label,head,calls,recs,fee,code))
            except Exception as exc:report['new_executions'].append({'label':label,'exception':repr(exc)})
            save('REPORT.json',report)
            if r.denied:break
        report['complete']=len(report['new_executions'])==5 and all('status' in x for x in report['new_executions'])
    except Exception as exc:report['fatal']=repr(exc);report['traceback']=traceback.format_exc()
    report['requests']=r.n;report['heavy_calls']=r.heavy;report['provider_denied']=r.denied
    report['note']='Positive payouts exclude actual gas and inclusion bid; alternative paths and states are not additive. Deployment and real capture remain untested.'
    save('REPORT.json',report);print(json.dumps(report,indent=2),flush=True)
    if not report['complete']:raise SystemExit('Incomplete research; inspect retained errors, not a zero-opportunity claim')
if __name__=='__main__':main()
