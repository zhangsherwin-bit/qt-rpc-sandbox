"""Bounded public RPC observations, never signed or broadcast.
Holder-context redemption tests are counterfactual liquidity diagnostics, NOT
permissionless liquidation executions. No storage, code, price or time overrides.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, sys, time, urllib.request, urllib.error
from pathlib import Path

BASE='https://mainnet.base.org'
ETH='https://rpc-eth.blockmachine.io'
MC='0xca11bde05977b3631167028862be2a173976ca11'
CORE='0xadedd8ab6de832766fedf0fac4992e5c4d3ea18a'
BLUE='0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb'
USDC='0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
PROBE='0x00000000000000000000000000000000dead9911'
VAULTS=['0xe690a58ef52854513462745237f6a213a0d54df1','0xf6a70085b7f79fa76b04ebf7a2d7d87c3c5c04bc']
SIZES=[117807337363261042850442,0]
SEEDS=[('0xaf532fea7df2fe561ad70e6df0649a946d35955d99906aa6adcd1fc1a07e1194',25643399),('0x080504ec2f23ac1754bef172376988e1d9727f4c67d442c6011eba5e2ff27bb6',25649158),('0xd47ca9ff33d59af1ff6dd0f2894f749d6799d5ed12f717f667c9c44bb70a2d2b',25868888)]
# Ethereum Keccak selectors independently generated and frozen before requests.
SIG={'aggregate3((address,bool,bytes)[])': '82ad56cb', 'asset()': '38d52e0f', 'totalAssets()': '01e1d114', 'totalSupply()': '18160ddd', 'virtualShares()': 'c719946c', 'receiveSharesGate()': '7e729ac4', 'sendSharesGate()': '93ab2ab7', 'receiveAssetsGate()': '54cde13e', 'sendAssetsGate()': '8eede801', 'liquidityAdapter()': 'ad468d11', 'liquidityData()': '2e029228', 'adaptersLength()': '5aa22bc8', 'managementFeeRecipient()': '6d9a3010', 'performanceFeeRecipient()': 'ed27f7c9', 'balanceOf(address)': '70a08231', 'canReceiveShares(address)': '98c9b49c', 'canSendShares(address)': '8e511e4d', 'canReceiveAssets(address)': '0d326b18', 'canSendAssets(address)': '20fe8d58', 'previewRedeem(uint256)': '4cdad506', 'redeem(uint256,address,address)': 'ba087652', 'MORPHO()': '3acb5624', 'morpho()': 'd8fbc833', 'parentVault()': '0fe36536'}
ALLOWED={'eth_chainId','eth_getBlockByNumber','eth_getTransactionReceipt','eth_getTransactionByHash','eth_getCode','eth_getLogs','eth_call','eth_simulateV1','debug_traceTransaction'}
OUT=Path('evidence'); OUT.mkdir(exist_ok=True); (OUT/'raw').mkdir(exist_ok=True)

def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def word(x):return int(x,16).to_bytes(32,'big') if isinstance(x,str) else int(x).to_bytes(32,'big')
def call(sig,*args):return '0x'+SIG[sig]+b''.join(word(x) for x in args).hex()
def num(b,p):
 if p<0 or p+32>len(b):raise ValueError('ABI bounds')
 return int.from_bytes(b[p:p+32],'big')
def addr(n):
 if n>=2**160:raise ValueError('address width')
 return '0x'+format(n,'040x')
def multi_payload(items):
 tails=[]
 for to,data in items:
  b=bytes.fromhex(data[2:]);tails.append(word(to)+word(1)+word(96)+word(len(b))+b+b'\0'*((-len(b))%32))
 offset=32*len(tails);heads=[]
 for t in tails:heads.append(word(offset));offset+=len(t)
 return '0x'+SIG['aggregate3((address,bool,bytes)[])']+(word(32)+word(len(tails))+b''.join(heads)+b''.join(tails)).hex()
def decode_multi(raw):
 b=bytes.fromhex(raw[2:]);root=num(b,0);n=num(b,root);head=root+32;ans=[]
 if n>200:raise ValueError('result too large')
 for i in range(n):
  p=head+num(b,head+32*i);ok=num(b,p);d=p+num(b,p+32);length=num(b,d)
  if ok not in (0,1) or d+32+length>len(b):raise ValueError('bad tuple')
  ans.append((bool(ok),'0x'+b[d+32:d+32+length].hex()))
 return ans

def rpc(endpoint,name,method,params):
 if endpoint not in (BASE,ETH) or method not in ALLOWED:raise ValueError('outside read-only allowlist')
 if endpoint in rpc.stopped or rpc.count>=95 or time.monotonic()-rpc.begin>840:raise RuntimeError('fixed budget/access stop')
 gap=65 if method in ('debug_traceTransaction','eth_simulateV1') else (2 if endpoint==ETH else 1.2)
 time.sleep(max(0,gap-(time.monotonic()-rpc.last.get(endpoint,0))))
 rpc.count+=1;payload={'jsonrpc':'2.0','id':rpc.count,'method':method,'params':params}
 meta={'name':name,'url':endpoint,'payload':payload,'start_utc':utc()};body=b'';result=None
 try:
  req=urllib.request.Request(endpoint,json.dumps(payload).encode(),{'Content-Type':'application/json','User-Agent':'QT-Execution-Followthrough/1'})
  with urllib.request.urlopen(req,timeout=45) as res:
   meta['http_status']=res.status;body=res.read(12000001)
  if len(body)>12000000:raise ValueError('response cap exceeded')
  data=json.loads(body);meta['status']='RPC_ERROR' if 'error' in data else 'OK';result=data.get('result');meta['rpc_error']=data.get('error')
 except urllib.error.HTTPError as e:
  body=e.read(100000);meta.update(status='HTTP_ERROR',http_status=e.code,error=str(e))
  if e.code in (401,403,429):rpc.stopped.add(endpoint)
 except Exception as e:meta.update(status='UNAVAILABLE',error=repr(e))
 meta.update(end_utc=utc(),sha256=hashlib.sha256(body).hexdigest(),response_bytes=len(body));stem=f'{rpc.count:03d}_{name}'
 (OUT/'raw'/f'{stem}.body').write_bytes(body);(OUT/'raw'/f'{stem}.json').write_text(json.dumps(meta,indent=2));rpc.last[endpoint]=time.monotonic()
 return result
rpc.count=0;rpc.stopped=set();rpc.last={};rpc.begin=time.monotonic()

def reads(endpoint,block,items):
 raw=rpc(endpoint,'views_'+str(rpc.count),'eth_call',[{'to':MC,'data':multi_payload([(a,d) for _,a,d in items]),'gas':hex(12000000)},block])
 if raw is None:return {name:{'unavailable':True} for name,_,_ in items}
 results=decode_multi(raw)
 if len(results)!=len(items):raise ValueError('view count mismatch')
 out={}
 for (name,_,_),(ok,b) in zip(items,results):
  out[name]={'ok':ok,'raw':b}
  if ok and len(b)==66:out[name]['integer']=str(int(b,16))
 return out

def simple(v,k):
 x=v.get(k,{})
 return int(x['integer']) if 'integer' in x else None

def inspect_vaults():
 if rpc(BASE,'base_chain','eth_chainId',[])!='0x2105':raise ValueError('not Base')
 h=rpc(BASE,'base_header','eth_getBlockByNumber',['latest',False]);block=h['number'];out={'header':h,'vaults':[]}
 actors={'core':CORE,'research_address':PROBE,'borrower':'0x8eb3a5db0b650bddd2ac457f5500b32c86505a14'}
 for i,vault in enumerate(VAULTS):
  noargs=['asset()','totalAssets()','totalSupply()','virtualShares()','receiveSharesGate()','sendSharesGate()','receiveAssetsGate()','sendAssetsGate()','liquidityAdapter()','liquidityData()','adaptersLength()','managementFeeRecipient()','performanceFeeRecipient()']
  items=[(s,vault,call(s)) for s in noargs]
  items += [('share_balance_core',vault,call('balanceOf(address)',CORE)),('idle_USDC',USDC,call('balanceOf(address)',vault))]
  for tag,account in actors.items():
   for f in ['canReceiveShares(address)','canSendShares(address)','canReceiveAssets(address)','canSendAssets(address)']:
    items.append((tag+'_'+f,vault,call(f,account)))
  sizes=[10**18]+([SIZES[i]//2,SIZES[i]] if SIZES[i] else [])
  items += [('preview_'+str(q),vault,call('previewRedeem(uint256)',q)) for q in sizes]
  values=reads(BASE,block,items);rec={'vault':vault,'views':values,'redemption_tests':[]};out['vaults'].append(rec)
  ad=simple(values,'liquidityAdapter()');ld=values.get('liquidityData()',{}).get('raw','0x')
  if ad:
   ad=addr(ad);rec['adapter']=ad;rec['adapter_views']=reads(BASE,block,[(s,ad,call(s)) for s in ['MORPHO()','morpho()','parentVault()']])
  try:
   bb=bytes.fromhex(ld[2:]);p=num(bb,0);n=num(bb,p);data=bb[p+32:p+32+n]
   if len(data)==160:
    mp=[addr(num(data,32*k)) for k in range(4)]+[str(num(data,128))];rec['liquidity_data_market_params']=mp
   else:rec['liquidity_data_decoded_bytes']=len(data)
  except (ValueError,IndexError):rec['liquidity_data_decode']='unavailable'
  bal=simple(values,'share_balance_core')
  # Counterfactual owner-context redemption: no statement that an EOA may control core.
  if i==0 and bal and simple(values,'asset()')==int(USDC,16):
   for q in [min(10**18,bal),min(SIZES[i],bal)]:
    calls=[{'to':USDC,'input':call('balanceOf(address)',CORE),'gas':hex(100000)},
           {'to':vault,'input':call('balanceOf(address)',CORE),'gas':hex(100000)},
           {'from':CORE,'to':vault,'input':call('redeem(uint256,address,address)',q,CORE,CORE),'gas':hex(6000000)},
           {'to':USDC,'input':call('balanceOf(address)',CORE),'gas':hex(100000)},
           {'to':vault,'input':call('balanceOf(address)',CORE),'gas':hex(100000)}]
    for c in calls:c['gasPrice']='0x0'
    result=rpc(BASE,'holder_redemption_'+str(q),'eth_simulateV1',[{'blockStateCalls':[{'calls':calls}],'validation':False},block])
    rec['redemption_tests'].append({'shares':str(q),'type':'holder-context liquidity diagnostic; not own liquidation or income','response':result})
 h2=rpc(BASE,'base_header_check','eth_getBlockByNumber',[block,False]);out['header_hash_stable']=h2 is not None and h2['hash']==h['hash']
 return out

def inspect_winners():
 if rpc(ETH,'eth_chain','eth_chainId',[])!='0x1':raise ValueError('not Ethereum')
 out=[]
 for i,(tx,bn) in enumerate(SEEDS):
  rec={'tx':tx,'expected_block':bn};out.append(rec)
  rec['receipt']=rpc(ETH,f'receipt_{i}','eth_getTransactionReceipt',[tx])
  rec['header']=rpc(ETH,f'header_{i}','eth_getBlockByNumber',[hex(bn),False])
  rec['transaction']=rpc(ETH,f'tx_{i}','eth_getTransactionByHash',[tx])
  rec['trace']=rpc(ETH,f'trace_{i}','debug_traceTransaction',[tx,{'tracer':'callTracer','timeout':'25s','tracerConfig':{'onlyTopCall':False}}])
  if rec['receipt'] and rec['header']:
   rec['canonical_anchor_matches']=rec['receipt']['blockHash']==rec['header']['hash'] and int(rec['receipt']['blockNumber'],16)==bn
 return out

def main():
 report={'started_utc':utc(),'transactions_sent':0,'profit_verified':False,'scope':'two known Tenor vaults and three preselected historical wrapper winners'}
 for name,fn in [('vaults',inspect_vaults),('winners',inspect_winners)]:
  try:report[name]=fn()
  except Exception as e:report[name]={'error':repr(e)}
  (OUT/'SUMMARY.json').write_text(json.dumps(report,indent=2))
 report.update(completed_utc=utc(),request_count=rpc.count,stopped_endpoints=sorted(rpc.stopped));(OUT/'SUMMARY.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k not in ('vaults','winners')},indent=2))
 print('Detailed raw observations and failures are preserved in SUMMARY.json and raw/.')
if __name__=='__main__':main()
