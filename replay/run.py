"""Historical economic simulations, never broadcast. Fixed three selected development cases.
Only probe code is overridden; no account funding or production balance/storage/oracle edits.
Original prefix calls retain sender/value/input/fees/access lists. Exact prefix logs/gas/status
must match canonical receipts before a candidate is accepted. Synthetic caller gas is priced later.
"""
from __future__ import annotations
import datetime as dt,hashlib,json,time,urllib.request,urllib.error,traceback
from pathlib import Path
from eth_abi import encode,decode
from Crypto.Hash import keccak
import solcx
ROOT=Path(__file__).resolve().parent;OUT=Path('evidence');OUT.mkdir(exist_ok=True);(OUT/'raw').mkdir(exist_ok=True)
RPC='https://rpc-eth.blockmachine.io';PROBE='0x00000000000000000000000000000000DeaD7711';CALLER='0x00000000000000000000000000000000DeaD7712'
CUST='0x4F95C5bA0C7c69FB2f9340E190cCeE890B3bd87c';USTB='0x00000000564ee6a571C5819057f27bb671E78Bd5';ZERO='0x'+'00'*20
FRX='0xCAcd6fd266aF91b8AeD52aCCc382b4e165586E29';USDC='0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
SEEDS=[
 {'tx':'0xaf532fea7df2fe561ad70e6df0649a946d35955d99906aa6adcd1fc1a07e1194','block':25643399,'index':0,'borrower':'0x0cd7E1660D63a6aEbDA782a2Eb7f2875716aC3E8','seize':1069297004535332906991616},
 {'tx':'0x080504ec2f23ac1754bef172376988e1d9727f4c67d442c6011eba5e2ff27bb6','block':25649158,'index':0,'borrower':'0xFd184b39Cd9152A09c1C895CaFd7efCD93dbbad1','seize':14141111919915761998533},
 {'tx':'0xd47ca9ff33d59af1ff6dd0f2894f749d6799d5ed12f717f667c9c44bb70a2d2b','block':25868888,'index':18,'borrower':'0x860b7Abd16672B33Bab84679526227adb283ed8f','seize':20542000000000000000000}]
COUNT=0;RU=0;LAST=0.;BEG=time.monotonic();STOP=False
ALLOW={'eth_chainId','eth_getBlockByNumber','eth_getTransactionReceipt','eth_getCode','eth_getBalance','eth_call','eth_simulateV1'}
def save(n,x):(OUT/n).write_text(json.dumps(x,indent=2,default=str))
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def selector(s):k=keccak.new(digest_bits=256);k.update(s.encode());return k.digest()[:4]
def data(s,t=(),v=()):return '0x'+(selector(s)+encode(list(t),list(v))).hex()
def rpc(name,method,params,cost=1):
 global COUNT,RU,LAST,STOP
 if method not in ALLOW:raise ValueError('read-only methods only')
 if STOP or COUNT>=110 or RU+cost>180 or time.monotonic()-BEG>720:raise RuntimeError('fixed budget or access stop')
 time.sleep(max(0,2*cost-(time.monotonic()-LAST)));COUNT+=1;RU+=cost
 p={'jsonrpc':'2.0','id':COUNT,'method':method,'params':params};rec={'name':name,'url':RPC,'payload':p,'started_utc':utc(),'estimated_RU':cost};b=b'';r=None
 try:
  req=urllib.request.Request(RPC,json.dumps(p).encode(),{'Content-Type':'application/json','User-Agent':'QT-Wrapper-Cash-Research/1'})
  with urllib.request.urlopen(req,timeout=50) as res:
   rec['http_status']=res.status;b=res.read(12000001)
   if len(b)>12000000:raise ValueError('body cap')
  r=json.loads(b);rec['status']='RPC_ERROR' if 'error'in r else 'OK'
 except urllib.error.HTTPError as e:
  b=e.read(100000);rec.update(status='HTTP_ERROR',http_status=e.code,error=str(e))
  if e.code in (401,403,429):STOP=True
 except Exception as e:rec.update(status='UNAVAILABLE',error=repr(e))
 rec.update(completed_utc=utc(),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b));(OUT/'raw'/f'{COUNT:04d}.body').write_bytes(b);save('raw/'+f'{COUNT:04d}.json',rec);LAST=time.monotonic()
 if STOP:raise RuntimeError('provider denied access/rate; endpoint not retried')
 return r

def val(*a,**kw):
 r=rpc(*a,**kw)
 if not isinstance(r,dict) or 'result' not in r:raise ValueError(str(r)[:800])
 return r['result']
def uintview(n,to,signature,types,args,block):
 r=rpc(n,'eth_call',[{'to':to,'data':data(signature,types,args)},block])
 if isinstance(r,dict) and 'result' in r and len(r['result'])==66:return str(int(r['result'],16))
 return {'unavailable':r}
def compile_probe():
 src=(ROOT/'WrapperCashProbe.sol').read_text();inp={'language':'Solidity','sources':{'W.sol':{'content':src}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.methodIdentifiers','evm.deployedBytecode.object']}}}}
 save('compiler_input.json',inp);solcx.install_solc('0.8.34');out=solcx.compile_standard(inp,solc_version='0.8.34');save('compiler_output.json',out)
 a=out['contracts']['W.sol']['WrapperCashProbe'];sig='execute(address,uint256,uint256,address,uint256)'
 if a['evm']['methodIdentifiers'][sig]!=selector(sig).hex():raise ValueError('ABI mismatch')
 if selector('claimLiquidation(address,address,uint256)').hex()!='d2c744ae':raise ValueError('wrapper interface mismatch with original trace')
 rt='0x'+a['evm']['deployedBytecode']['object'];(OUT/'runtime.hex').write_text(rt)
 return rt,{'compiler':'0.8.34','source_sha256':hashlib.sha256(src.encode()).hexdigest(),'runtime_sha256':hashlib.sha256(bytes.fromhex(rt[2:])).hexdigest(),'compiled':True}
def normlogs(logs):return [(l['address'].lower(),[t.lower() for t in l['topics']],l['data'].lower()) for l in logs]
def ascall(tx):
 c={k:tx[k] for k in ('from','to','value','gas','accessList','authorizationList') if tx.get(k) is not None};c['input']=tx['input']
 if tx.get('maxFeePerGas') is not None:c.update(maxFeePerGas=tx['maxFeePerGas'],maxPriorityFeePerGas=tx.get('maxPriorityFeePerGas','0x0'))
 elif tx.get('gasPrice') is not None:c['gasPrice']=tx['gasPrice']
 return c

def main():
 s={'started_utc':utc(),'transactions_sent':0,'live_profit':False,'source_selection_artifact_sha256':'3299f995dfe19288cf5dedb3be9ffe8c964e3b8ec0b98ded6f13a9531fbf1f0a','cases':[],'limitations':['Retrospective winners and event-sized selection; no prospective discovery or capture rate.','Source interface was corroborated with actual historical traces; no claim of deployed bytecode identity with current source.','eth_simulateV1 validation=false; candidate synthetic caller pays zero gas in simulation, full gas priced separately.','Token payouts are received by the specified research caller, not real earnings.','Returned primitive errors remain unavailable, never zero profit.']}
 try:
  rt,build=compile_probe();s['compile']=build
  if val('chain','eth_chainId',[])!='0x1':raise ValueError('wrong chain')
  for i,e in enumerate(SEEDS):
   case={'seed':e,'variants':[]};s['cases'].append(case)
   try:
    r=val('winner_receipt_'+str(i),'eth_getTransactionReceipt',[e['tx']]);h=val('target_'+str(i),'eth_getBlockByNumber',[hex(e['block']),True],4);p=val('parent_'+str(i),'eth_getBlockByNumber',[hex(e['block']-1),False]);case.update(receipt=r,header=h,parent=p)
    if r['blockHash']!=h['hash'] or int(r['transactionIndex'],16)!=e['index'] or h['transactions'][e['index']]['hash']!=e['tx']:raise ValueError('anchor mismatch')
    if val('unused_probe_'+str(i),'eth_getCode',[PROBE,p['number']])!='0x' or int(val('unfunded_probe_'+str(i),'eth_getBalance',[PROBE,p['number']]),16):raise ValueError('probe not empty')
    if val('unused_caller_'+str(i),'eth_getCode',[CALLER,p['number']])!='0x':raise ValueError('research caller occupied')
    prefix=h['transactions'][:e['index']];canonical=[]
    if len(prefix)>20:raise ValueError('prefix outside frozen cap')
    for j,t in enumerate(prefix):canonical.append(val(f'prefix_receipt_{i}_{j}','eth_getTransactionReceipt',[t['hash']]))
    case['canonical_prefix_receipts']=canonical
    bo={'number':h['number'],'time':h['timestamp'],'gasLimit':h['gasLimit'],'baseFeePerGas':h['baseFeePerGas'],'feeRecipient':h['miner'],'prevRandao':h['mixHash']}
    routes=[('frx_all_LP',ZERO,10000),('usdc_custodian_all_LP',CUST,10000),('usdc_ustb_all_LP',USTB,10000)]
    if i==2:routes.insert(0,('frx_9980_bps_LP_control',ZERO,9980))
    for label,ex,fraction in routes:
     v={'label':label,'exit':ex,'lp_bps':fraction};case['variants'].append(v)
     if ex!=ZERO:
      v['exit_code_present']=val('exit_code_'+str(i)+'_'+label,'eth_getCode',[ex,p['number']])!='0x'
      if not v['exit_code_present']:v['status']='EXIT_NOT_DEPLOYED_AT_PARENT';continue
     ec={'from':CALLER,'to':PROBE,'input':data('environment()'),'gas':hex(200000),'gasPrice':'0x0'}
     call={'from':CALLER,'to':PROBE,'input':data('execute(address,uint256,uint256,address,uint256)',['address','uint256','uint256','address','uint256'],[e['borrower'],e['seize'],fraction,ex,0]),'gas':hex(10000000),'gasPrice':'0x0'}
     payload={'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{PROBE:{'code':rt}},'calls':[ascall(t) for t in prefix]+[ec,call]}],'validation':False,'traceTransfers':False}
     response=rpc('simulate_'+str(i)+'_'+label,'eth_simulateV1',[payload,p['number']],5);v['response']=response
     if not isinstance(response,dict) or not response.get('result'):v['status']='RPC_UNAVAILABLE';continue
     calls=response['result'][0]['calls'];checks=[]
     for a,b in zip(calls[:len(prefix)],canonical):checks.append({'status':a.get('status')==b['status'],'gas':int(a.get('gasUsed','0x0'),16)==int(b['gasUsed'],16),'logs':normlogs(a.get('logs',[]))==normlogs(b['logs'])})
     v['prefix_matches']=checks;v['prefix_verified']=len(checks)==len(prefix) and all(all(z.values()) for z in checks)
     env=calls[-2];expected=(1,e['block'],int(h['timestamp'],16),0)
     v['environment_verified']=env.get('status')=='0x1' and decode(['uint256']*4,bytes.fromhex(env['returnData'][2:]))==expected
     a=calls[-1];v['status']='CANDIDATE_REVERTED'
     if a.get('status')=='0x1':
      w=decode(['uint256']*7,bytes.fromhex(a['returnData'][2:]));v['values']={k:str(n) for k,n in zip(('repaid_frx','lp_received','lp_burned','surplus_frx','usdc_paid','lp_residual','internal_gas'),w)};v['gas_used']=int(a['gasUsed'],16)
      v['status']='CASH_PAID' if ex!=ZERO else 'IN_KIND_ONLY'
      if not(v['prefix_verified'] and v['environment_verified']):v['status']='UNVERIFIED_STATE'
     save('SUMMARY.json',s)
    case['gas_reference']={'winner_gas':int(r['gasUsed'],16),'winner_effective_gas_price':int(r['effectiveGasPrice'],16),'block_base_fee':int(h['baseFeePerGas'],16)}
   except Exception as err:case['error']=repr(err);case['traceback']=traceback.format_exc()
   save('SUMMARY.json',s)
  # Current capacity is a distinct snapshot, not substituted into historical tests.
  latest=val('current','eth_getBlockByNumber',['latest',False]);s['current_cash_exits']={'header':latest,'routes':[]}
  for ex in (CUST,USTB):
   z={'address':ex};s['current_cash_exits']['routes'].append(z)
   for sig,n in [('totalAssets()',0),('previewRedeem(uint256)',1000*10**18)]:z[sig]=uintview('current_'+sig+'_'+ex[:10],ex,sig,[] if n==0 else ['uint256'],[] if n==0 else [n],latest['number'])
   z['direct_USDC_custody']=uintview('USDC_'+ex[:10],USDC,'balanceOf(address)',['address'],[ex],latest['number'])
 except Exception as e:s['error']=repr(e);s['traceback']=traceback.format_exc()
 s.update(completed_utc=utc(),request_count=COUNT,estimated_RU=RU);save('SUMMARY.json',s)
 print(json.dumps({'compile':s.get('compile'),'requests':COUNT,'error':s.get('error'),'cases':[{'seed':c['seed'],'error':c.get('error'),'variants':[{k:v[k] for k in ('label','status','values','gas_used','prefix_verified','environment_verified') if k in v} for v in c['variants']]} for c in s['cases']],'current_cash_exits':s.get('current_cash_exits')},indent=2))
if __name__=='__main__':main()
