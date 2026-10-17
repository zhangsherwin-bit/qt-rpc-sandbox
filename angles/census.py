"""Four-angle historical development census. Read-only public data; no keys/trades.
Ethereum, 2026-09-10 <= t < 2026-10-01. Explicitly not a prospective holdout.
"""
import json,time,hashlib,datetime,pathlib,urllib.request,urllib.error,collections
from eth_abi import encode,decode
from Crypto.Hash import keccak
OUT=pathlib.Path('evidence');RPC='https://rpc-eth.blockmachine.io'
MC='0xca11bde05977b3631167028862be2a173976ca11'
ZERO='0x'+'00'*20
WETH='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
STETH='0xae7ab96520de3a18e5e111b5eaab095312d7fe84'
ARM='0x85b78aca6deae198fbf201c82daf6ca21942acc6'
KEEPERS=['0x9201da0d97caaaff53f01b2fb56767c7072de340','0xfb726f57d251ab5c731e5c64ed4f5f94351ef9f3','0x3fa20eaa107de08b38a8734063d605d5842fe09c','0x338cb2d827112d989a861cde87cd9ffd913a1f9d']
TMS=['0x7bcb64b2c9206a5b699ed43363f6f98d4776cf5a','0xa2895d6a3bf110561dfe4b71ca539d84e1928b22','0xb2b2abeb5c357a234363ff5d180912d319e3e19e']
FACTORIES=['0xbc587a495420abb71bbd40a0e291b64e80117526','0xba7fcb508c7195ee5ae823f37ee2c11d7ed52f8e','0xa076c247afa44f8f006ca7f21a4ef59f7e4dc605','0xe6ab098e8582178a76dc80d55ca304d1dec11ad8']
START=1788998400;END=1790812800
ALLOWED={'eth_chainId','eth_blockNumber','eth_getBlockByNumber','eth_getCode','eth_getLogs','eth_call','eth_getTransactionReceipt','eth_getTransactionByHash'}
def save(n,v):
 p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2))
def h(s):return keccak.new(digest_bits=256,data=s.encode()).hexdigest()
def calldata(sig,types=(),args=()):return '0x'+h(sig)[:8]+encode(types,args).hex()
class Client:
 def __init__(self):self.n=0;self.last=0;self.last_heavy=0;self.start=time.monotonic();self.stopped=False;self.cache={}
 def rpc(self,name,method,params):
  if method not in ALLOWED or self.stopped or self.n>=1400 or time.monotonic()-self.start>3300:raise RuntimeError('read-only scope/budget/access stop')
  gap=70 if method=='eth_getLogs' else 1.5
  time.sleep(max(0,gap-(time.monotonic()-self.last)));self.n+=1;body=b''
  rec={'name':name,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'url':RPC,'payload':{'jsonrpc':'2.0','id':self.n,'method':method,'params':params}}
  try:
   req=urllib.request.Request(RPC,json.dumps(rec['payload']).encode(),{'Content-Type':'application/json','User-Agent':'QT-four-angle-read-only/1'})
   with urllib.request.urlopen(req,timeout=40) as r:rec['http']=r.status;body=r.read(24000001)
   if len(body)>24000000:raise ValueError('response cap')
   j=json.loads(body)
   if 'error' in j:
    rec['status']='RPC_ERROR';rec['error']=j['error']
    if any(w in str(j['error']).lower() for w in ('rate limit','quota','unauthorized','forbidden','api key')):self.stopped=True
    raise ValueError(str(j['error']))
   rec['status']='OK';return j['result']
  except urllib.error.HTTPError as e:
   body=e.read(100000);rec.update(status='HTTP_ERROR',http=e.code,error=str(e));self.stopped=e.code in (401,403,429);raise
  except Exception as e:rec.setdefault('status','UNAVAILABLE');rec.setdefault('error',repr(e));raise
  finally:
   self.last=time.monotonic();rec['sha256']=hashlib.sha256(body).hexdigest();save('raw/%04d.json'%self.n,rec);(OUT/'raw'/('%04d.body'%self.n)).write_bytes(body)
 def head(self,b):
  key=str(b)
  if key not in self.cache:self.cache[key]=self.rpc('header_'+key,'eth_getBlockByNumber',[hex(b) if isinstance(b,int) else b,False])
  return self.cache[key]
 def first(self,t):
  hi=int(self.head('latest')['number'],16);lo=max(1,hi-1000000)
  if int(self.head(lo)['timestamp'],16)>=t:lo=1
  while lo<hi:
   mid=(lo+hi)//2
   if int(self.head(mid)['timestamp'],16)<t:lo=mid+1
   else:hi=mid
  assert int(self.head(lo-1)['timestamp'],16)<t<=int(self.head(lo)['timestamp'],16)
  return lo
 def view(self,to,sig,types,args,b,outs):
  head=self.head(b);raw=self.rpc(sig,'eth_call',[{'to':to,'data':calldata(sig,types,args),'gasPrice':head['baseFeePerGas']},hex(b)])
  return decode(outs,bytes.fromhex(raw[2:]))
 def many(self,jobs,b):
  results=[];head=self.head(b)
  for i in range(0,len(jobs),20):
   chunk=jobs[i:i+20];items=[(x[0],True,bytes.fromhex(calldata(x[1],x[2],x[3])[2:])) for x in chunk]
   data=calldata('aggregate3((address,bool,bytes)[])',['(address,bool,bytes)[]'],[items])
   raw=self.rpc('view_batch','eth_call',[{'to':MC,'data':data,'gas':hex(12000000),'gasPrice':head['baseFeePerGas']},hex(b)])
   vals=decode(['(bool,bytes)[]'],bytes.fromhex(raw[2:]))[0]
   for job,(ok,v) in zip(chunk,vals):
    try:out=decode(job[4],v) if ok else None;err=None if ok else 'call reverted'
    except Exception as e:out=None;err=str(e)
    results.append({'address':job[0],'signature':job[1],'args':job[3],'ok':ok and out is not None,'values':out,'error':err})
   time.sleep(4)
  return results

def main():
 OUT.mkdir(exist_ok=True);c=Client();summary={'signed_or_sent':0,'profit_verified':False,'window':['2026-09-10','2026-10-01 exclusive'],'scope':'four specified Yearn factory registries, four Curve V2 keepers, three current Liquity V2 branches, Origin stETH ARM; historical registry-at-end universe','log_window_complete':False}
 save('PLAN.json',{'start':START,'end':END,'factories':FACTORIES,'keepers':KEEPERS,'trove_managers':TMS,'arm':ARM,'max_requests':1400,'max_seconds':3300,'log_chunk':10000,'historical_membership':True,'reserved_oct3_oct9_not_used':True})
 try:
  assert c.rpc('chain','eth_chainId',[])=='0x1'
  a=c.first(START);z=c.first(END)-1;b=z
  save('BOUNDARIES.json',{'first':c.head(a),'before':c.head(a-1),'last':c.head(z),'after':c.head(z+1)})
  reg=[];auctions=[]
  for f in FACTORIES:
   row={'factory':f}
   try:
    row['code']=c.rpc('factory_code','eth_getCode',[f,hex(b)])
    if row['code']=='0x':raise ValueError('not deployed at study end')
    row['auctions']=list(c.view(f,'getAllAuctions()',[],[],b,['address[]'])[0]);auctions+=row['auctions']
    try:row['version']=c.view(f,'version()',[],[],b,['string'])[0]
    except Exception as e:row['version_error']=repr(e)
   except Exception as e:row['unavailable']=repr(e)
   reg.append(row)
  auctions=sorted(set(x.lower() for x in auctions));save('FACTORIES.json',reg);summary['factory_auctions']=len(auctions)
  if len(auctions)>250:raise ValueError('more than 250 auction instances; refuse silent truncation')
  jobs=[]
  for x in auctions:
   for sig,out in [('want()',['address']),('getAllEnabledAuctions()',['address[]']),('version()',['string'])]:jobs.append((x,sig,[],[],out))
  ar=c.many(jobs,b);save('AUCTION_METADATA.json',ar)
  records=[]
  for i,x in enumerate(auctions):
   w,t,v=ar[3*i:3*i+3]
   records.append({'auction':x,'want':w['values'][0] if w['ok'] else None,'from_tokens':list(t['values'][0]) if t['ok'] else None,'version':v['values'][0] if v['ok'] else None})
  save('AUCTIONS.json',records)
  edges=[(r['auction'],t,r['want']) for r in records if r['from_tokens'] is not None and r['want'] for t in r['from_tokens']]
  pairs=[(x,y) for i,x in enumerate(edges) for y in edges[i+1:] if x[0]!=y[0] and x[1]==y[2] and x[2]==y[1]]
  save('RECIPROCAL_PAIRS_STRUCTURAL.json',pairs);summary['enabled_pairs']=len(edges);summary['reciprocal_pairs_structural']=len(pairs)
  jobs=[]
  for pk in KEEPERS:
   for sig,out in [('pool()',['address']),('regulator()',['address']),('caller_share()',['uint256']),('debt()',['uint256']),('estimate_caller_profit()',['uint256'])]:jobs.append((pk,sig,[],[],out))
  for tm in TMS:
   for sig,out in [('collToken()',['address']),('gasPoolAddress()',['address']),('getTroveIdsCount()',['uint256']),('shutdownTime()',['uint256'])]:jobs.append((tm,sig,[],[],out))
  for sig,out in [('token0()',['address']),('token1()',['address']),('getReserves()',['uint256','uint256']),('traderate0()',['uint256']),('traderate1()',['uint256']),('buyPrice()',['uint256']),('sellPrice()',['uint256'])]:jobs.append((ARM,sig,[],[],out))
  meta=c.many(jobs,b);save('FAMILY_METADATA.json',meta)
  # All contract logs, not just successful fills. Excludes token pool logs (obtained from receipts later).
  addresses=sorted(set(auctions+KEEPERS+TMS+[ARM]+FACTORIES))
  logs=[];pages=[]
  for start in range(a,z+1,10000):
   end=min(start+9999,z)
   rows=c.rpc('all_family_logs_%s'%start,'eth_getLogs',[{'address':addresses,'fromBlock':hex(start),'toBlock':hex(end)}]);logs.extend(rows);pages.append({'start':start,'end':end,'count':len(rows)})
   save('PAGES.json',pages);save('ALL_LOGS.json',logs);print(json.dumps({'page':pages[-1],'calls':c.n}),flush=True)
  unique={(x['transactionHash'],x['logIndex']) for x in logs}
  assert len(unique)==len(logs),'duplicate logs'
  kinds=collections.Counter(x['address'].lower() for x in logs);summary.update(log_window_complete=True,log_count=len(logs),pages=len(pages),log_counts_by_address=dict(kinds))
  # Only named externally callable action events define service candidates; zero-address LP burns are never rewards.
  liq='0x'+h('Liquidation('+','.join(['uint256']*10)+')')
  keeper_topics={'0x8d685bd3f45d861c759ed7a46ea3d30eb5cc6ce9fe06c526931f94c963bca7d2','0x5b6b431d4476a211bb7d41c20d1aab9ae2321deee0d20be3d9fc9b1093fa6e3d'}
  chosen=[]
  for family,cond in [('liquity',lambda l:l['address'].lower() in TMS and l['topics'][0].lower()==liq),('keeper',lambda l:l['address'].lower() in KEEPERS and l['topics'][0].lower() in keeper_topics)]:
   rows=sorted([l for l in logs if cond(l)],key=lambda l:(int(l['blockNumber'],16),int(l['logIndex'],16)))
   save(family+'_events.json',rows);summary[family+'_events']=len(rows)
   txs=list(dict.fromkeys(l['transactionHash'] for l in rows));summary[family+'_transactions']=len(txs)
   chosen+=txs
  chosen=list(dict.fromkeys(chosen));save('SERVICE_RECEIPTS_SELECTED.json',chosen)
  if len(chosen)>350:summary['receipt_scope_truncated']=True;chosen=chosen[:350]
  receipts=[]
  for tx in chosen:
   try:r=c.rpc('receipt_'+tx,'eth_getTransactionReceipt',[tx]);receipts.append(r)
   except Exception as e:receipts.append({'transactionHash':tx,'error':repr(e)})
   if c.stopped:raise RuntimeError('provider stopped')
   save('SERVICE_RECEIPTS.json',receipts)
  summary['service_receipts']=len(receipts)
 except Exception as e:summary['exception']=repr(e)
 summary.update(requests=c.n,provider_stopped=c.stopped);save('SUMMARY.json',summary);print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
