"""Complete historical cash-path tests. Requires the completed PR26 census.
Only public reads and eth_simulateV1. No wallet, signing or transaction sending.
"""
import sys,json,hashlib,pathlib,time,datetime,traceback,collections,os
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import angles.census as C
from eth_abi import encode,decode
from solcx import install_solc,compile_standard
OUT=C.OUT; IN=pathlib.Path('input_census')
PROBE='0x00000000000000000000000000000000dead8822'; BENEF='0x00000000000000000000000000000000dead8821'
JOB='(uint256,address,uint256[],uint256,uint256,bytes)'
TOKEN_LIST=[C.WETH,C.STETH,'0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0','0xae78736cd615f374d3085123a210448e74fc6393','0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48','0xdac17f958d2ee523a2206206994597c13d831ec7']
TRANSFER='0x'+C.h('Transfer(address,address,uint256)')
TROVE='0x'+C.h('TroveOperation(uint256,uint8,uint256,uint256,uint256,int256,uint256,int256)')
def load(name):return json.loads((IN/name).read_text())
def normlogs(x):return [(v['address'].lower(),[t.lower() for t in v['topics']],v['data'].lower()) for v in x]
def ascall(t):
 r={k:t[k] for k in ('from','to','value','gas','accessList','authorizationList') if t.get(k) is not None};r['input']=t['input']
 if t.get('maxFeePerGas') is not None:r.update(maxFeePerGas=t['maxFeePerGas'],maxPriorityFeePerGas=t.get('maxPriorityFeePerGas','0x0'))
 elif t.get('gasPrice') is not None:r['gasPrice']=t['gasPrice']
 return r

def compile_probe():
 s=pathlib.Path('angles_probe/CashProbe.sol').read_text()
 old='function approve(address t,address s,uint a) internal{require(Token(t).approve(s,0),"approve0");require(Token(t).approve(s,a),"approve");}'
 new='function optionalReturn(address t,bytes memory d) internal{bytes memory r=raw(t,d,0);require(r.length==0||abi.decode(r,(bool)),"token operation");}\n function approve(address t,address s,uint a) internal{optionalReturn(t,abi.encodeWithSignature("approve(address,uint256)",s,0));optionalReturn(t,abi.encodeWithSignature("approve(address,uint256)",s,a));}'
 assert s.count(old)==1;s=s.replace(old,new)
 old='require(Token(t).transfer(BENEFICIARY,n),"payout");'
 assert s.count(old)==1;s=s.replace(old,'optionalReturn(t,abi.encodeWithSignature("transfer(address,uint256)",BENEFICIARY,n));')
 (OUT/'CashProbe.sol').write_text(s)
 inp={'language':'Solidity','sources':{'CashProbe.sol':{'content':s}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.deployedBytecode.object']}}}}
 C.save('compiler_input.json',inp);install_solc('0.8.24');out=compile_standard(inp,solc_version='0.8.24');C.save('compiler_output.json',out)
 ct=out['contracts']['CashProbe.sol']['CashProbe'];runtime='0x'+ct['evm']['deployedBytecode']['object'];(OUT/'runtime.hex').write_text(runtime)
 assert len(runtime)//2-1<24576
 funcs={x['name'] for x in ct['abi'] if x.get('type')=='function'};assert {'matrix','execute','env','balances'}<=funcs
 C.save('BUILD.json',{'source_sha256':hashlib.sha256(s.encode()).hexdigest(),'runtime_sha256':hashlib.sha256(bytes.fromhex(runtime[2:])).hexdigest(),'compiler':'0.8.24','runtime_bytes':len(runtime)//2-1,'optional_return_token_fix':True})
 return runtime

class Runner(C.Client):
 def __init__(self):
  super().__init__();self.raw_cache={};self.receipts={};self.heavy=0
  for p in sorted((IN/'raw').glob('*.json')):
   m=json.loads(p.read_text());bp=p.with_suffix('.body');raw=bp.read_bytes();assert hashlib.sha256(raw).hexdigest()==m['sha256']
   if m.get('status')=='OK':
    j=json.loads(raw);payload=m['payload'];self.raw_cache[json.dumps([payload['method'],payload['params']],sort_keys=True)]=j['result']
    if payload['method']=='eth_getBlockByNumber' and isinstance(j['result'],dict):self.cache[str(int(j['result']['number'],16))]=j['result']
  for r in load('SERVICE_RECEIPTS.json') if (IN/'SERVICE_RECEIPTS.json').exists() else []:
   if r and r.get('blockNumber'):self.receipts[r['transactionHash']]=r
  self.cached_uses=[]
 def rpc(self,name,method,params):
  k=json.dumps([method,params],sort_keys=True)
  if k in self.raw_cache:
   self.cached_uses.append({'name':name,'method':method,'params':params});C.save('CACHE_USED.json',self.cached_uses);return self.raw_cache[k]
  if method in ('eth_simulateV1','debug_traceTransaction'):
   time.sleep(max(0,70-(time.monotonic()-self.last)));self.heavy+=1
  return super().rpc(name,method,params)
 def getreceipt(self,tx):
  if tx not in self.receipts:self.receipts[tx]=self.rpc('receipt','eth_getTransactionReceipt',[tx])
  return self.receipts[tx]
 def prefix(self,rec):
  n=int(rec['blockNumber'],16);b=self.rpc('full_header','eth_getBlockByNumber',[hex(n),True]);idx=int(rec['transactionIndex'],16)
  assert b['hash']==rec['blockHash'] and b['transactions'][idx]['hash']==rec['transactionHash']
  ts=b['transactions'][:idx]
  all_receipts=self.rpc('block_receipts','eth_getBlockReceipts',[hex(n)])
  byhash={x['transactionHash']:x for x in all_receipts};rr=[byhash[t['hash']] for t in ts]
  return b,[ascall(t) for t in ts],rr
 def call(self,data,gas=12000000,to=PROBE):return {'from':BENEF,'to':to,'input':data,'gas':hex(gas),'gasPrice':'0x0'}
 def simulate(self,label,header,jobs,runtime,prefix=None,receipts=None,single=False):
  n=int(header['number'],16);parent=self.head(n-1);assert parent['hash']==header['parentHash'];prefix=prefix or [];receipts=receipts or []
  env=self.call(C.calldata('env()'),100000);bal=self.call(C.calldata('balances(address[])',['address[]'],[TOKEN_LIST]),250000)
  data=C.calldata('execute('+JOB+')',[JOB],[jobs[0]]) if single else C.calldata('matrix('+JOB+'[])',[JOB+'[]'],[jobs])
  calls=prefix+[env,bal,self.call(data,24000000),bal,env]
  bo={'number':header['number'],'time':header['timestamp'],'gasLimit':header['gasLimit'],'baseFeePerGas':header['baseFeePerGas'],'feeRecipient':header['miner'],'prevRandao':header['mixHash']}
  p={'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{PROBE:{'code':runtime}},'calls':calls}],'validation':False,'traceTransfers':False}
  r=self.rpc(label,'eth_simulateV1',[p,parent['number']]);C.save('cases/'+label+'.json',{'header':header,'jobs':[(x[:5]+(x[5].hex(),)) for x in jobs],'prefix_receipts':receipts,'simulation':r})
  cs=r[0]['calls'];assert len(cs)==len(calls)
  for actual,canonical in zip(cs[:len(prefix)],receipts):
   assert actual.get('status')==canonical['status'] and int(actual['gasUsed'],16)==int(canonical['gasUsed'],16) and normlogs(actual.get('logs',[]))==normlogs(canonical['logs']),'original prefix mismatch'
  a,bb,trade,ba,z=cs[-5:]
  ev=decode(['uint256']*6,bytes.fromhex(a['returnData'][2:]));after=decode(['uint256']*6,bytes.fromhex(z['returnData'][2:]));initial=decode(['uint256[]'],bytes.fromhex(bb['returnData'][2:]))[0];terminal=decode(['uint256[]'],bytes.fromhex(ba['returnData'][2:]))[0]
  assert ev[:4]==(1,n,int(header['timestamp'],16),int(header['baseFeePerGas'],16)) and after[:4]==ev[:4]
  assert ev[4:]==(0,0) and all(v==0 for v in initial),'research address initially funded'
  out={'label':label,'block':n,'timestamp':ev[2],'mode':'complete_single' if single else 'reset_matrix','environment_verified':True,'prefix_count':len(prefix),'prefix_exact_match':True,'status':trade.get('status'),'gas_used':int(trade.get('gasUsed','0x0'),16),'initial_tokens':list(initial),'terminal_tokens':list(terminal),'beneficiary_eth_delta':after[5]-ev[5],'rows':[]}
  if trade.get('status')!='0x1':out['error']=trade.get('error');assert list(initial)==list(terminal) and after[4:]==ev[4:];out['rollback_verified']=True;return out
  if single:
   token,amount=decode(['address','uint256'],bytes.fromhex(trade['returnData'][2:]));row={'cash_token':token,'cash_raw':str(amount),'gas_used':out['gas_used'],'base_fee_cost_wei':str(out['gas_used']*ev[3]),'explicit_competitive_bid_wei':'0'}
   if token==C.WETH:assert out['beneficiary_eth_delta']==amount;row['net_eth_after_base_fee_wei']=str(amount-out['gas_used']*ev[3])
   else:
    paid=sum(int(v['data'],16) for v in trade.get('logs',[]) if v['address'].lower()==token and len(v['topics'])==3 and v['topics'][0].lower()==TRANSFER and '0x'+v['topics'][1][-40:].lower()==PROBE and '0x'+v['topics'][2][-40:].lower()==BENEF)
    assert paid==amount;row['cash_transfer_verified']=True
   assert after[4]==0 and all(v<=2 if TOKEN_LIST[i]==C.STETH else v==0 for i,v in enumerate(terminal));out['rows']=[row]
  else:
   vals=decode(['(bool,bytes,uint256)[]'],bytes.fromhex(trade['returnData'][2:]))[0];assert len(vals)==len(jobs)
   for j,(ok,d,gas) in zip(jobs,vals):
    row={'kind':j[0],'target':j[1],'ids':j[2],'input_raw':str(j[3]),'exit_mode':j[4],'completed_cash_path':ok,'subcall_gas':gas,'error_data':'0x'+d.hex() if not ok else None}
    if ok:
     assert d[:4].hex()==C.h('Measurement(address,uint256)')[:8];tok,paid=decode(['address','uint256'],d[4:]);row.update(cash_token=tok,cash_raw=str(paid))
    elif d[:4].hex()==C.h('CashShortfall(uint256,uint256)')[:8]:
     avail,required=decode(['uint256','uint256'],d[4:]);row.update(failure='principal_not_covered',available_raw=str(avail),required_raw=str(required),shortfall_raw=str(required-avail))
    elif d[:4].hex()==C.h('NoReward()')[:8]:row['failure']='no_cash_reward'
    out['rows'].append(row)
   assert after[4:]==ev[4:] and tuple(terminal)==tuple(initial),'matrix did not reset';out['rollback_verified']=True
  return out

def run():
 OUT.mkdir(exist_ok=True);s={'new_remote_run':True,'signed_or_sent':0,'standalone_market_profit_verified':False,'stage':os.environ.get('QT_STAGE','services'),'results':[],'scope':'21 daily ARM states plus deterministically selected original reward-event states; no assumed opportunity count from samples'}
 try:
  summary=load('SUMMARY.json');assert summary['log_window_complete'];r=Runner();C.ALLOWED.update({'eth_simulateV1','debug_traceTransaction','eth_getBlockReceipts'});runtime=compile_probe()
  a=int(load('BOUNDARIES.json')['first']['number'],16)
  assert r.rpc('probe_no_code','eth_getCode',[PROBE,hex(a)])=='0x';assert r.rpc('beneficiary_no_code','eth_getCode',[BENEF,hex(a)])=='0x'
  liqs=load('liquity_events.json');pks=load('keeper_events.json');selection=[]
  for family,events,targets,maxn in [('keeper',pks,C.KEEPERS[:2],3),('liquity',liqs,C.TMS,3)]:
   for target in targets:
    rows=sorted({x['transactionHash']:x for x in events if x['address'].lower()==target}.values(),key=lambda x:(int(x['blockNumber'],16),int(x['transactionIndex'],16)))
    inds=sorted(set([0,len(rows)//2,len(rows)-1])) if rows else []
    for i in inds[:maxn]:selection.append({'family':family,'target':target,'tx':rows[i]['transactionHash'],'available_event_count':len(rows)})
  C.save('EXECUTION_PLAN.json',{'original_events':selection,'arm_dates':[datetime.datetime.fromtimestamp(C.START+i*86400,datetime.timezone.utc).isoformat() for i in range(21)],'arm_inputs_ETH':['0.1','1','10','100'],'arm_exit_modes':['Origin ARM','same Curve pool reverse comparator'],'state_sampling':'first real block at/after 12:00 UTC each day; snapshots not an intraday census','raw_input_hash_count':len(r.raw_cache),'max_seconds':3300,'recipient':BENEF,'probe':PROBE,'quote_only':False})
  for k,item in enumerate(selection if s['stage']=='services' else []):
   try:
    rec=r.getreceipt(item['tx']);header,prefix,recs=r.prefix(rec);target=item['target'];ids=[]
    if item['family']=='liquity':
     for l in rec['logs']:
      if l['address'].lower()==target and l['topics'][0].lower()==TROVE and int(l['data'][2:66],16)==5:ids.append(int(l['topics'][1],16))
     assert ids,'no liquidation trove IDs'
    jobs=[(1 if item['family']=='keeper' else 2,target,ids,0,0,b'')]
    if item['family']=='liquity' and target!=C.TMS[0]:jobs.append((2,target,ids,0,1,b''))
    out=r.simulate('service_%02d_matrix'%k,header,jobs,runtime,prefix,recs);out['selection']=item;s['results'].append(out);C.save('SUMMARY.json',s)
    positive=[(j,v) for j,v in zip(jobs,out['rows']) if v.get('completed_cash_path')]
    if positive:
     best=max(positive,key=lambda x:int(x[1]['cash_raw']))[0]
     one=r.simulate('service_%02d_payout'%k,header,[best],runtime,prefix,recs,True);one['selection']=item;s['results'].append(one);C.save('SUMMARY.json',s)
     if k<3 or item['family']=='liquity':
      try:tr=r.rpc('winner_trace','debug_traceTransaction',[item['tx'],{'tracer':'callTracer','timeout':'25s'}]);C.save('traces/'+item['tx']+'.json',{'trace':tr,'receipt':rec,'header':header})
      except Exception as e:s.setdefault('trace_errors',[]).append({'tx':item['tx'],'error':repr(e)})
   except Exception as e:s.setdefault('execution_errors',[]).append({'case':item,'error':repr(e)})
   if r.stopped:raise RuntimeError('provider stopped')
  for day in (range(21) if s['stage']=='arm' else []):
   try:
    n=r.first(C.START+day*86400+12*3600);header=r.head(n);jobs=[(0,C.ARM,[],q,mode,b'') for q in [10**17,10**18,10**19,10**20] for mode in [0,1]]
    out=r.simulate('arm_day_%02d'%day,header,jobs,runtime);s['results'].append(out);C.save('SUMMARY.json',s)
    positive=[(j,v) for j,v in zip(jobs,out['rows']) if v.get('completed_cash_path')]
    if positive:
     best=max(positive,key=lambda x:int(x[1]['cash_raw']))[0]
     one=r.simulate('arm_day_%02d_payout'%day,header,[best],runtime,single=True);s['results'].append(one);C.save('SUMMARY.json',s)
   except Exception as e:s.setdefault('execution_errors',[]).append({'arm_day':day,'error':repr(e)})
   if r.stopped:raise RuntimeError('provider stopped')
  s['all_planned_states_attempted']=True
 except Exception as e:s['exception']=repr(e);s['traceback']=traceback.format_exc()
 s.update(requests=r.n if 'r' in locals() else 0,heavy_calls=r.heavy if 'r' in locals() else 0,provider_stopped=r.stopped if 'r' in locals() else None);C.save('SUMMARY.json',s);print(json.dumps(s,indent=2),flush=True)
if __name__=='__main__':run()
