"""Bounded public research, no signing, broadcasting, keys or trading.
HTTP failures stay unknown; current snapshots are not historical orderbooks.
"""
from __future__ import annotations
import json,time,hashlib,traceback,datetime,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from Crypto.Hash import keccak
OUT=Path('evidence'); OUT.mkdir(exist_ok=True)
ETH='https://rpc-eth.blockmachine.io'
RPC={1:ETH,8453:'https://mainnet.base.org',42161:'https://arb1.arbitrum.io/rpc',10:'https://mainnet.optimism.io'}
CHAINLOG='0xda0ab1e0017debcd72beaceedaeccfbc436b6f13'
REACTOR='0x00000011f84b9aa48e5f8aa8b9897600006289be'
COW='0x9008d19f58aabd9ed0d60971565aa8510560ab41'
START=int(datetime.datetime(2026,9,10,tzinfo=datetime.timezone.utc).timestamp())
END=int(datetime.datetime(2026,10,1,tzinfo=datetime.timezone.utc).timestamp())
USDC={1:'0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',8453:'0x833589fcd6edb6e08f4c7c32d4f71b54bda02913',42161:'0xaf88d065e77c8cc2239327c5edb3a432268e5831',10:'0x0b2c639c533813f4aa9d7837caf62653d097ff85'}
def H(s):k=keccak.new(digest_bits=256);k.update(s.encode());return k.hexdigest()
def save(n,v):p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2))
def wi(n):return f'{int(n):064x}'
def addr(h):return '0x'+h[-40:].lower()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class Client:
 def __init__(self):self.n=0;self.blocked=set();self.last={};self.start=time.monotonic();self.records=[]
 def get(self,name,url,payload=None):
  host=urllib.parse.urlsplit(url).netloc
  if host in self.blocked:raise RuntimeError('STOPPED_ENDPOINT '+host)
  if self.n>=500 or time.monotonic()-self.start>2600:raise RuntimeError('FIXED_RESEARCH_BUDGET')
  if host not in {'rpc-eth.blockmachine.io','mainnet.base.org','arb1.arbitrum.io','mainnet.optimism.io','across.to','api.uniswap.org'}:raise ValueError('unapproved host')
  if payload is not None and payload.get('method') not in {'eth_chainId','eth_blockNumber','eth_getBlockByNumber','eth_getTransactionByHash','eth_getTransactionReceipt','eth_getBlockReceipts','eth_getCode','eth_call','eth_getLogs','debug_traceTransaction'}:raise ValueError('read RPC allowlist')
  heavy=payload is not None and payload['method'] in {'eth_getLogs','debug_traceTransaction'}
  delay=(70 if heavy else 1.0)-(time.monotonic()-self.last.get(host,0));time.sleep(max(0,delay))
  self.n+=1;rec={'id':self.n,'name':name,'url':url,'payload':payload,'started_utc':utc()};b=b''
  try:
   data=None if payload is None else json.dumps(payload).encode()
   req=urllib.request.Request(url,data=data,headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'QT-ReadOnly-Stage1/20261018'})
   with urllib.request.urlopen(req,timeout=50) as r:rec['http_status']=r.status;b=r.read(10000001)
   if len(b)>10000000:raise RuntimeError('BODY_LIMIT')
   p=json.loads(b)
   if payload is not None and isinstance(p,dict) and p.get('error'):
    rec['rpc_error']=p['error'];msg=str(p['error']).lower()
    if any(s in msg for s in ('rate limit','access denied','unauthorized','client adjustable limit')):self.blocked.add(host)
    raise RuntimeError('RPC '+str(p['error']))
   rec['status']='OK';return p
  except urllib.error.HTTPError as e:
   b=e.read(100000);rec.update(status='HTTP_ERROR',http_status=e.code,error=str(e))
   if e.code in (401,403,429):self.blocked.add(host)
   raise
  except Exception as e:rec.setdefault('status','UNAVAILABLE');rec['error']=repr(e);raise
  finally:
   self.last[host]=time.monotonic();rec['ended_utc']=utc();rec['sha256']=hashlib.sha256(b).hexdigest();self.records.append(rec)
   (OUT/'raw').mkdir(exist_ok=True);(OUT/f'raw/{self.n:04d}.body').write_bytes(b);save(f'raw/{self.n:04d}.json',rec)
   print(json.dumps({'n':self.n,'name':name,'status':rec.get('status'),'error':rec.get('error')},sort_keys=True),flush=True)
 def rpc(self,name,method,params,chain=1):return self.get(name,RPC[chain],{'jsonrpc':'2.0','id':self.n+1,'method':method,'params':params})['result']
 def view(self,name,to,sig,args='',block='latest',chain=1):return self.rpc(name,'eth_call',[{'to':to,'data':'0x'+H(sig)[:8]+args},block],chain)
 def header(self,n,chain=1,full=False):return self.rpc('header_'+str(n),'eth_getBlockByNumber',[hex(n),full],chain)
 def boundary(self,ts):
  low,high=25500000,26300000
  while low<high:
   mid=(low+high)//2;h=self.header(mid)
   if int(h['timestamp'],16)<ts:low=mid+1
   else:high=mid
  before=self.header(low-1);after=self.header(low);assert int(before['timestamp'],16)<ts<=int(after['timestamp'],16);return low
 def logs(self,name,addresses,topics,a,b):
  rows=[];coverage=[]
  for lo in range(a,b+1,10000):
   hi=min(b,lo+9999);part=self.rpc(name,'eth_getLogs',[{'address':addresses,'topics':topics,'fromBlock':hex(lo),'toBlock':hex(hi)}]);rows+=part;coverage.append([lo,hi,len(part)])
   save(name+'.json',{'rows':rows,'pages':coverage,'requested':[a,b],'complete':hi==b})
  return rows

def across(c):
 result={'scope':'Latest 1000 API rows in each reciprocal Ethereum/Base corridor at retrieval; not a calendar census','refunds_are_not_verified':True,'corridors':[]}
 save('ACROSS.json',result)
 for origin,dest in [(1,8453),(8453,1)]:
  try:
   rows=c.get('across_deposits',f'https://across.to/api/deposits?originChainId={origin}&destinationChainId={dest}&status=filled&limit=1000&skip=0')
   if not isinstance(rows,list):raise ValueError('deposits list schema')
   save(f'across/{origin}_{dest}_deposits.json',rows)
   eligible=[r for r in rows if r.get('inputToken','').lower()==USDC[origin] and r.get('outputToken','').lower()==USDC[dest]]
   duplicates=len(eligible)-len({(r.get('originChainId'),str(r.get('depositId'))) for r in eligible})
   summary={'origin':origin,'destination':dest,'rows':len(rows),'native_usdc_rows':len(eligible),'duplicate_ids':duplicates,'sample':[]}
   result['corridors'].append(summary)
   for r in eligible[:3]:
    entry={'deposit_id':str(r.get('depositId')),'input_amount':r.get('inputAmount'),'output_amount':r.get('outputAmount'),'gross_user_fee_upper_bound_raw':str(int(r['inputAmount'])-int(r['outputAmount'])),'lp_fee_refund_link_unverified':True}
    summary['sample'].append(entry)
    for leg,key,ch in [('deposit','depositTxHash',origin),('fill','fillTx',dest)]:
     tx=r.get(key) or r.get('depositTxnRef' if leg=='deposit' else 'fillTxnRef')
     if tx:
      try:
       receipt=c.rpc('across_'+leg,'eth_getTransactionReceipt',[tx],ch);assert receipt and receipt['status']=='0x1'
       save(f'across/{origin}_{dest}_{entry["deposit_id"]}_{leg}_receipt.json',receipt)
       entry[leg+'_tx']=tx;entry[leg+'_gas_wei']=str(int(receipt['gasUsed'],16)*int(receipt['effectiveGasPrice'],16));entry[leg+'_l1fee_wei']=receipt.get('l1Fee')
      except Exception as e:entry[leg+'_error']=repr(e)
    try:
     details=c.get('across_detail',f'https://across.to/api/deposit?originChainId={origin}&depositId={entry["deposit_id"]}');save(f'across/{origin}_{dest}_{entry["deposit_id"]}_detail.json',details)
    except Exception as e:entry['detail_error']=repr(e)
   summary['gross_user_fee_bound_usdc']=str(sum(int(r['inputAmount'])-int(r['outputAmount']) for r in eligible)/1e6)
   summary['relayer_counts']={x:sum(r.get('relayer')==x for r in eligible) for x in sorted({r.get('relayer','unknown') for r in eligible})}
  except Exception as e:result['corridors'].append({'origin':origin,'destination':dest,'error':repr(e)})
  save('ACROSS.json',result)
 return result

def orders(c):
 result={'scope':'Six spaced present-time open snapshots plus latest API filled samples; not historical open-order completeness','snapshots':[],'filled_samples':[]}
 for i in range(6):
  for chain,kind in [(1,'Dutch_V2'),(8453,'Dutch_V3'),(42161,'Dutch_V3')]:
   try:
    r=c.get('uniswapx_open',f'https://api.uniswap.org/v2/orders?orderStatus=open&chainId={chain}&orderType={kind}&limit=50');save(f'orders/{i}_{chain}_open.json',r)
    result['snapshots'].append({'snapshot':i,'chain':chain,'observed_utc':utc(),'count':len(r.get('orders',[]))})
   except Exception as e:result['snapshots'].append({'snapshot':i,'chain':chain,'error':repr(e)})
  save('ORDERS.json',result)
  if i<5:time.sleep(20)
 for chain,kind in [(1,'Dutch_V2'),(8453,'Dutch_V3')]:
  try:
   r=c.get('uniswapx_filled',f'https://api.uniswap.org/v2/orders?orderStatus=filled&chainId={chain}&orderType={kind}&limit=50');save(f'orders/{chain}_filled.json',r);result['filled_samples'].append({'chain':chain,'count':len(r.get('orders',[]))})
  except Exception as e:result['filled_samples'].append({'chain':chain,'error':repr(e)})
 save('ORDERS.json',result);return result

def sky(c):
 result={'scope':'Frozen full 21-day Ethereum Dog Bark and recovered Clipper reset census. Eligibility and cash are not inferred from absence of events.','errors':[]}
 a=c.boundary(START);b=c.boundary(END)-1;result['blocks']=[a,b];save('SKY.json',result)
 addresses={}
 for key in ['MCD_DOG','MCD_VAT','MCD_DAI_JOIN','MCD_DAI']:
  try:addresses[key]=addr(c.view('chainlog_'+key,CHAINLOG,'getAddress(bytes32)',key.encode().hex().ljust(64,'0'),hex(b)))
  except Exception as e:result['errors'].append({'key':key,'error':repr(e)})
 result['addresses']=addresses;save('SKY.json',result)
 if 'MCD_DOG' not in addresses:return result
 dog=addresses['MCD_DOG'];barks=c.logs('sky_barks',[dog],['0x'+H('Bark(bytes32,address,uint256,uint256,uint256,address,uint256)')],a,b)
 result['bark_count']=len(barks);clippers={};events=[]
 for l in barks:
  words=[l['data'][i:i+64] for i in range(2,len(l['data']),64)]
  event={'block':int(l['blockNumber'],16),'tx':l['transactionHash'],'tx_index':int(l['transactionIndex'],16),'topics':l['topics'],'data_words':words};events.append(event)
  if len(words)==5:clippers[addr(words[3])]=l['topics'][1]
 result['decoded_barks']=events;result['clippers_from_barks']=clippers;save('SKY.json',result)
 # Also fixed major vault branches so existing-auction resets do not require a new bark.
 for name in ['ETH_A','ETH_B','ETH_C','WBTC_A','WBTC_B','WBTC_C','WSTETH_A','WSTETH_B','RETH_A']:
  key='MCD_CLIP_'+name
  try:
   cp=addr(c.view('chainlog_'+key,CHAINLOG,'getAddress(bytes32)',key.encode().hex().ljust(64,'0'),hex(b)))
   if int(cp,16):clippers.setdefault(cp,None)
  except Exception as e:result['errors'].append({'key':key,'error':repr(e)})
 result['clippers']=clippers;result['parameters']={}
 for cp in clippers:
  param={}
  for sig in ['tip()','chip()','stopped()','count()','dog()','vat()','ilk()']:
   try:param[sig]=c.view('clip_'+sig,cp,sig,block=hex(b))
   except Exception as e:param[sig]={'error':repr(e)}
  result['parameters'][cp]=param;save('SKY.json',result)
 if clippers:
  resets=c.logs('sky_redos',list(clippers),['0x'+H('Redo(uint256,uint256,uint256,uint256,address,address,uint256)')],a,b);result['redo_count']=len(resets)
 selected=[]
 if events:
  ordered=sorted(events,key=lambda x:(x['block'],x['tx_index']))
  selected=list({x['tx']:x for x in [ordered[0],ordered[len(ordered)//2],ordered[-1]]}.values())
 result['selected_before_traces']=selected;save('SKY.json',result)
 for e in selected:
  try:
   rc=c.rpc('sky_receipt','eth_getTransactionReceipt',[e['tx']]);save('sky/'+e['tx']+'_receipt.json',rc)
   tr=c.rpc('sky_trace','debug_traceTransaction',[e['tx'],{'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True}}]);save('sky/'+e['tx']+'_trace.json',tr)
  except Exception as exc:e['trace_error']=repr(exc)
 save('SKY.json',result);return result

def chain_orders(c):
 # The CoW HTTP endpoint was denied in preflight; it is not retried or bypassed.
 a=c.boundary(int(datetime.datetime(2026,9,18,tzinfo=datetime.timezone.utc).timestamp()));b=c.boundary(int(datetime.datetime(2026,9,19,tzinfo=datetime.timezone.utc).timestamp()))-1
 r={'scope':'One frozen September18 day of canonical settlements, not complete unfilled order data','blocks':[a,b]}
 for label,contract,sig in [('uniswapx',REACTOR,'Fill(bytes32,address,address,uint256)'),('cow',COW,'Settlement(address)')]:
  try:
   logs=c.logs(label+'_settlements',[contract],['0x'+H(sig)],a,b);r[label]={'events':len(logs),'unique_transactions':len({x['transactionHash'] for x in logs})}
   ts=sorted({x['transactionHash']:x for x in logs}.values(),key=lambda l:(int(l['blockNumber'],16),int(l['transactionIndex'],16)))
   for l in ts[:2]:
    receipt=c.rpc(label+'_receipt','eth_getTransactionReceipt',[l['transactionHash']]);save(label+'/'+l['transactionHash']+'_receipt.json',receipt)
    trace=c.rpc(label+'_trace','debug_traceTransaction',[l['transactionHash'],{'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True}}]);save(label+'/'+l['transactionHash']+'_trace.json',trace)
  except Exception as e:r[label]={'error':repr(e)}
  save('CHAIN_ORDERS.json',r)
 return r

def main():
 c=Client();plan={'created_utc':utc(),'scope':'STAGE1_EMPIRICAL_DEVELOPMENT','start':START,'end_exclusive':END,'no_live_transfers_or_signatures':True,'reserved_oct3_oct9_untouched':True,'CoW_API_denial_respected':True,'maximum_requests':500,'maximum_seconds':2600,'no_profit_guarantee_or_zero_capital_assumption':True};save('PLAN.json',plan)
 for name,fn in [('across',across),('orders',orders),('sky',sky),('chain_orders',chain_orders)]:
  try:plan[name]=fn(c)
  except Exception as e:plan[name]={'error':repr(e),'traceback':traceback.format_exc()}
  save('REPORT.json',plan)
 plan['requests']=c.n;plan['blocked_hosts']=sorted(c.blocked);plan['ended_utc']=utc();save('REPORT.json',plan)
 print(json.dumps({k:plan.get(k) for k in ['requests','blocked_hosts','ended_utc']},indent=2))
if __name__=='__main__':main()
