"""Stage1 Yearn: real kicked USDC/CRV auctions paid in crvUSD.
Read-only same-state on-chain auction and finite DEX conversion quotes.
Quotes are NOT executions, filler rights, available capital or trading income.
Selection fixed by logged event chronology before any profitability queries.
"""
import collections,datetime as dt,hashlib,json,time,traceback,urllib.request,urllib.error
from pathlib import Path
from Crypto.Hash import keccak
OUT=Path("auction_evidence");OUT.mkdir(exist_ok=True)
RPC="https://rpc-eth.blockmachine.io"
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
CRV="0xd533a949740bb3306d119cc777fa900ba034cd52"
CRVUSD="0xf939e0a03fb07f59a73314e73794be0e57ac1b4e"
CURVE="0x4dece678ceceb27446b35c672dc7d61f30bad69e"
QUOTER="0x61ffe014ba17989e743c5f6cb21bf9697530b21e"
KICK="0xb3831db58b36bd77258a9cc9589b88fab5d52f7a1814e6f17faec14b149fe084"
SETTLE="0x3539af76bcb13fa381f2ec32e6d90b9c5e95055778ebdca0e7a192ba07755881"
METHODS=("getAmountNeeded(address,uint256)","available(address)","get_dy(int128,int128,uint256)","get_dy(uint256,uint256,uint256)","coins(uint256)","quoteExactInputSingle((address,address,uint256,uint24,uint160))")
def h(s):
 a=keccak.new(digest_bits=256);a.update(s.encode());return a.hexdigest()
def pad(n):return format(int(n),'064x')
def enc(x):return pad(int(x,16) if isinstance(x,str) and x.startswith("0x") else x)
def data(sig,*args):return "0x"+h(sig)[:8]+''.join(enc(a) for a in args)
def number(raw):
 if not isinstance(raw,str) or not raw.startswith('0x') or len(raw)<66:raise ValueError("Malformed ABI response")
 return int(raw[2:66],16)
def address(i):return '0x'+format(i,'040x')
def save(filename,obj):
 path=OUT/filename;path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,indent=2,default=str)+'\n')
def frozen():
 p=Path('input_auctions')
 meta=json.loads((p/'AUCTIONS.json').read_text())
 logs=json.loads((p/'ALL_LOGS.json').read_text())
 summary=json.loads((p/'SUMMARY.json').read_text())
 if len(meta)!=141 or summary['factory_auctions']!=141 or summary['log_count']!=len(logs):raise ValueError('Changed or incomplete source census')
 amap={x['auction'].lower():x for x in meta}
 events=[];settles=collections.defaultdict(list)
 for l in logs:
  if l['topics'][0].lower()==SETTLE and len(l['topics'])==2:
   key=(l['address'].lower(),address(int(l['topics'][1],16)))
   settles[key].append(int(l['blockNumber'],16))
 for l in logs:
  if l['topics'][0].lower()!=KICK:continue
  if len(l['topics'])!=2:raise ValueError('Kick event ABI mismatch')
  au=l['address'].lower();m=amap.get(au)
  if not m or m['want'].lower()!=CRVUSD:continue
  token=address(int(l['topics'][1],16))
  if token not in (USDC,CRV):continue
  qty=number(l['data'])
  if qty <= (100*10**6 if token==USDC else 100*10**18):continue
  b=int(l['blockNumber'],16)
  future=[z for z in settles[(au,token)] if z>=b]
  events.append(dict(auction=au,from_token=token,want=CRVUSD,kick_block=b,
    kicker_tx=l['transactionHash'],kick_log_index=int(l['logIndex'],16),
    kicked_raw=str(qty),next_settlement_block=min(future) if future else None,
    kick_date=dt.datetime.fromtimestamp(int(l['blockTimestamp'],16),dt.timezone.utc).date().isoformat()))
 events.sort(key=lambda r:(r['kick_block'],r['kick_log_index']))
 chosen=[]
 for token in (USDC,CRV):
  dates=set()
  for c in [z for z in events if z['from_token']==token]:
   if c['kick_date'] in dates:continue
   chosen.append(c);dates.add(c['kick_date'])
   if len(dates)==4:break
 if len(chosen)!=8:raise ValueError('Frozen 8 distinct-date events per asset not available')
 return chosen,{'source_events':len(events),'source_auctions':len(meta),'source_logs':len(logs),'chosen':len(chosen)}

class Rpc:
 def __init__(self):self.n=0;self.denied=False;self.cache={}
 def call(self,label,method,params):
  if self.denied:raise RuntimeError('Provider denied')
  if method not in ('eth_chainId','eth_getCode','eth_getBlockByNumber','eth_call','eth_getTransactionReceipt'):raise ValueError('Read-only RPC only')
  key=json.dumps([method,params],sort_keys=True)
  if key in self.cache:return self.cache[key]
  if self.n>=175:raise RuntimeError('RPC budget reached')
  self.n+=1;time.sleep(1.2);raw=b'';rec={'id':self.n,'label':label,'method':method,'status':'UNKNOWN'}
  try:
   req=urllib.request.Request(RPC,data=json.dumps({'jsonrpc':'2.0','id':self.n,'method':method,'params':params}).encode(),
        headers={'Content-Type':'application/json','User-Agent':'QT-Stage1-ReadOnly-Auction/1'})
   with urllib.request.urlopen(req,timeout=30) as resp:raw=resp.read(1_500_001)
   if len(raw)>1_500_000:raise ValueError('Response size limit')
   x=json.loads(raw)
   if x.get('error'):
    rec['rpc_error']=x['error'];s=str(x['error']).lower()
    if any(x in s for x in ('rate limit','unauthorized','access denied','client adjustable limit')):self.denied=True
    raise RuntimeError(str(x['error'])[:200])
   rec['status']='OK';self.cache[key]=x['result'];return x['result']
  except urllib.error.HTTPError as exc:
   rec['error']=str(exc);raw=exc.read(10000)
   if exc.code in (401,403,429):self.denied=True
   raise
  except Exception as exc:rec['error']=repr(exc);raise
  finally:
   rec['sha256']=hashlib.sha256(raw).hexdigest();rec['length']=len(raw)
   (OUT/'raw').mkdir(exist_ok=True)
   (OUT/f'raw/{self.n:04d}.body').write_bytes(raw)
   save(f'raw/{self.n:04d}.json',rec)
 def read(self,contract,sig,block,*args):
  return self.call(sig,'eth_call',[{'to':contract,'data':data(sig,*args)},hex(block)])

def get_curve_dy(r,block,amt):
 errors=[]
 for sig in ('get_dy(int128,int128,uint256)','get_dy(uint256,uint256,uint256)'):
  try:
   return number(r.read(CURVE,sig,block,0,1,amt)),sig
  except Exception as exc:errors.append(repr(exc))
 raise RuntimeError(';'.join(errors)[:340])

def event_result(r,item):
 kick=item['kick_block'];settle=item.get('next_settlement_block')
 rec=r.call('kicker_receipt','eth_getTransactionReceipt',[item['kicker_tx']])
 if rec['status']!='0x1' or int(rec['blockNumber'],16)!=kick:raise ValueError('Original kick receipt mismatch')
 if not any(l['topics'][0].lower()==KICK and int(l['logIndex'],16)==item['kick_log_index']
   and l['address'].lower()==item['auction'] for l in rec['logs']):raise ValueError('Missing actual kick')
 item['receipt_verified']=True
 for off in (50,180):
  block=kick+off
  if settle and block>=settle:
   item.setdefault('snapshots',[]).append({'offset':off,'status':'ALREADY_SETTLED'});continue
  x={'offset':off,'block':block,'statuses':[]};item.setdefault('snapshots',[]).append(x)
  h=r.call('actual_header','eth_getBlockByNumber',[hex(block),False])
  x['timestamp_utc']=dt.datetime.fromtimestamp(int(h['timestamp'],16),dt.timezone.utc).isoformat()
  available=number(r.read(item['auction'],'available(address)',block,item['from_token']))
  x['available_raw']=str(available)
  if not available:continue
  lot=min(available,int(item['kicked_raw']))
  for div in (10,2):
   take=lot//div
   if take==0:continue
   q={'fraction':div,'take_raw':str(take)}
   x['statuses'].append(q)
   try:
    pay=number(r.read(item['auction'],'getAmountNeeded(address,uint256)',block,item['from_token'],take))
    q['actual_auction_payment_crvusd_raw']=str(pay)
    if pay==0:raise ValueError('Zero auction payment')
    if item['from_token']==USDC:
     crv,dys=get_curve_dy(r,block,take)
     q.update(cash_out_crvusd_raw=str(crv),pool_get_dy_selector=dys,
       gross_crvusd_margin_raw=str(crv-pay),positive_before_cost=crv>pay)
    else:
     results=[]
     for fee in (500,3000):
      row={'fee':fee}
      results.append(row)
      try:
       raw=r.call('crv_to_usdc_quote','eth_call',[{'to':QUOTER,
         'data':data('quoteExactInputSingle((address,address,uint256,uint24,uint160))',
           CRV,USDC,take,fee,0)},hex(block)])
       crvusdc=number(raw);row['usdc_out_raw']=str(crvusdc)
       obtained,sig=get_curve_dy(r,block,crvusdc)
       row.update(crvusd_out_raw=str(obtained),pool_selector=sig,
         gross_crvusd_margin_raw=str(obtained-pay),positive_before_cost=obtained>pay)
      except Exception as exc:row['error']=repr(exc)
     q['dex_paths']=results
   except Exception as exc:q['error']=repr(exc)

def main():
 report={'kind':'Stage1 historical Yearn crvUSD-bid auction-to-cash-quote test',
  'read_only':True,'no_funding_or_trades':True,'not_cash_execution':True,'capture_unmeasured':True,
  'source':'Frozen authenticated 2026-09-10 to 2026-10-01 auction event census, run 39016955510',
  'comparators':'Actual at-state auction obligation versus real quoted from-asset to crvUSD; no residual ignored',
  'cases':[],'complete':False}
 save('REPORT.json',report);r=Rpc()
 try:
  chosen,scope=frozen();report['scope']=scope;report['cases']=chosen;save('REPORT.json',report)
  assert int(r.call('chain_id','eth_chainId',[]),16)==1
  for addr in (CURVE,QUOTER,chosen[0]['auction']):
   assert len(r.call('deployed_code','eth_getCode',[addr,hex(chosen[0]['kick_block'])]))>10
  # Deployment identity proof before pricing; does not presume a pool symbol label.
  assert address(number(r.read(CURVE,'coins(uint256)',chosen[0]['kick_block'],0)))==USDC
  assert address(number(r.read(CURVE,'coins(uint256)',chosen[0]['kick_block'],1)))==CRVUSD
  for item in report['cases']:
   try:event_result(r,item)
   except Exception as exc:item['error']=repr(exc)
   save('REPORT.json',report)
   if r.denied:raise RuntimeError('Provider denied')
  report['complete']=True
 except Exception as exc:report['fatal']=repr(exc);report['traceback']=traceback.format_exc()
 report['requests']=r.n;report['provider_denied']=r.denied
 report['positive_quoted_paths']=sum(y.get('positive_before_cost',False) for c in report['cases'] for x in c.get('snapshots',[]) for q in x.get('statuses',[]) for y in ([q] if 'dex_paths' not in q else q['dex_paths']))
 save('REPORT.json',report)
 print(json.dumps({'complete':report['complete'],'cases':len(report['cases']),'requests':r.n,
  'positive_quoted_paths':report['positive_quoted_paths'],'fatal':report.get('fatal')},indent=2),flush=True)
 if not report['complete']:raise SystemExit('Research incomplete; error is not zero arbitrage')
if __name__=='__main__':main()
