"""Bounded read-only historical repairs. No wallets, signing or broadcasts."""
import sys,pathlib,json,hashlib,time,traceback,collections
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'angles_probe'),str(ROOT/'followthrough')]
import execute as D
from logic import transform,BASE_SHA,CRVUSD,normlogs,logbag,native_delta,compensation,historical_headroom
from eth_abi import encode,decode
from solcx import install_solc,compile_standard
C=D.C;OUT=C.OUT;INPUT=pathlib.Path('input_services')
def save(n,v):C.save(n,v)

def build():
 s=(INPUT/'CashProbe.sol').read_text();assert hashlib.sha256(s.encode()).hexdigest()==BASE_SHA
 old=(INPUT/'runtime.hex').read_text().strip();b=json.loads((INPUT/'BUILD.json').read_text())
 assert hashlib.sha256(bytes.fromhex(old[2:])).hexdigest()==b['runtime_sha256']
 src=transform(s);(OUT/'ImprovedKeeper.sol').write_text(src)
 inp={'language':'Solidity','sources':{'ImprovedKeeper.sol':{'content':src}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.deployedBytecode.object']}}}}
 save('compiler_input.json',inp);install_solc('0.8.24');res=compile_standard(inp,solc_version='0.8.24');save('compiler_output.json',res)
 ct=res['contracts']['ImprovedKeeper.sol']['CashProbe'];runtime='0x'+ct['evm']['deployedBytecode']['object'];assert (len(runtime)-2)//2<24576
 (OUT/'runtime.hex').write_text(runtime)
 save('BUILD.json',{'source_sha256':hashlib.sha256(src.encode()).hexdigest(),'runtime_sha256':hashlib.sha256(bytes.fromhex(runtime[2:])).hexdigest(),'baseline_runtime_sha256':b['runtime_sha256'],'compiler':'0.8.24','runtime_bytes':(len(runtime)-2)//2})
 return old,runtime

class Client(D.Runner):
 def __init__(self):
  super().__init__();self.new_heavy=0
  for p in sorted((INPUT/'raw').glob('*.json')):
   m=json.loads(p.read_text());raw=p.with_suffix('.body').read_bytes();assert hashlib.sha256(raw).hexdigest()==m['sha256']
   q=m['payload'];v=json.loads(raw)
   if m.get('status')=='OK':self.raw_cache[json.dumps([q['method'],q['params']],sort_keys=True)]=v['result']
 def rpc(self,name,method,params):
  cached=json.dumps([method,params],sort_keys=True) in self.raw_cache
  if not cached:
   if self.n>=160 or time.monotonic()-self.start>2400:raise RuntimeError('bounded run exhausted')
   if method in ('eth_simulateV1','debug_traceCall','debug_traceTransaction'):
    if self.new_heavy>=22:raise RuntimeError('heavy request cap')
    time.sleep(max(0,70-(time.monotonic()-self.last)));self.new_heavy+=1
  return super().rpc(name,method,params)
 def call(self,data,gas=12000000,to=D.PROBE):
  gas={24000000:1200000,100000:50000,250000:100000}.get(gas,gas)
  return super().call(data,gas,to)

def trace_call(r,name,tx,n,cfg):
 t=r.rpc(name,'debug_traceCall',[tx,hex(n),cfg]);save('traces/'+name+'.json',t);return t

def inspect_interfaces(r):
 b=int(D.load('BOUNDARIES.json')['last']['number'],16);out={'block':b,'liquity':[]}
 for tm in C.TMS:
  row={'trove_manager':tm}
  try:
   ap=r.view(tm,'activePool()',[],[],b,['address'])[0];ct=r.view(ap,'collToken()',[],[],b,['address'])[0]
   row.update(active_pool=ap,collateral_token=ct,verified_lookup_chain=True)
  except Exception as e:row['error']=repr(e)
  out['liquity'].append(row)
 out['arm']=r.many([(C.ARM,s,[],[],['uint256']) for s in ['traderate0()','traderate1()']],b)
 save('INTERFACES.json',out)

def auction_checkpoint(r):
 b=int(D.load('BOUNDARIES.json')['last']['number'],16);pairs=D.load('RECIPROCAL_PAIRS_STRUCTURAL.json')
 legs=sorted(set(tuple(x) for pair in pairs for x in pair));jobs=[]
 for a,f,w in legs:
  jobs.extend([(a,'available(address)',['address'],[f],['uint256']),(a,'kickable(address)',['address'],[f],['uint256']),(f,'balanceOf(address)',['address'],[a],['uint256'])])
 vals=r.many(jobs,b);rows=[]
 for i,(a,f,w) in enumerate(legs):
  v=vals[3*i:3*i+3];row={'auction':a,'from':f,'want':w,'available':v[0]['values'][0] if v[0]['ok'] else None,'kickable':v[1]['values'][0] if v[1]['ok'] else None,'token_balance':v[2]['values'][0] if v[2]['ok'] else None,'view_errors':[x for x in v if not x['ok']]};rows.append(row)
 by={tuple(x):row for x,row in zip(legs,rows)};cash={C.WETH,'0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48','0xdac17f958d2ee523a2206206994597c13d831ec7'};tests=[]
 for pair in pairs:
  for A,B in [pair,pair[::-1]]:
   a=by[tuple(A)];brow=by[tuple(B)]
   if a['from'] not in cash or not a['available'] or not brow['available']:continue
   x={'A':a,'B':brow}
   try:
    owed=r.view(a['auction'],'getAmountNeeded(address,uint256)',['address','uint256'],[a['from'],a['available']],b,['uint256'])[0];x['A_payment']=owed
    if owed>brow['available']:x['status']='insufficient_B_inventory'
    else:
     cost=r.view(brow['auction'],'getAmountNeeded(address,uint256)',['address','uint256'],[brow['from'],owed],b,['uint256'])[0]
     x.update(status='finite_quote_only',cash_surplus_raw=str(a['available']-cost),cash_token=a['from'])
   except Exception as exc:x['error']=repr(exc)
   tests.append(x)
 save('AUCTION_CHECKPOINT.json',{'block':b,'scope':'one canonical study-end snapshot only; does not establish historical nonexistence','legs':rows,'pairs_examined':len(pairs),'cash_tests':tests,'full_cash_execution':False})

def main():
 OUT.mkdir(exist_ok=True);report={'new_workflow':True,'signed_or_sent':0,'baseline_repairs':[],'alternative_exits':[],'warnings':['retrospective first/middle/last events, not a calendar income census','synthetic caller gasPrice=0; real caller needs gas upfront','equal observed compensation is not a proven winning bid','each reset alternative is separate, not additive income']};r=None
 try:
  C.ALLOWED.update({'eth_simulateV1','debug_traceCall','debug_traceTransaction','eth_getBlockReceipts'})
  r=Client();assert r.rpc('chain','eth_chainId',[])=='0x1';old,new=build()
  rows=sorted({x['transactionHash']:x for x in D.load('keeper_events.json') if x['address'].lower()==C.KEEPERS[1]}.values(),key=lambda x:(int(x['blockNumber'],16),int(x['transactionIndex'],16)))
  selected=[rows[i] for i in sorted(set([0,len(rows)//2,len(rows)-1]))]
  save('PLAN.json',{'selection':selected,'original_runtime_unchanged':True,'exits':{'1':'coin0->Uniswap500->WETH','2':'coin0->Uniswap100->WETH','3':'crvUSD->CurveUSDC->Uniswap500->WETH','4':'crvUSD->CurveTricryptoWETH'},'repair':'smaller declared research gas; separately calibrated transaction-index tracing','max_new_rpc':160,'max_heavy':22,'seconds':2400,'no_reserved_oct3_oct9':True})
  for i,e in enumerate(selected):
   item={'tx':e['transactionHash']}
   try:
    rec=r.getreceipt(e['transactionHash']);h,prefix,rr=r.prefix(rec);item['headroom']=historical_headroom(h,rr)
    if item['headroom']<1500000:raise ValueError('insufficient gas budget for unchanged-prefix diagnostic')
    item['result']=r.simulate('repaired_original_%d'%i,h,[(1,C.KEEPERS[1],[],0,1,b'')],old,prefix,rr,True)
   except Exception as exc:item['error']=repr(exc)
   report['baseline_repairs'].append(item);save('SUMMARY.json',report)
   if r.stopped:raise RuntimeError('provider access/rate refusal')
  inspect_interfaces(r);auction_checkpoint(r)
  for i,e in enumerate(selected):
   item={'tx':e['transactionHash'],'results':[]}
   try:
    rec=r.getreceipt(e['transactionHash']);n=int(rec['blockNumber'],16);h,prefix,rr=r.prefix(rec);idx=int(rec['transactionIndex'],16)
    headroom=historical_headroom(h,rr);item['headroom']=headroom
    full=r.rpc('full_header','eth_getBlockByNumber',[hex(n),True]);tx=full['transactions'][idx];assert tx['hash']==e['transactionHash']
    orig={k:tx[k] for k in ('from','to','value','gas','accessList','authorizationList') if tx.get(k) is not None};orig.update(input=tx['input'],gasPrice=rec['effectiveGasPrice'])
    cfg={'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True},'txIndex':idx}
    cal=trace_call(r,'calibration_%d'%i,orig,n,cfg)
    item['calibration']={'success':not cal.get('error') and rec['status']=='0x1','gas_matches':int(cal.get('gasUsed','0x0'),16)==int(rec['gasUsed'],16),'logs_match':collections.Counter(logbag(cal))==collections.Counter(normlogs(rec['logs']))}
    if not all(item['calibration'].values()):raise ValueError('txIndex calibration failed; no candidate tested at guessed state')
    bid=compensation(rec,h,native_delta(cal,h['miner'].lower()));item['benchmark_producer_wei']=str(bid)
    jobs=[(1,C.KEEPERS[1],[],0,m,b'') for m in (1,2,3,4)];fields=[n,int(h['timestamp'],16),int(h['baseFeePerGas'],16)]
    opts=dict(cfg,stateOverrides={D.PROBE:{'code':new}},blockOverrides={'number':h['number'],'time':h['timestamp'],'baseFeePerGas':h['baseFeePerGas'],'gasLimit':h['gasLimit'],'feeRecipient':h['miner'],'prevRandao':h['mixHash']})
    data=C.calldata('checkedMatrix('+D.JOB+'[],uint256,uint256,uint256)',[D.JOB+'[]','uint256','uint256','uint256'],[jobs]+fields)
    call={'from':D.BENEF,'to':D.PROBE,'input':data,'gas':hex(5000000),'gasPrice':'0x0'}
    matrix=trace_call(r,'matrix_%d'%i,call,n,opts)
    if matrix.get('error'):raise ValueError('diagnostic matrix reverted '+str(matrix.get('error')))
    parsed=decode(['(bool,bytes,uint256)[]'],bytes.fromhex(matrix['output'][2:]))[0];good=[];item['matrix']=[]
    for j,(ok,dat,gas) in zip(jobs,parsed):
     row={'mode':j[4],'completed':ok,'gas_diagnostic':gas}
     if ok:
      assert dat[:4].hex()==C.h('Measurement(address,uint256)')[:8];token,cash=decode(['address','uint256'],dat[4:]);assert token==C.WETH
      row.update(native_cash_wei=str(cash),net_diagnostic_wei=str(cash-gas*fields[2]));good.append((cash-gas*fields[2],j))
     else:row['error_data']='0x'+dat.hex()
     item['matrix'].append(row)
    if not good:raise ValueError('all tested exits reverted')
    best=max(good,key=lambda x:x[0])[1];item['selected_mode']=best[4]
    for label,payment,state_index in [('no_bid',0,idx),('equal_visible_compensation',bid,idx),('after_original_control',0,idx+1)]:
     data=C.calldata('checkedExecute('+D.JOB+',uint256,uint256,uint256,uint256)',[D.JOB,'uint256','uint256','uint256','uint256'],[best]+fields+[payment])
     call={'from':D.BENEF,'to':D.PROBE,'input':data,'gas':hex(min(1500000,headroom-30000)),'gasPrice':'0x0'}
     result=trace_call(r,'%s_%d'%(label,i),call,n,dict(opts,txIndex=state_index))
     q={'label':label,'status':'reverted' if result.get('error') else 'completed','gas_used':int(result.get('gasUsed','0x0'),16),'error':result.get('error'),'output':result.get('output')}
     if not result.get('error'):
      token,paid=decode(['address','uint256'],bytes.fromhex(result['output'][2:]));assert token==C.WETH
      assert native_delta(result,D.BENEF)==paid and native_delta(result,h['miner'].lower())==payment
      assert q['gas_used']<=headroom
      q.update(native_payout_wei=str(paid),producer_paid_wei=str(payment),base_fee_cost_wei=str(q['gas_used']*fields[2]),net_after_base_fee_wei=str(paid-q['gas_used']*fields[2]),checked_actual_cash=True)
     item['results'].append(q);save('SUMMARY.json',report|{'alternative_exits':report['alternative_exits']+[item]})
   except Exception as exc:item['error']=repr(exc)
   report['alternative_exits'].append(item);save('SUMMARY.json',report)
   if r.stopped:raise RuntimeError('provider access/rate refusal')
 except Exception as exc:report['error']=repr(exc);report['traceback']=traceback.format_exc()
 report.update(new_requests=r.n if r else 0,heavy_calls=r.new_heavy if r else 0,provider_stopped=r.stopped if r else None)
 save('SUMMARY.json',report);print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
