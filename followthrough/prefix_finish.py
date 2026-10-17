"""Complete frozen tests using canonical prefix replay, preserving blobs.
No balance/storage/oracle changes; actual producer balances checked.
"""
import sys,pathlib,json,hashlib,traceback
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import run as R
from logic import historical_headroom,native_delta,compensation
D=R.D;C=R.C;OUT=C.OUT;OLD_ASCALL=D.ascall

def ascall_with_blobs(t):
 c=OLD_ASCALL(t)
 for k in ('blobVersionedHashes','maxFeePerBlobGas'):
  if t.get(k) is not None:c[k]=t[k]
 return c
D.ascall=ascall_with_blobs

class Runner(R.Client):
 def __init__(self):
  super().__init__();self.context=None
  for p in sorted(pathlib.Path('input_repair/raw').glob('*.json')):
   m=json.loads(p.read_text());raw=p.with_suffix('.body').read_bytes();assert hashlib.sha256(raw).hexdigest()==m['sha256']
   j=json.loads(raw);q=m['payload']
   if m.get('status')=='OK':self.raw_cache[json.dumps([q['method'],q['params']],sort_keys=True)]=j['result']
 def call(self,data,gas=12000000,to=D.PROBE):
  if self.context is not None and data[:10]==C.calldata('execute('+D.JOB+')')[:10]:
   h,bid=self.context;j=D.decode([D.JOB],bytes.fromhex(data[10:]))[0]
   data=C.calldata('checkedExecute('+D.JOB+',uint256,uint256,uint256,uint256)',[D.JOB,'uint256','uint256','uint256','uint256'],[j,int(h['number'],16),int(h['timestamp'],16),int(h['baseFeePerGas'],16),bid])
  return super().call(data,gas,to)

def build_metered():
 base=pathlib.Path('input_repair/ImprovedKeeper.sol').read_text();prior=json.loads(pathlib.Path('input_repair/BUILD.json').read_text())
 assert hashlib.sha256(base.encode()).hexdigest()==prior['source_sha256']
 a='function env() external view returns(uint,uint,uint,uint,uint,uint){return(block.chainid,block.number,block.timestamp,block.basefee,address(this).balance,BENEFICIARY.balance);}'
 b='function env() external view returns(uint,uint,uint,uint,uint,uint,uint){return(block.chainid,block.number,block.timestamp,block.basefee,address(this).balance,BENEFICIARY.balance,block.coinbase.balance);}'
 assert base.count(a)==1;source=base.replace(a,b);(OUT/'ImprovedKeeper.sol').write_text(source)
 inp=json.loads(pathlib.Path('input_repair/compiler_input.json').read_text());inp['sources']={'ImprovedKeeper.sol':{'content':source}};C.save('compiler_input.json',inp)
 R.install_solc('0.8.24');compiled=R.compile_standard(inp,solc_version='0.8.24');C.save('compiler_output.json',compiled)
 runtime='0x'+compiled['contracts']['ImprovedKeeper.sol']['CashProbe']['evm']['deployedBytecode']['object'];(OUT/'runtime.hex').write_text(runtime)
 C.save('BUILD.json',{'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'runtime_sha256':hashlib.sha256(bytes.fromhex(runtime[2:])).hexdigest(),'compiler':'0.8.24','runtime_bytes':(len(runtime)-2)//2,'changed_only_monitoring_view_from_prior':True})
 assert D.decode(['uint256']*6,D.encode(['uint256']*7,list(range(7))))==tuple(range(6))
 return runtime

def one(r,label,h,prefix,receipts,j,runtime,bid):
 r.context=(h,bid);result=r.simulate(label,h,[j],runtime,prefix,receipts,True)
 data=json.loads((OUT/'cases'/f'{label}.json').read_text());cs=data['simulation'][0]['calls']
 before=D.decode(['uint256']*7,bytes.fromhex(cs[-5]['returnData'][2:]));after=D.decode(['uint256']*7,bytes.fromhex(cs[-1]['returnData'][2:]))
 result['producer_payment_wei']=str(after[6]-before[6])
 if result['status']=='0x1':assert after[6]-before[6]==bid
 else:assert after[6]==before[6]
 for row in result.get('rows',[]):row['explicit_competitive_bid_wei']=str(bid)
 result['requested_producer_wei']=str(bid);result['historical_remaining_gas']=historical_headroom(h,receipts)
 assert result['gas_used']<=result['historical_remaining_gas']
 return result

def main():
 OUT.mkdir(exist_ok=True);report={'new_workflow':True,'signed_or_sent':0,'baseline_repairs':[],'alternative_exits':[],'repairs':['preserve blobVersionedHashes and maxFeePerBlobGas in original prefixes','use eth_simulateV1 to verify canonical base fee at zero synthetic gas price','meter actual producer native balance changes'],'limitations':['synthetic gas-price zero; base-fee costs deducted from payout; actual user needs upfront gas','frozen three historical events; route selection is development, not validation','same visible compensation is not the minimum winning bid','counterfactual alternatives are not additive']};r=None
 try:
  C.ALLOWED.update({'eth_simulateV1','debug_traceTransaction','eth_getBlockReceipts'})
  r=Runner();runtime=build_metered();events=json.loads(pathlib.Path('input_repair/PLAN.json').read_text())['selection']
  C.save('PLAN.json',{'selection':events,'four_modes':[1,2,3,4],'full_prefix_with_blob_fields':True,'max_new_heavy_calls':22,'prior_run_preserved':39050314384,'parent_balances_storage_oracles_unchanged':True})
  e=events[0];rec=r.getreceipt(e['transactionHash']);h,p,rr=r.prefix(rec)
  try:
   old=pathlib.Path('input_services/runtime.hex').read_text().strip();r.context=None
   result=r.simulate('repaired_original_0',h,[(1,C.KEEPERS[1],[],0,1,b'')],old,p,rr,True);report['baseline_repairs'].append({'tx':e['transactionHash'],'result':result})
  except Exception as ex:report['baseline_repairs'].append({'tx':e['transactionHash'],'error':repr(ex)})
  C.save('SUMMARY.json',report)
  for i,e in enumerate(events):
   item={'tx':e['transactionHash'],'variants':[],'results':[]}
   try:
    rec=r.getreceipt(e['transactionHash']);h,p,rr=r.prefix(rec)
    orig=r.rpc('winner_trace_'+str(i),'debug_traceTransaction',[e['transactionHash'],{'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True}}]);C.save('traces/winner_%d.json'%i,orig)
    import collections
    assert not orig.get('error') and int(orig['gasUsed'],16)==int(rec['gasUsed'],16)
    assert collections.Counter(R.logbag(orig))==collections.Counter(R.normlogs(rec['logs']))
    bid=compensation(rec,h,native_delta(orig,h['miner'].lower()));item['benchmark_producer_wei']=str(bid);positive=[]
    for mode in (1,2,3,4):
     j=(1,C.KEEPERS[1],[],0,mode,b'')
     try:
      q=one(r,'variant_%d_%d'%(i,mode),h,p,rr,j,runtime,0);q['mode']=mode;item['variants'].append(q)
      if q['status']=='0x1':positive.append((int(q['rows'][0]['net_eth_after_base_fee_wei']),mode))
     except Exception as exc:item['variants'].append({'mode':mode,'error':repr(exc)})
     C.save('SUMMARY.json',report|{'alternative_exits':report['alternative_exits']+[item]})
     if r.stopped:raise RuntimeError('provider access/rate refusal')
    if not positive:raise ValueError('no fully verified alternative cash path')
    best=max(positive)[1];item['selected_mode']=best;j=(1,C.KEEPERS[1],[],0,best,b'')
    item['results'].append(one(r,'equal_bid_%d'%i,h,p,rr,j,runtime,bid))
    full=r.rpc('full_header','eth_getBlockByNumber',[h['number'],True]);ix=int(rec['transactionIndex'],16)
    item['results'].append(one(r,'after_original_%d'%i,h,p+[D.ascall(full['transactions'][ix])],rr+[rec],j,runtime,0))
   except Exception as exc:item['error']=repr(exc)
   report['alternative_exits'].append(item);C.save('SUMMARY.json',report)
   if r.stopped:raise RuntimeError('provider stopped')
 except Exception as exc:report['error']=repr(exc);report['traceback']=traceback.format_exc()
 report.update(new_requests=r.n if r else 0,heavy_calls=r.new_heavy if r else 0,provider_stopped=r.stopped if r else None)
 C.save('SUMMARY.json',report);print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
