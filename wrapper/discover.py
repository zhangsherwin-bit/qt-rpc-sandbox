"""Read-only follow-through of the previously reported Stake DAO frxUSD/msUSD lead.
Retrospective discovery: Jul-Sep 2026 only; no reserved Oct 3-9 observations.
No keys, signatures, state overrides, calls changing live state, or trading.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, time, urllib.request, urllib.error
from pathlib import Path
from eth_abi import encode, decode
from eth_utils import keccak
OUT=Path('evidence'); OUT.mkdir(exist_ok=True); (OUT/'raw').mkdir(exist_ok=True)
API='https://api.morpho.org/graphql'; RPC='https://rpc-eth.blockmachine.io'
FRX='0xCAcd6fd266aF91b8AeD52aCCc382b4e165586E29'; USDC='0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
LP='0x9A9e2e70919c75D80aAaA1D483c46CdBb8ac4d1b'
CUST='0x4F95C5bA0C7c69FB2f9340E190cCeE890B3bd87c'
USTB_EXIT='0x00000000564ee6a571C5819057f27bb671E78Bd5'
ZERO='0x'+'00'*20; START=1782864000; END=1790812799
MAX_CALLS=140; MAX_RU=230; MAX_SECONDS=650
RECORDS=[]; BLOCKED=set(); BEG=time.monotonic(); LAST=0.; RU=0

def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def save(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2,default=str))
def request(name,url,payload,cost=1):
 global LAST,RU
 if url not in (API,RPC) or url in BLOCKED:raise RuntimeError('endpoint outside permitted read scope or previously denied')
 if url==API:
  if not payload.get('query','').lstrip().startswith('query'):raise ValueError('query only')
 elif payload.get('method') not in {'eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call','eth_getTransactionReceipt','eth_getTransactionByHash','debug_traceTransaction'}:raise ValueError('read-only RPC allowlist')
 if len(RECORDS)>=MAX_CALLS or RU+cost>MAX_RU or time.monotonic()-BEG>MAX_SECONDS:raise RuntimeError('bounded budget exhausted')
 if url==RPC:time.sleep(max(0,2*cost-(time.monotonic()-LAST)))
 else:time.sleep(.5)
 RU+=cost; rec={'name':name,'url':url,'payload':payload,'started_utc':utc(),'estimated_RU':cost};body=b'';obj=None
 try:
  req=urllib.request.Request(url,json.dumps(payload).encode(),{'Content-Type':'application/json','User-Agent':'QT-Public-Wrapper-Research/1'})
  with urllib.request.urlopen(req,timeout=40) as res:
   rec['http_status']=res.status;body=res.read(10000001)
   if len(body)>10000000:raise ValueError('body cap')
  obj=json.loads(body);rec['status']='API_ERROR' if isinstance(obj,dict) and ('errors' in obj or 'error' in obj) else 'OK'
 except urllib.error.HTTPError as e:
  body=e.read(100000);rec.update(status='HTTP_ERROR',http_status=e.code,error=str(e))
  if e.code in (401,403,429):BLOCKED.add(url)
 except Exception as e:rec.update(status='UNAVAILABLE',error=repr(e))
 rec.update(completed_utc=utc(),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body));n=len(RECORDS)+1
 (OUT/'raw'/f'{n:04d}.body').write_bytes(body);(OUT/'raw'/f'{n:04d}.json').write_text(json.dumps(rec,indent=2));RECORDS.append(rec);LAST=time.monotonic()
 if url in BLOCKED:raise RuntimeError('provider access/rate denial, stopping that endpoint')
 return obj

def gql(n,q,v=None):
 r=request(n,API,{'query':q,'variables':v or {}})
 if not isinstance(r,dict) or r.get('errors'):raise ValueError(str(r)[:1500])
 return r['data']
def rpc(n,m,p,c=1):
 r=request(n,RPC,{'jsonrpc':'2.0','id':len(RECORDS)+1,'method':m,'params':p},c)
 if not isinstance(r,dict) or 'result' not in r:raise ValueError(str(r)[:800])
 return r['result']
def calldata(s,t=(),a=()):return '0x'+keccak(text=s)[:4].hex()+encode(t,a).hex()
def view(n,to,s,t=(),a=(),block='latest',out=('uint256',)):
 r=rpc(n,'eth_call',[{'to':to,'data':calldata(s,t,a)},block]);return decode(list(out),bytes.fromhex(r[2:]))
def safeview(*a,**kw):
 try:return {'ok':True,'value':view(*a,**kw)}
 except Exception as e:return {'ok':False,'error':repr(e)}
def flow_summary(tx,receipt,trace,loan):
 actors={tx['from'].lower(),tx['to'].lower()};deltas={};transfers=[];native=[];calls=[]
 topic='0x'+keccak(text='Transfer(address,address,uint256)').hex()
 for log in receipt['logs']:
  topics=log['topics']
  if len(topics)!=3 or topics[0].lower()!=topic:continue
  f='0x'+topics[1][-40:].lower();t='0x'+topics[2][-40:].lower();v=int(log['data'],16);token=log['address'].lower()
  change=v*(int(t in actors)-int(f in actors));deltas[token]=deltas.get(token,0)+change
  transfers.append({'token':token,'from':f,'to':t,'amount':str(v)})
 def walk(n):
  if not isinstance(n,dict) or n.get('error'):return
  calls.append({'type':n.get('type'),'from':n.get('from'),'to':n.get('to'),'input':n.get('input'),'output':n.get('output'),'value':n.get('value'),'gasUsed':n.get('gasUsed')})
  if int(n.get('value','0x0'),16) and n.get('type','').upper() in {'CALL','CREATE','CREATE2','SELFDESTRUCT'}:native.append({k:n.get(k) for k in ('type','from','to','value')})
  for ch in n.get('calls',[]):walk(ch)
 walk(trace)
 net=sum(int(n['value'],16)*(int(n.get('to','').lower() in actors)-int(n.get('from','').lower() in actors)) for n in native)
 return {'actor_scope':sorted(actors),'token_transfer_deltas':{k:str(v) for k,v in deltas.items() if v},'native_delta_before_gas_wei':str(net),'sender_gas_wei':str(int(receipt['gasUsed'],16)*int(receipt['effectiveGasPrice'],16)),'transfers':transfers,'native_transfers':native,'calls':calls,'warning':'Sender plus tx.to only. External recipient ownership unknown; wrapped-native burns/unwraps require reconciliation. No net profit valuation claimed.'}

def main():
 s={'started_utc':utc(),'transactions_sent':0,'profit_verified':False,'scope':'Follow unfinished frxUSD/msUSD wrapper lead; retrospective sample selection before reading traces','errors':[],'selected':[]}
 try:
  schema=gql('filter_schema','query {m:__type(name:"MarketFilters"){inputFields{name}} t:__type(name:"TransactionFilters"){inputFields{name}}}')
  save('schema.json',schema)
  names={x['name'] for x in (schema.get('m') or {}).get('inputFields',[])}
  if 'loanAssetAddress_in' in names: filt='loanAssetAddress_in:["'+FRX+'"]'
  elif 'loanAssetSelector_in' in names:filt='loanAssetSelector_in:["1:'+FRX+'"]'
  else:raise ValueError('no supported exact loan-token market filter')
  q='query($skip:Int!){markets(first:100,skip:$skip,where:{chainId_in:[1],'+filt+'}){items{marketId lltv irmAddress collateralAsset{address symbol decimals}loanAsset{address symbol decimals}oracle{address}morphoBlue{address}state{borrowAssets borrowAssetsUsd collateralAssets}}}}'
  markets=[];complete=False
  for skip in (0,100,200):
   rows=gql('markets_'+str(skip),q,{'skip':skip})['markets']['items'];markets+=rows
   if len(rows)<100:complete=True;break
  s['market_listing_complete']=complete;s['markets']=markets;save('summary.json',s)
  if rpc('chain','eth_chainId',[])!='0x1':raise ValueError('Ethereum chain mismatch')
  h=rpc('latest_header','eth_getBlockByNumber',['latest',False]);s['current_header']=h
  matches=[]
  for m in markets:
   sym=(m.get('collateralAsset') or {}).get('symbol','').lower()
   if any(x in sym for x in ('msusd','frxms')):matches.append(m)
  s['matched_markets']=matches;s['matched_market_limit']=6
  for m in matches[:6]:
   mid=m['marketId'];ct=m['collateralAsset']['address'];m['asset_view']=safeview('asset_'+mid[:10],ct,'asset()',block=h['number'],out=('address',))
  ids=[m['marketId'] for m in matches[:6]]
  if ids:
   q='query($ids:[String!],$start:Int!,$end:Int!,$skip:Int!){marketTransactions(first:250,skip:$skip,orderBy:Timestamp,orderDirection:Asc,where:{chainId_in:[1],marketUniqueKey_in:$ids,type_in:[Liquidation],timestamp_gte:$start,timestamp_lte:$end}){items{txHash timestamp blockNumber txIndex logIndex user{address}market{marketId lltv irmAddress collateralAsset{address decimals symbol}loanAsset{address decimals symbol}oracle{address}morphoBlue{address}}data{...on MarketTransactionLiquidationData{liquidator repaidAssets repaidShares seizedAssets badDebtAssets badDebtShares}}}}}'
   events=[];complete=False
   for skip in (0,250,500,750):
    rows=gql('events_'+str(skip),q,{'ids':ids,'start':START,'end':END,'skip':skip})['marketTransactions']['items'];events+=rows
    if len(rows)<250:complete=True;break
   s.update(events=events,event_listing_complete=complete,event_window=[START,END]);save('summary.json',s)
   days={}
   for e in events:
    day=dt.datetime.fromtimestamp(e['timestamp'],dt.timezone.utc).date().isoformat();old=days.get(day)
    if old is None or int(e['data']['repaidAssets'])>int(old['data']['repaidAssets']):days[day]=e
   selected=[days[d] for d in sorted(days)[:3]];s['selection_rule']='Largest repayment per UTC event day, first three dates. Frozen before receipt/trace reads; development sample.'
   save('selection.json',selected)
   for j,e in enumerate(selected):
    r={'event':e};s['selected'].append(r)
    try:
     txh=e['txHash'];receipt=rpc('receipt_'+str(j),'eth_getTransactionReceipt',[txh]);tx=rpc('tx_'+str(j),'eth_getTransactionByHash',[txh]);head=rpc('header_'+str(j),'eth_getBlockByNumber',[receipt['blockNumber'],False])
     if int(receipt['blockNumber'],16)!=e['blockNumber'] or receipt['blockHash']!=head['hash']:raise ValueError('canonical event mismatch')
     trace=rpc('trace_'+str(j),'debug_traceTransaction',[txh,{'tracer':'callTracer','timeout':'25s'}],30)
     r.update(receipt=receipt,transaction=tx,header=head,flows=flow_summary(tx,receipt,trace,FRX));save('trace_'+str(j)+'.json',trace)
    except Exception as ex:r['error']=repr(ex)
    save('summary.json',s)
  # Publicly documented stablecoin exits: quote/physical-cash checks only.
  s['cash_exits']=[]
  for name,target in [('USDC_custodian',CUST),('USTB_USDC_router',USTB_EXIT)]:
   rec={'name':name,'target':target,'block':h['number']};s['cash_exits'].append(rec)
   rec['code_present']=rpc(name+'_code','eth_getCode',[target,h['number']])!='0x'
   rec['USDC_custody']=safeview(name+'_usdc',USDC,'balanceOf(address)',['address'],[target],block=h['number'])
   if rec['code_present']:
    rec['asset']=safeview(name+'_asset',target,'asset()',block=h['number'],out=('address',))
    rec['preview_1000_frx']=safeview(name+'_preview',target,'previewRedeem(uint256)',['uint256'],[1000*10**18],block=h['number'])
    rec['totalAssets']=safeview(name+'_assets',target,'totalAssets()',block=h['number'])
  save('summary.json',s)
 except Exception as e:s['errors'].append(repr(e))
 s.update(completed_utc=utc(),request_count=len(RECORDS),estimated_RU=RU);save('summary.json',s)
 print(json.dumps({'started':s['started_utc'],'completed':s['completed_utc'],'requests':len(RECORDS),'errors':s['errors'],'market_count':len(s.get('markets',[])),'matched':[(m['marketId'],m['collateralAsset']['symbol']) for m in s.get('matched_markets',[])],'event_count':len(s.get('events',[])),'selected':[{k:r[k] for k in ('event','error') if k in r} for r in s['selected']],'cash_exits':s.get('cash_exits')},indent=2))
if __name__=='__main__':main()
