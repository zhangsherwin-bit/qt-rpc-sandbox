"""Public economic evidence only. No signing, broadcasting, balances or storage overrides.
Midnight: paginated Base USDC market/offer discovery and exact borrower/cash reads.
Blue: fresh indexed liquidation census outside the reserved Oct 3-9 period.
Vault: native ERC4626 views and finite-size canonical Uniswap Quoter calls.
Positive quotes are NOT executions or profit claims. All raw responses retained.
"""
from __future__ import annotations
import datetime as dt,hashlib,json,time,traceback,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from eth_abi import encode,decode
from eth_utils import keccak,to_checksum_address
OUT=Path('evidence');OUT.mkdir(exist_ok=True);(OUT/'raw').mkdir(exist_ok=True)
API='https://api.morpho.org';RPC='https://mainnet.base.org'
CORE='0xAdedD8ab6dE832766Fedf0FaC4992E5C4D3EA18A';USDC='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
YO='0x0000000f2eb9f69274678c76222b35eec7588a65'
MULTI='0xcA11bde05977b3631167028862bE2a173976CA11'
FACTORY='0x33128a8fC17869897dcE68Ed026d694621f6FDfD'
QUOTER='0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a'
MT='(uint256,address,address,(address,uint256,uint256,address)[],uint256,uint256,address,address)'
W=10**18; SCALE=10**36
MAX_REQUESTS=280;END=time.monotonic()+600;COUNT=0;RECORDS=[];STOP_HOSTS=set()
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def save(n,x): (OUT/n).write_text(json.dumps(x,indent=2,default=str))
class Boundary(Exception):pass
def request(name,url,payload=None):
 global COUNT
 parsed=urllib.parse.urlsplit(url)
 if parsed.scheme!='https' or parsed.hostname not in {'api.morpho.org','mainnet.base.org','api.dexscreener.com'}:raise ValueError('unapproved endpoint')
 if parsed.hostname in STOP_HOSTS:raise Boundary('host access/rate boundary already encountered')
 if payload is not None:
  if parsed.hostname=='mainnet.base.org':
   if payload.get('method') not in {'eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call','eth_getBalance'}:raise ValueError('unapproved RPC method')
  elif parsed.hostname=='api.morpho.org' and 'query' in payload:
   if not payload['query'].lstrip().startswith('query'):raise ValueError('GraphQL read queries only')
  else:raise ValueError('unapproved POST')
 if COUNT>=MAX_REQUESTS or time.monotonic()>END:raise Boundary('fixed total budget reached')
 time.sleep(0.9);COUNT+=1
 rec={'name':name,'number':COUNT,'url':url,'payload':payload,'started_utc':utc()};body=b'';res=None
 try:
  req=urllib.request.Request(url,data=None if payload is None else json.dumps(payload).encode(),headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'QT-Public-Economic-Research/3'})
  with urllib.request.urlopen(req,timeout=18) as r:
   body=r.read(4000001);rec['http_status']=r.status
  if len(body)>4000000:raise ValueError('body cap reached')
  res=json.loads(body);rec['status']='API_ERROR' if isinstance(res,dict) and ('errors' in res or 'error' in res) else 'OK'
 except urllib.error.HTTPError as e:
  body=e.read(50000);rec.update(http_status=e.code,status='HTTP_ERROR',error=str(e))
  if e.code in (401,403,429):STOP_HOSTS.add(parsed.hostname)
 except Exception as e:rec.update(status='UNAVAILABLE',error=repr(e))
 rec.update(completed_utc=utc(),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
 (OUT/'raw'/f'{COUNT:04d}.body').write_bytes(body);(OUT/'raw'/f'{COUNT:04d}.json').write_text(json.dumps(rec,indent=2));RECORDS.append(rec)
 return res
def get(n,path,params=None):return request(n,API+path+('?' +urllib.parse.urlencode(params) if params else ''))
def rpc(n,method,params):
 r=request(n,RPC,{'jsonrpc':'2.0','id':COUNT+1,'method':method,'params':params})
 if not isinstance(r,dict) or 'result' not in r:raise ValueError('RPC unavailable: '+str(r)[:250])
 return r['result']
def data(sig,types=(),vals=()):return '0x'+keccak(text=sig)[:4].hex()+encode(types,vals).hex()
def call(n,to,d,block):return bytes.fromhex(rpc(n,'eth_call',[{'to':to,'data':d,'gas':hex(14000000)},block])[2:])
def batch(n,items,block):
 raw=call(n,MULTI,data('aggregate3((address,bool,bytes)[])',['(address,bool,bytes)[]'],[[(to,True,bytes.fromhex(d[2:])) for to,d in items]]),block)
 return decode(['(bool,bytes)[]'],raw)[0]
def words(b):
 if not b or len(b)%32:raise ValueError('malformed word return')
 return [int.from_bytes(b[i:i+32],'big') for i in range(0,len(b),32)]
def paged(n,path,params,pages=4):
 allrows=[];seen=set();cursor=None
 for i in range(pages):
  p=dict(params)
  if cursor:p['cursor']=cursor
  r=get(f'{n}_{i}',path,p)
  if not isinstance(r,dict) or not isinstance(r.get('data'),list):return allrows,False,r
  allrows.extend(r['data']);cursor=r.get('cursor')
  if not cursor:return allrows,True,None
  if cursor in seen:break
  seen.add(cursor)
 return allrows,False,{'remaining_cursor':cursor}
def lif(cp):return W*W//(W-int(cp[2])*(W-int(cp[1]))//W)
def ceil(a,b):return (a+b-1)//b

def midnight():
 out={'stage':'public discovery and necessary economic conditions, NOT execution','markets':[],'errors':[]}
 listing,complete,err=paged('midnight_all_USDC','/v0/midnight/markets',{'chain_ids':8453,'loan_assets':USDC,'limit':100},4)
 out.update(listing_complete=complete,listing_error=err,listed_rows=listing);save('midnight.json',out)
 # Included despite maturity; app book absence is not protocol-wide absence.
 chosen=[m for m in listing if int(m.get('total_units','0'))>=100*10**6]
 chosen.sort(key=lambda m:(not m.get('listed',False),-int(m.get('total_units',0))))
 out['omitted_market_ids']=[m['market_id'] for m in chosen[24:]];chosen=chosen[:24]
 for m in chosen:
  rec={'market_id':m['market_id'],'metadata':m};out['markets'].append(rec)
  try:
   if m.get('listed') and m['maturity']>int(dt.datetime.now(dt.timezone.utc).timestamp()):
    for side in ['asks','bids']:
     r=get('book_'+side+'_'+m['market_id'][:10],f"/v0/midnight/books/{m['market_id']}/{side}/takeable-offers")
     rec[side]=r
   ps,pc,pe=paged('positions_'+m['market_id'][:10],f"/v0/midnight/markets/{m['market_id']}/positions",{'types':'borrow','limit':100,'sort_by':'debt','sort_direction':'desc'},3)
   rec.update(api_positions=ps,position_discovery_complete=pc,position_error=pe)
  except Exception as e:rec['discovery_error']=repr(e)
  save('midnight.json',out)
 if int(rpc('chain','eth_chainId',[]),16)!=8453:raise ValueError('wrong chain')
 head=rpc('pinned_block','eth_getBlockByNumber',['latest',False]);B=head['number'];timestamp=int(head['timestamp'],16)
 out['snapshot']={k:head[k] for k in ['number','hash','timestamp','baseFeePerGas']}
 for rec in out['markets']:
  mid=rec['market_id']
  try:
   rs=batch('market_views_'+mid[:10],[(CORE,data('toMarket(bytes32)',['bytes32'],[bytes.fromhex(mid[2:])])),(CORE,data('marketState(bytes32)',['bytes32'],[bytes.fromhex(mid[2:])]))],B)
   if not all(x[0] for x in rs):raise ValueError('market view failed')
   m=decode([MT],rs[0][1])[0];st=words(rs[1][1]);rec['market_state']=st;rec['decoded_market']=m
   reconstructed=keccak(b'\xff'+bytes.fromhex(m[1][2:])+b'\x00'*32+keccak(bytes.fromhex('600b380380600b5f395ff3')+encode([MT],[m])))
   if reconstructed.hex()!=mid[2:].lower() or m[0]!=8453 or m[1].lower()!=CORE.lower() or m[2].lower()!=USDC.lower():raise ValueError('market identity mismatch')
   rec['id_checked']=True;rec['withdrawable_USDC']=st[2]/1e6;rec['canonical_total_units_USDC']=st[0]/1e6
   oracle_results=batch('oracles_'+mid[:10],[(cp[3],data('price()')) for cp in m[3]],B)
   prices=[words(v)[0] if ok else None for ok,v in oracle_results];rec['prices']=prices
   positions=rec.get('api_positions',[]);rec['borrower_results']=[];sumdebt=0;allread=True
   for off in range(0,min(len(positions),200),40):
    cohort=positions[off:off+40];items=[]
    for p in cohort:
     u=p['user_address'];items.append((CORE,data('position(bytes32,address)',['bytes32','address'],[bytes.fromhex(mid[2:]),u])))
     items.extend((CORE,data('collateral(bytes32,address,uint256)',['bytes32','address','uint256'],[bytes.fromhex(mid[2:]),u,j])) for j in range(len(m[3])))
    rr=batch('borrowers_'+mid[:10]+'_'+str(off),items,B);step=1+len(m[3])
    for j,p in enumerate(cohort):
     row={'borrower':p['user_address']};rec['borrower_results'].append(row);part=rr[j*step:(j+1)*step]
     if not all(x[0] for x in part):row['error']='view failed';allread=False;continue
     pos=words(part[0][1]);amounts=[words(x[1])[0] for x in part[1:]];debt=pos[4];sumdebt+=debt
     row.update(debt_raw=debt,amounts_raw=amounts,bitmap=pos[5])
     if any(a and price is None for a,price in zip(amounts,prices)):row['error']='unknown active oracle';allread=False;continue
     maxdebt=sum((a*(p or 0)//SCALE)*int(cp[1])//W for a,p,cp in zip(amounts,prices,m[3]))
     recover=sum(ceil(ceil(a*(p or 0),SCALE)*W,lif(cp)) for a,p,cp in zip(amounts,prices,m[3]))
     row.update(max_debt_raw=maxdebt,health_eligible=debt>maxdebt,post_maturity_eligible=debt>0 and timestamp>m[4],estimated_bad_debt_raw=max(0,debt-recover),cash_candidates=[])
     for i,cp in enumerate(m[3]):
      if cp[0].lower()!=USDC.lower() or amounts[i]==0 or prices[i] is None:continue
      for post in [False,True]:
       if not (row['post_maturity_eligible'] if post else row['health_eligible']):continue
       if row['estimated_bad_debt_raw']>0:continue
       l=lif(cp)
       if post:l=min(l,W+(l-W)*(timestamp-m[4])//3600)
       cap=(amounts[i]*prices[i]//SCALE)*W//l;limit=min(debt,cap)
       if not post and cp[1]<W:
        mx=ceil((debt-maxdebt)*W*W,W*W-l*cp[1])
        if max(0,cap-mx)>=m[5]:limit=min(limit,mx)
       seize=(limit*l//W)*SCALE//prices[i]
       row['cash_candidates'].append({'index':i,'post':post,'repayment_raw':limit,'seized_raw':seize,'cash_gap_before_costs_raw':seize-limit,'status':'ARITHMETIC_ONLY_NOT_EXECUTED'})
   rec['borrower_coverage']={'read_debt_sum_raw':sumdebt,'canonical_debt_raw':st[0]-st[2],'reconciles':allread and len(positions)<=200 and rec.get('position_discovery_complete') and sumdebt==st[0]-st[2]}
  except Exception as e:rec['state_error']=repr(e)
  save('midnight.json',out)
 return out

def blue_census():
 start=int(dt.datetime(2026,10,10,tzinfo=dt.timezone.utc).timestamp());end=int(dt.datetime.now(dt.timezone.utc).timestamp())
 q='''query($n:Int!,$skip:Int!,$start:Int!,$end:Int!){marketTransactions(first:$n,skip:$skip,orderBy:Timestamp,orderDirection:Asc,where:{chainId_in:[1,8453,42161],type_in:[Liquidation],timestamp_gte:$start,timestamp_lte:$end}){items{chain{id} txHash timestamp blockNumber txIndex logIndex user{address} market{marketId lltv irmAddress collateralAsset{address decimals symbol}loanAsset{address decimals symbol} oracle{address}morphoBlue{address}}data{... on MarketTransactionLiquidationData{liquidator repaidAssets repaidShares seizedAssets badDebtAssets badDebtShares}}}}}'''
 rows=[];complete=False;err=None
 for skip in range(0,2000,250):
  r=request('blue_events_'+str(skip),API+'/graphql',{'query':q,'variables':{'n':250,'skip':skip,'start':start,'end':end}})
  if not isinstance(r,dict) or r.get('errors'):err=r;break
  p=r['data']['marketTransactions']['items'];rows+=p
  if len(p)<250:complete=True;break
  save('blue_events.json',{'start':start,'end':end,'complete':False,'events':rows})
 out={'start':start,'end':end,'complete':complete,'error':err,'events':rows,'note':'Indexed event observations, not own capture or terminal profit; Oct 3-9 not queried.'};save('blue_events.json',out);return out

def vault_quotes():
 out={'note':'Quotes and protocol views only. previewRedeem may be gross of fees or differ from actual cash; no execution claim.','quotes':[]}
 h=rpc('vault_snapshot','eth_getBlockByNumber',['latest',False]);B=h['number'];out['block']=h
 views=['asset()','decimals()','totalAssets()','totalSupply()']
 rr=batch('vault_views',[(YO,data(s)) for s in views]+[(USDC,data('balanceOf(address)',['address'],[YO]))],B)
 out['vault_views']=[{'signature':s,'ok':v[0],'raw':v[1].hex()} for s,v in zip(views+['USDC.balanceOf(vault)'],rr)]
 fees=[100,500,3000,10000];rs=batch('uniswap_pools',[(FACTORY,data('getPool(address,address,uint24)',['address','address','uint24'],[USDC,YO,f])) for f in fees],B)
 out['pools']=[]
 for f,(ok,r) in zip(fees,rs):
  p=decode(['address'],r)[0] if ok and r else None;out['pools'].append({'fee':f,'address':p})
  if not p or int(p,16)==0:continue
  for shares in [10,100,1000,5000,10000]:
   q=shares*10**6;rec={'fee':f,'shares_raw':q,'pool':p};out['quotes'].append(rec)
   try:
    redeem=words(call('preview_redeem',YO,data('previewRedeem(uint256)',['uint256'],[q]),B))[0]
    raw=call('quote_exact_output',QUOTER,data('quoteExactOutputSingle((address,address,uint256,uint24,uint160))',['(address,address,uint256,uint24,uint160)'],[(USDC,YO,q,f,0)]),B)
    cost=words(raw)[0];rec.update(preview_redeem_raw=redeem,swap_cost_raw=cost,preview_gap_raw=redeem-cost)
   except Exception as e:rec['error']=repr(e)
   save('vault_quotes.json',out)
 out['dex_discovery']=request('yoUSD_Dexscreener','https://api.dexscreener.com/token-pairs/v1/base/'+YO)
 save('vault_quotes.json',out);return out

def main():
 summary={'started_utc':utc(),'no_transactions_submitted':True,'no_state_overrides':True,'profit_verified':False,'stage_results':{}}
 for name,fn in [('midnight',midnight),('blue_census',blue_census),('vault_quotes',vault_quotes)]:
  try:
   r=fn()
   if name=='midnight':
    markets=r.get('markets',[]);summary['stage_results'][name]={'market_rows':len(r.get('listed_rows',[])),'listing_complete':r.get('listing_complete'),'examined':len(markets),'omitted':r.get('omitted_market_ids'),'borrowers':sum(len(m.get('borrower_results',[])) for m in markets),'cash_candidates':sum(len(p.get('cash_candidates',[])) for m in markets for p in m.get('borrower_results',[])),'asks':sum(len(m.get('asks',{}).get('data',[])) if isinstance(m.get('asks'),dict) else 0 for m in markets)}
   elif name=='blue_census':summary['stage_results'][name]={'events':len(r.get('events',[])),'complete':r.get('complete'),'error':r.get('error')}
   else:summary['stage_results'][name]={'quotes':r['quotes'],'pools':r.get('pools')}
  except Exception as e:summary['stage_results'][name]={'error':repr(e)};save(name+'_failure.json',{'error':repr(e),'traceback':traceback.format_exc()})
  save('summary.json',summary)
 summary.update(finished_utc=utc(),request_count=COUNT,status_counts={s:sum(x.get('status')==s for x in RECORDS) for s in set(x.get('status') for x in RECORDS)})
 save('summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
