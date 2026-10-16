"""Read-only frxUSD size, later-date and displacement research.
Every amount/date resets to canonical state. No keys, signing or transactions.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
import traceback
import urllib.error
import urllib.request
RPC='https://rpc-eth.blockmachine.io'
SOURCE='https://raw.githubusercontent.com/zhangsherwin-bit/qt-rpc-sandbox/75b67d7efbd6c96920872075f3c093f0c5ecb842/standalone/ConversionProbe.sol'
SOURCE_SHA='260aa95cc1dbb42b29b6c3d9c3d544d99428037e9d3bc814c6be25dffb0eff9b'
RUNTIME_SHA='d09a975447d21d41e9a459bdae81d93e4f145f390695d922723b3c388d1d342e'
PROBE='0x00000000000000000000000000000000DeaD7714'
CALLER='0x00000000000000000000000000000000DeaD7712'
USDC='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
MORPHO='0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb'
STABLE='0x13e12bb0e6a2f1a3d6901a59a9d585e89a6243e1'
TRI='0x4ebdf703948ddcea3b11f675b4d1fba9d2414a14'
REDEEM='0x00000000564ee6a571c5819057f27bb671e78bd5'
TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
SEEDS=[
 {'label':'discovery_Jul30','block':25643399,'hash':'0x61212afaf0084a1ef50a718ef4b49032bc2f979eadc465f574ecab626d90100a','tx':'0xaf532fea7df2fe561ad70e6df0649a946d35955d99906aa6adcd1fc1a07e1194'},
 {'label':'later_Jul31','block':25649158,'hash':'0x576760295c2273beb26e8f99610fb1327c4d2d07a110b3aac8c27d3b77e39e30','tx':'0x080504ec2f23ac1754bef172376988e1d9727f4c67d442c6011eba5e2ff27bb6'},
 {'label':'later_Aug30','block':25868888,'hash':'0xaafc315bc10ae5c0203951eb23cc08d265b4ca2712fd1b58410602612d3720c6','tx':'0xd47ca9ff33d59af1ff6dd0f2894f749d6799d5ed12f717f667c9c44bb70a2d2b'},
]
SIZES=(500,5000,20000,50000)
RESERVE=200_000_000_000_000
MINIMUM=1_000_000
ALLOWED={'eth_chainId','eth_getBlockByNumber','eth_getTransactionReceipt','eth_getCode','eth_simulateV1','eth_getLogs','debug_traceTransaction'}
OUT=Path('evidence');COUNT=0;STOP=False;LAST=0.0;START=time.monotonic()
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def save(name,obj):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2),encoding='utf-8')
def words(raw,n):
 if not isinstance(raw,str) or not raw.startswith('0x') or len(raw)!=2+64*n:raise ValueError('unexpected fixed-width return')
 return tuple(int(raw[2+i*64:2+(i+1)*64],16) for i in range(n))
def encode_uints(selector,*args):
 if len(selector)!=8 or any(type(x)!=int or x<0 or x>=2**256 for x in args):raise ValueError('invalid uint argument')
 return '0x'+selector+''.join(format(x,'064x') for x in args)
def rpc(name,method,params):
 global COUNT,STOP,LAST
 if method not in ALLOWED:raise ValueError('write or unapproved method')
 if STOP or COUNT>=100 or time.monotonic()-START>1350:raise RuntimeError('budget/access stop')
 gap=70 if method in ('eth_simulateV1','debug_traceTransaction') else 1.0
 time.sleep(max(0,gap-(time.monotonic()-LAST)))
 COUNT+=1;payload={'jsonrpc':'2.0','id':COUNT,'method':method,'params':params};m={'name':name,'url':RPC,'payload':payload,'started_utc':utc()};b=b'';r=None
 try:
  req=urllib.request.Request(RPC,json.dumps(payload).encode(),{'Content-Type':'application/json','User-Agent':'QT-ReadOnly-FrxUSD-Falsification/1'})
  with urllib.request.urlopen(req,timeout=55) as response:m['http_status']=response.status;b=response.read(12_000_001)
  if len(b)>12_000_000:raise ValueError('body cap')
  r=json.loads(b);m['status']='RPC_ERROR' if 'error' in r else 'OK'
  if 'error' in r:
   msg=str(r['error']).lower()
   if any(x in msg for x in ('rate limit','unauthorized','api key required','quota exceeded')):STOP=True
 except urllib.error.HTTPError as e:
  b=e.read(100_000);m.update(status='HTTP_ERROR',http_status=e.code,error=str(e))
  if e.code in (401,403,429):STOP=True
 except Exception as e:m.update(status='UNAVAILABLE',error=repr(e))
 LAST=time.monotonic();m.update(completed_utc=utc(),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b));(OUT/'raw').mkdir(parents=True,exist_ok=True);(OUT/'raw'/f'{COUNT:04d}.body').write_bytes(b);save(f'raw/{COUNT:04d}.json',m)
 if STOP:raise RuntimeError('provider denied access/rate; stop without retry or alternate endpoint')
 return r

def val(*args):
 r=rpc(*args)
 if not isinstance(r,dict) or r.get('result') is None:raise ValueError('RPC result unavailable: '+str(r)[:300])
 return r['result']

def build():
 import solcx
 with urllib.request.urlopen(urllib.request.Request(SOURCE,headers={'User-Agent':'QT-Pinned-Source-Research/1'}),timeout=30) as r:b=r.read(60_001)
 if hashlib.sha256(b).hexdigest()!=SOURCE_SHA:raise ValueError('source mismatch')
 (OUT/'ConversionProbe.sol').write_bytes(b)
 inp={'language':'Solidity','sources':{'C.sol':{'content':b.decode()}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.methodIdentifiers','evm.deployedBytecode.object']}}}}
 solcx.install_solc('0.8.34');ob=solcx.compile_standard(inp,solc_version='0.8.34');save('compiler_input.json',inp);save('compiler_output.json',ob)
 c=ob['contracts']['C.sol']['ConversionProbe'];code=c['evm']['deployedBytecode']['object']
 if hashlib.sha256(bytes.fromhex(code)).hexdigest()!=RUNTIME_SHA:raise ValueError('runtime mismatch')
 if c['evm']['methodIdentifiers']['execute(uint256,uint256,uint256)']!='2d29a47b' or c['evm']['methodIdentifiers']['environment()']!='74e2b63c':raise ValueError('ABI mismatch')
 (OUT/'runtime.hex').write_text('0x'+code);return '0x'+code

def token_transfers(logs,token):
 out=[]
 for l in logs:
  t=l.get('topics',[])
  if l.get('address','').lower()==token.lower() and len(t)==3 and t[0].lower()==TRANSFER:
   out.append(('0x'+t[1][-40:].lower(),'0x'+t[2][-40:].lower(),int(l['data'],16)))
 return out

def evaluate(calls,header,principal):
 if len(calls)!=3 or calls[0].get('status')!='0x1' or calls[2].get('status')!='0x1':raise ValueError('environment call failed')
 before=words(calls[0]['returnData'],9);after=words(calls[2]['returnData'],9)
 if before[:3]!=(1,int(header['number'],16),int(header['timestamp'],16)) or before[3:]!=(0,0,0,0,0,0):raise ValueError('wrong or funded environment')
 t=calls[1];d={'status':t['status'],'gas_used':int(t['gasUsed'],16),'environment_verified':True}
 if t['status']!='0x1':
  if after!=before:raise ValueError('revert did not roll back')
  d.update(error=t.get('error'),rollback_verified=True,paid_cash_raw=None);return d
 v=words(t['returnData'],6)
 if after[:3]!=before[:3] or after[3:7]!=(0,0,0,0) or after[7]!=v[4] or after[8]!=v[3]:raise ValueError('terminal balances mismatch')
 if v[0]!=principal or v[1]-v[2]!=v[3] or v[3]<MINIMUM or v[4]!=RESERVE:raise ValueError('cash accounting mismatch')
 flows=token_transfers(t.get('logs',[]),USDC)
 incoming=sum(q for a,b,q in flows if a==MORPHO.lower() and b==PROBE.lower())
 repayment=sum(q for a,b,q in flows if a==PROBE.lower() and b==MORPHO.lower())
 payout=sum(q for a,b,q in flows if a==PROBE.lower() and b==CALLER.lower())
 if (incoming,repayment,payout)!=(principal,principal,v[3]):raise ValueError('USDC transfer reconciliation failed')
 burn=d['gas_used']*int(header['baseFeePerGas'],16)
 d.update(loan_raw=str(v[0]),gross_cash_raw=str(v[1]),reserve_purchase_raw=str(v[2]),paid_cash_raw=str(v[3]),frx_redeemed_raw=str(v[5]),native_reserve_wei=str(v[4]),base_fee_cost_wei=str(burn),reserve_covers_base_fee=RESERVE>=burn,unvalued_native_after_base_fee_wei=str(RESERVE-burn),cash_and_repayment_verified=True)
 return d

def simulate(seed,offset,usd,runtime,headers):
 target=seed['block']+offset
 if target not in headers:headers[target]=val('header_'+str(target),'eth_getBlockByNumber',[hex(target),False])
 if target-1 not in headers:headers[target-1]=val('header_'+str(target-1),'eth_getBlockByNumber',[hex(target-1),False])
 h,p=headers[target],headers[target-1]
 if h['parentHash']!=p['hash']:raise ValueError('header ancestry mismatch')
 principal=usd*10**6
 env={'from':CALLER,'to':PROBE,'input':'0x74e2b63c','gas':hex(200_000),'gasPrice':'0x0'}
 trade={'from':CALLER,'to':PROBE,'input':encode_uints('2d29a47b',principal,RESERVE,MINIMUM),'gas':hex(10_000_000),'gasPrice':'0x0'}
 bo={'number':h['number'],'time':h['timestamp'],'gasLimit':h['gasLimit'],'baseFeePerGas':h['baseFeePerGas'],'feeRecipient':h['miner'],'prevRandao':h['mixHash']}
 payload={'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{PROBE:{'code':runtime}},'calls':[env,trade,env]}],'validation':False,'traceTransfers':False}
 case={'event':seed['label'],'principal_USDC':usd,'offset_blocks':offset,'parent':p,'target':h,'actual_unused_block_gas':int(h['gasLimit'],16)-int(h['gasUsed'],16),'seconds_after_trigger':int(h['timestamp'],16)-int(headers[seed['block']]['timestamp'],16),'explicit_bid_wei':'0'}
 r=rpc(f"sim_{seed['label']}_{offset}_{usd}",'eth_simulateV1',[payload,p['number']]);case['response']=r
 if not isinstance(r,dict) or not r.get('result'):
  case['unavailable']=True;return case
 case.update(evaluate(r['result'][0]['calls'],h,principal));case['minimum_displaced_gas']=max(0,case['gas_used']-case['actual_unused_block_gas'])
 return case

def plan():
 return {'scope':'unchanged original route; eight amount/state cases around ONE discovery event plus two later previously selected wrapper events; NOT prospective holdout','sizes_USDC':list(SIZES),'discovery_offsets':[1,2],'later_events_size_USDC':20000,'later_offsets':[1],'events':SEEDS,'reserve_wei':str(RESERVE),'minimum_cash_raw':str(MINIMUM),'simulation_calls':10,'source_url':SOURCE,'source_sha256':SOURCE_SHA,'runtime_sha256':RUNTIME_SHA,'request_limit':100,'time_budget_seconds':1350,'additional_trace_rule':'first two next-block transactions touching the fixed stable pool, sorted by transaction index; no selection on cash outcome','no_production_storage_or_balance_overrides':True,'no_signing_or_transactions':True,'fixed_historical_dates_avoid_reserved_Oct3_Oct9':True}

def main():
 OUT.mkdir(exist_ok=True);save('PLAN.json',plan());s={'started_utc':utc(),'plan':plan(),'transactions_sent':0,'live_profit':False,'cases':[],'selected_pool_transactions':[]}
 try:
  runtime=build();assert val('chain','eth_chainId',[])=='0x1';headers={}
  for seed in SEEDS:
   h=val('anchor_'+seed['label'],'eth_getBlockByNumber',[hex(seed['block']),False]);assert h['hash']==seed['hash'];headers[seed['block']]=h
   rec=val('trigger_receipt_'+seed['label'],'eth_getTransactionReceipt',[seed['tx']]);assert rec['blockHash']==h['hash'] and rec['status']=='0x1';save('triggers/'+seed['label']+'.json',{'header':h,'receipt':rec})
   for who,address in [('probe',PROBE),('caller',CALLER)]:assert val(who+'_code_'+seed['label'],'eth_getCode',[address,h['number']])=='0x'
  bn=SEEDS[0]['block']+1
  poollogs=val('next_block_route_logs','eth_getLogs',[{'fromBlock':hex(bn),'toBlock':hex(bn),'address':[STABLE,TRI,REDEEM]}]);save('pool_logs.json',poollogs)
  txs=[]
  for l in sorted(poollogs,key=lambda x:(int(x['transactionIndex'],16),int(x['logIndex'],16))):
   if l['address'].lower()==STABLE.lower() and l['transactionHash'] not in txs:txs.append(l['transactionHash'])
  s['route_log_transactions_total']=len(set(x['transactionHash'] for x in poollogs));s['stable_transactions_total']=len(txs);s['stable_trace_omitted_count']=max(0,len(txs)-2)
  for tx in txs[:2]:
   rec=val('competitor_receipt_'+str(len(s['selected_pool_transactions'])),'eth_getTransactionReceipt',[tx]);s['selected_pool_transactions'].append({'tx':tx,'receipt':rec})
  jobs=[(SEEDS[0],o,q) for o in (1,2) for q in SIZES]+[(x,1,20000) for x in SEEDS[1:]]
  for seed,offset,usd in jobs:
   try:c=simulate(seed,offset,usd,runtime,headers)
   except Exception as e:c={'event':seed['label'],'offset_blocks':offset,'principal_USDC':usd,'unavailable':True,'exception':repr(e),'traceback':traceback.format_exc()}
   s['cases'].append(c);save('SUMMARY.json',s);print(json.dumps({k:v for k,v in c.items() if k not in ('response','parent','target','traceback')},indent=2),flush=True)
   if STOP:break
  if not STOP:
   for i,rec in enumerate(s['selected_pool_transactions']):
    r=rpc('competitor_trace_'+str(i),'debug_traceTransaction',[rec['tx'],{'tracer':'callTracer','timeout':'25s','tracerConfig':{'onlyTopCall':False}}]);rec['trace']=r;save('SUMMARY.json',s)
 except Exception as e:s.update(exception=repr(e),traceback=traceback.format_exc())
 s.update(completed_utc=utc(),rpc_requests=COUNT,stopped_on_provider=STOP);save('SUMMARY.json',s)
 print(json.dumps({'rpc_requests':COUNT,'cases':[{k:v for k,v in c.items() if k in ('event','offset_blocks','principal_USDC','status','paid_cash_raw','error','unavailable','exception')} for c in s['cases']],'exception':s.get('exception')},indent=2),flush=True)
if __name__=='__main__':main()
