"""Two previously selected development events; not fresh opportunity discovery.
Historical read-only calls only. Inserting executor code is the only account override.
Projected calls change block time/number explicitly and verify an environment control.
Canonical prefix simulation is additionally attempted for the selected Aave event.
No private keys, trade sending, account funding or production-storage edits.
"""
import sys,json,time,pathlib,hashlib,datetime,urllib.request,urllib.error
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'phase2'))
from midnight_codec import selector,word,addr,decode_words,bhex,PROBE,CALLER,keccak256
ROOT=pathlib.Path(__file__).resolve().parent
BASE='https://mainnet.base.org';ETH='https://rpc-eth.blockmachine.io'
POOL='0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2';WETH='0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
YO_TX='0x1fadad037540174670a17c198e01277a8c3aaa2b8b541fb37a62555f8013810d'
YO_USER='0x65e4a9ca948ebe0c4c0a65f09a230e5b71ffe530'
ALLOW={'eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call','eth_getLogs','eth_getTransactionReceipt','eth_getTransactionByHash','eth_simulateV1','debug_traceTransaction'}
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class Stop(Exception):pass
class Client:
 def __init__(self,out):self.out=out;out.mkdir(parents=True,exist_ok=True);self.count=0;self.ru=0;self.last=0;self.blocked=set();self.records=[]
 def rpc(self,url,method,params,cost=1):
  if url not in (BASE,ETH) or method not in ALLOW:raise ValueError('not allowlisted')
  if url in self.blocked:raise Stop('endpoint previously refused access/rate')
  if self.count>=80 or self.ru+cost>140:raise Stop('fixed budget exhausted')
  time.sleep(max(0,2*cost-(time.monotonic()-self.last)));self.count+=1;self.ru+=cost
  payload={'jsonrpc':'2.0','id':self.count,'method':method,'params':params};r={'url':url,'payload':payload,'started_utc':utc(),'estimated_RU':cost};body=b'';ret=None
  try:
   req=urllib.request.Request(url,json.dumps(payload).encode(),{'Content-Type':'application/json','User-Agent':'QT-historical-cash-research/1'})
   with urllib.request.urlopen(req,timeout=35) as res:
    r['http_status']=res.status;body=res.read(8_000_001)
    if len(body)>8_000_000:raise ValueError('response size cap')
   ret=json.loads(body)
  except urllib.error.HTTPError as e:
   r['http_status']=e.code;body=e.read(100000);r['error']=str(e)
   if e.code in (401,403,429):self.blocked.add(url)
  except Exception as e:r['error']=repr(e)
  if isinstance(ret,dict) and 'error' in ret:r['provider_error']=ret['error']
  r.update(completed_utc=utc(),sha256=hashlib.sha256(body).hexdigest());p=self.out/f'{self.count:03d}'
  p.with_suffix('.json').write_text(json.dumps(r,indent=2));p.with_suffix('.body').write_bytes(body);self.records.append(r);self.last=time.monotonic()
  if url in self.blocked:raise Stop('access/rate denial; no retry or provider bypass')
  return ret
 def val(self,url,method,params,cost=1):
  r=self.rpc(url,method,params,cost)
  if not isinstance(r,dict) or 'result' not in r:raise ValueError(str(r)[:400])
  return r['result']
def compile_probe():
 import solcx
 out=ROOT/'build';out.mkdir(exist_ok=True);source=(ROOT/'HistoricalCashProbe.sol').read_text()
 status={'compiled':False,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'compiler':'0.8.34'}
 try:
  if '0.8.34' not in {str(v) for v in solcx.get_installed_solc_versions()}:solcx.install_solc('0.8.34')
  inp={'language':'Solidity','sources':{'H.sol':{'content':source}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.deployedBytecode.object','evm.methodIdentifiers']}}}}
  (out/'compiler_input.json').write_text(json.dumps(inp));r=solcx.compile_standard(inp,solc_version='0.8.34');(out/'compiler_output.json').write_text(json.dumps(r))
  a=r['contracts']['H.sol']['HistoricalCashProbe'];rt='0x'+a['evm']['deployedBytecode']['object']
  for sig in ('yo(address,uint256)','aave(address,uint256)','environment()'):
   if a['evm']['methodIdentifiers'][sig]!=selector(sig)[2:]:raise ValueError('ABI mismatch')
  status.update(compiled=True,runtime_sha256=hashlib.sha256(bhex(rt)).hexdigest());(out/'runtime.hex').write_text(rt)
 except Exception as e:status['error']=repr(e);rt=None
 (out/'status.json').write_text(json.dumps(status,indent=2));return rt,status

def outcome(r):
 if isinstance(r,dict) and 'result' in r:
  try:return {'status':'RETURNED','words':[str(x) for x in decode_words(r['result'])]}
  except Exception:return {'status':'UNRECOGNIZED_RETURN'}
 return {'status':'REVERT_OR_UNAVAILABLE','raw':r}
def call_variants(c,url,chain,rt,parent,target,data,label):
 cases=[];P=parent['number'];B=target['number'];T=target['timestamp']
 if c.val(url,'eth_getCode',[PROBE,P])!='0x':raise ValueError('probe occupied')
 override={PROBE:{'code':rt}};env={'from':CALLER,'to':PROBE,'data':selector('environment()'),'gas':hex(1000000)}
 for mode,block,extra,expected in [
  ('parent_time',P,[],[chain,int(P,16),int(parent['timestamp'],16),0]),
  ('parent_state_target_time',P,[{'number':B,'time':T}],[chain,int(B,16),int(T,16),0]),
  ('after_winner_block',B,[],[chain,int(B,16),int(T,16),0])]:
  control=c.rpc(url,'eth_call',[env,block,override]+extra);ok=isinstance(control,dict) and 'result'in control and decode_words(control['result'])==expected
  item={'mode':mode,'environment_control':control,'environment_verified':ok,'label':label}
  if ok:
   result=c.rpc(url,'eth_call',[{'from':CALLER,'to':PROBE,'data':data,'gas':hex(6000000)},block,override]+extra)
   item.update(outcome(result));item['full_response']=result
  cases.append(item)
 return cases

def trace_accounting(tx,receipt,trace):
 actors={tx['from'].lower(),tx['to'].lower()};native=0;weth=0;other={}
 def walk(node):
  nonlocal native
  if not isinstance(node,dict) or node.get('error'):return
  if node.get('type','').upper() in ('CALL','CREATE','CREATE2','SELFDESTRUCT'):
   f=node.get('from','').lower();t=node.get('to','').lower();v=int(node.get('value','0x0'),16)
   native+=v*((t in actors)-(f in actors))
  for ch in node.get('calls',[]):walk(ch)
 walk(trace)
 topic='0x'+keccak256(b'Transfer(address,address,uint256)').hex()
 for log in receipt.get('logs',[]):
  ts=log.get('topics',[])
  if len(ts)!=3 or ts[0].lower()!=topic:continue
  f='0x'+ts[1][-40:].lower();t='0x'+ts[2][-40:].lower();n=int(log['data'],16)*((t in actors)-(f in actors));token=log['address'].lower()
  if token==WETH.lower():weth+=n
  elif n:other[token]=other.get(token,0)+n
 gas=int(receipt['gasUsed'],16)*int(receipt['effectiveGasPrice'],16)
 return {'scope':'sender plus tx.to only; beneficial ownership and external payout ownership unknown','native_net_before_gas':str(native),'weth_transfer_net':str(weth),'sender_gas_wei':str(gas),'eth_plus_weth_after_gas_wei':str(native+weth-gas),'other_token_transfer_deltas':{k:str(v) for k,v in other.items()},'warning':'WETH mint/burn via Deposit/Withdrawal needs separate checking before this becomes a complete consolidated P&L.'}

def main():
 out=ROOT/('public_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(exist_ok=True)
 c=Client(out/'raw');s={'started_utc':utc(),'scope':'Previously selected development anchors only','transactions_sent':0,'live_profit':False,'warnings':['Historical parent-time scenarios are not exact intra-block state.','No capture probability or recurrence is estimated.','Projected calls explicitly change only block number/time plus executor code.','Realised sender gas is not our simulated gas.']}
 try:rt,status=compile_probe();s['compile']=status
 except Exception as e:rt=None;s['compile']={'compiled':False,'error':repr(e)}
 if rt:
  try:
   if c.val(BASE,'eth_chainId',[])!='0x2105':raise ValueError('wrong Base chain')
   receipt=c.val(BASE,'eth_getTransactionReceipt',[YO_TX]);b=c.val(BASE,'eth_getBlockByNumber',[receipt['blockNumber'],False]);p=c.val(BASE,'eth_getBlockByNumber',[hex(int(b['number'],16)-1),False])
   if int(b['number'],16)!=51840855 or int(b['timestamp'],16)!=1790471057:raise ValueError('yoUSD historical anchor mismatch')
   data=selector('yo(address,uint256)')+(addr(YO_USER)+word(7025200000)).hex()
   s['yo']={'block':b,'receipt':receipt,'cases':call_variants(c,BASE,8453,rt,p,b,data,'yoUSD historical')}
  except Exception as e:s['yo_error']=repr(e)
  try:
   if c.val(ETH,'eth_chainId',[])!='0x1':raise ValueError('wrong Ethereum chain')
   topic='0x'+keccak256(b'LiquidationCall(address,address,address,uint256,uint256,address,bool)').hex();asset='0x'+addr(WETH).hex();B=25832491
   logs=c.val(ETH,'eth_getLogs',[{'fromBlock':hex(B),'toBlock':hex(B),'address':POOL,'topics':[topic,asset,asset]}],5)
   s['aave_logs']=logs
   if not logs:raise ValueError('selected same-asset event not returned')
   log=sorted(logs,key=lambda l:int(l['logIndex'],16))[0];words=decode_words(log['data']);user='0x'+log['topics'][3][-40:];repay=words[0]
   receipt=c.val(ETH,'eth_getTransactionReceipt',[log['transactionHash']]);tx=c.val(ETH,'eth_getTransactionByHash',[log['transactionHash']]);b=c.val(ETH,'eth_getBlockByNumber',[hex(B),True],6);p=c.val(ETH,'eth_getBlockByNumber',[hex(B-1),False])
   s['aave']={'borrower':user,'observed_repaid':str(repay),'observed_collateral':str(words[1]),'receiveAToken':words[3],'receipt':receipt,'tx':tx,'block':b,'parent':p}
   if words[3]!=0:raise ValueError('event requested aToken, not selected underlying case')
   data=selector('aave(address,uint256)')+(addr(user)+word(repay)).hex()
   s['aave']['cases']=call_variants(c,ETH,1,rt,p,b,data,'Aave same asset historical')
   # Add actual preceding calls before our alternative executor. Validate prefix logs.
   prefix=b['transactions'][:int(log['transactionIndex'],16)]
   s['aave']['prefix_tx_count']=len(prefix)
   if len(prefix)<=8:
    calls=[];canonical=[]
    for t in prefix:
     call={k:t[k] for k in ('from','to','value','gas') if t.get(k) is not None};call['input']=t['input']
     if t.get('maxFeePerGas') is not None:
      call['maxFeePerGas']=t['maxFeePerGas'];call['maxPriorityFeePerGas']=t['maxPriorityFeePerGas']
     elif t.get('gasPrice') is not None:call['gasPrice']=t['gasPrice']
     calls.append(call);canonical.append(c.val(ETH,'eth_getTransactionReceipt',[t['hash']]))
    calls.append({'from':CALLER,'to':PROBE,'input':data,'gas':hex(6000000)})
    bo={'number':b['number'],'time':b['timestamp'],'gasLimit':b['gasLimit'],'baseFeePerGas':b['baseFeePerGas'],'feeRecipient':b['miner'],'prevRandao':b['mixHash']}
    payload={'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{PROBE:{'code':rt}},'calls':calls}],'validation':False,'traceTransfers':False}
    result=c.rpc(ETH,'eth_simulateV1',[payload,p['number']]);s['aave']['prefix_simulation']=result;s['aave']['canonical_prefix_receipts']=canonical
   result=c.rpc(ETH,'debug_traceTransaction',[log['transactionHash'],{'tracer':'callTracer','timeout':'20s'}],30)
   s['aave']['winner_trace']=result
   if isinstance(result,dict) and isinstance(result.get('result'),dict):s['aave']['winner_scoped_accounting']=trace_accounting(tx,receipt,result['result'])
  except Exception as e:s['aave_error']=repr(e)
 s.update(completed_utc=utc(),request_count=c.count,estimated_RU=c.ru)
 (out/'SUMMARY.json').write_text(json.dumps(s,indent=2))
 small={'started_utc':s['started_utc'],'completed_utc':s['completed_utc'],'requests':c.count,'compile':s.get('compile'),'yo_error':s.get('yo_error'),'aave_error':s.get('aave_error'),'yo_cases':s.get('yo',{}).get('cases'),'aave_cases':s.get('aave',{}).get('cases'),'aave_winner_accounting':s.get('aave',{}).get('winner_scoped_accounting')}
 print(json.dumps(small,indent=2));print('Evidence',out)
if __name__=='__main__':main()
