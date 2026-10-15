"""Pure observation of a frozen public liquidation cohort. No transactions or simulations.
One identical fixed-time public GraphQL census, then every Base/USDC receipt (cap100).
Auction metadata is not full solver P&L. No explorer calls after prior access denial.
"""
import json,time,hashlib,urllib.request,urllib.error,datetime as dt
from pathlib import Path
from eth_utils import keccak
OUT=Path('evidence');OUT.mkdir(exist_ok=True);(OUT/'raw').mkdir(exist_ok=True)
RPC='https://mainnet.base.org';API='https://api.morpho.org/graphql'
USDC='0x833589fcd6edb6e08f4c7c32d4f71b54bda02913';ATLAS='0x583dcfef0d240dc80753f0f0b26513fee27d9b77'
START=1791590400;END=1792075518;N=0;RECORDS=[]
def save(n,x):(OUT/n).write_text(json.dumps(x,indent=2))
def req(name,url,body):
 global N
 if N>=110:raise ValueError('fixed request cap')
 if url==RPC:
  if body.get('method')!='eth_getTransactionReceipt':raise ValueError('receipts only')
 elif url==API:
  if not body.get('query','').startswith('query'):raise ValueError('query only')
 else:raise ValueError('endpoint not allowed')
 time.sleep(1);N+=1;r={'name':name,'url':url,'payload':body,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()};b=b'';ans=None
 try:
  q=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'QT-public-auction-census/1'})
  with urllib.request.urlopen(q,timeout=20) as x:b=x.read(3000001);r['http_status']=x.status
  if len(b)>3000000:raise ValueError('body bound')
  ans=json.loads(b);r['status']='API_ERROR' if 'errors' in ans or 'error' in ans else 'OK'
 except urllib.error.HTTPError as e:
  r.update(status='HTTP_ERROR',http_status=e.code,error=str(e));b=e.read(10000)
 except Exception as e:r.update(status='UNAVAILABLE',error=repr(e))
 r.update(sha256=hashlib.sha256(b).hexdigest(),completed_utc=dt.datetime.now(dt.timezone.utc).isoformat());RECORDS.append(r)
 (OUT/'raw'/f'{N:03d}.body').write_bytes(b);save(f'raw/{N:03d}.json',r)
 if r.get('http_status') in (401,403,429):raise RuntimeError('Access/rate boundary; stop')
 return ans

def ws(d):return [int(d[i:i+64],16) for i in range(2,len(d),64)]
def topic(s):return '0x'+keccak(text=s).hex()
TRANSFER=topic('Transfer(address,address,uint256)')
SOLVER=topic('SolverTxResult(address,address,address,address,uint256,bool,bool,uint256)')
META=topic('MetacallResult(address,address,bool,uint256,uint256)')
LIQ=topic('Liquidate(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)')

def main():
 q='query($n:Int!,$skip:Int!,$start:Int!,$end:Int!){marketTransactions(first:$n,skip:$skip,orderBy:Timestamp,orderDirection:Asc,where:{chainId_in:[1,8453,42161],type_in:[Liquidation],timestamp_gte:$start,timestamp_lte:$end}){items{chain{id}txHash timestamp blockNumber txIndex logIndex user{address}market{marketId lltv collateralAsset{address decimals symbol}loanAsset{address decimals symbol}}data{... on MarketTransactionLiquidationData{liquidator repaidAssets repaidShares seizedAssets badDebtAssets badDebtShares}}}}}'
 data=req('frozen_census',API,{'query':q,'variables':{'n':250,'skip':0,'start':START,'end':END}})
 if not isinstance(data,dict) or data.get('errors'):raise ValueError('No usable cohort')
 rows=data['data']['marketTransactions']['items'];coh={}
 for e in rows:
  if e['chain']['id']==8453 and e['market']['loanAsset']['address'].lower()==USDC:coh.setdefault(e['txHash'],[]).append(e)
 result={'frozen_start':START,'frozen_end':END,'indexed_event_count':len(rows),'index_page_complete':len(rows)<250,'all_index_events':rows,'transactions':[],'no_profit_execution':True}
 for tx,ev in list(coh.items())[:100]:
  rec={'tx':tx,'events':ev};result['transactions'].append(rec)
  rr=req('receipt',RPC,{'jsonrpc':'2.0','id':N+1,'method':'eth_getTransactionReceipt','params':[tx]});r=rr.get('result') if isinstance(rr,dict) else None;rec['receipt']=r
  if not r:rec['error']='receipt unavailable';save('auction_census.json',result);continue
  rec['atlas_entrypoint']=r['to'].lower()==ATLAS;rec['solver_results']=[];rec['metacall_results']=[];rec['canonical_match_count']=0
  for l in r['logs']:
   ts=l['topics']
   if not ts:continue
   if l['address'].lower()==ATLAS and ts[0]==SOLVER:
    a=ws(l['data']);rec['solver_results'].append({'solver':'0x'+ts[1][-40:],'solver_from':'0x'+ts[2][-40:],'control':'0x'+ts[3][-40:],'bid_token':'0x'+format(a[0],'040x'),'bid_amount_raw':a[1],'executed':bool(a[2]),'success':bool(a[3]),'result':a[4]})
   if l['address'].lower()==ATLAS and ts[0]==META:
    a=ws(l['data']);rec['metacall_results'].append({'bundler':'0x'+ts[1][-40:],'user':'0x'+ts[2][-40:],'success':bool(a[0]),'eth_paid_to_bundler_raw':a[1],'net_gas_surcharge_raw':a[2]})
   if ts[0]==LIQ:
    a=ws(l['data'])
    for e in ev:
     if int(l['logIndex'],16)==e['logIndex'] and l['transactionHash'].lower()==e['txHash'].lower() and int(r['blockNumber'],16)==e['blockNumber'] and ts[1].lower()==e['market']['marketId'].lower() and '0x'+ts[3][-40:].lower()==e['user']['address'].lower() and a[0]==int(e['data']['repaidAssets']) and a[2]==int(e['data']['seizedAssets']):rec['canonical_match_count']+=1
  rec['network_charge_wei']=int(r['gasUsed'],16)*int(r['effectiveGasPrice'],16)+int(r.get('l1Fee','0x0'),16)
  save('auction_census.json',result)
 summary={'requests':N,'indexed_events':len(rows),'selected_events':sum(len(e) for e in coh.values()),'selected_transactions':len(coh),'receipts':sum(bool(x.get('receipt')) for x in result['transactions']),'canonical_event_matches':sum(x.get('canonical_match_count',0) for x in result['transactions']),'atlas_transactions':sum(x.get('atlas_entrypoint',False) for x in result['transactions']),'atlas_events':sum(len(x['events']) for x in result['transactions'] if x.get('atlas_entrypoint')),'atlas_repaid_raw':sum(int(e['data']['repaidAssets']) for x in result['transactions'] if x.get('atlas_entrypoint') for e in x['events']),'all_repaid_raw':sum(int(e['data']['repaidAssets']) for e in rows if e['chain']['id']==8453 and e['market']['loanAsset']['address'].lower()==USDC),'successful_solver_events':sum(s['success'] for x in result['transactions'] for s in x.get('solver_results',[])),'request_statuses':{s:sum(x['status']==s for x in RECORDS) for s in {x['status'] for x in RECORDS}},'finished_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'profit_verified':False}
 save('auction_summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
