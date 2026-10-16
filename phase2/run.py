"""Read-only Phase 2, adapted from supplied prepared harness. Public calls are opt-in.
Fixed public hosts; no keys/signing/balance overrides/transactions. Bounded sample,
not a complete protocol census. Positive calls are gross cash, not capturable profit.
"""
import argparse,json,pathlib,time,urllib.request,urllib.parse,urllib.error,hashlib,datetime
from codec import *
ROOT=pathlib.Path(__file__).resolve().parent
API='https://api.morpho.org';RPC='https://mainnet.base.org'
EXPECTED_RUNTIME_SHA='7884845d7adfa271bc0715c0f6205a006f053921128680defea915fa8a8a831d'
WAD=10**18;O=10**36

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class Stop(Exception):pass
class Client:
 def __init__(self,root,limit):self.root=root;root.mkdir(parents=True,exist_ok=True);self.count=0;self.limit=limit;self.last=0;self.last_http_status=None
 def request(self,url,payload=None):
  parsed=urllib.parse.urlsplit(url)
  if parsed.scheme!='https' or parsed.hostname not in {'api.morpho.org','mainnet.base.org'} or parsed.username or parsed.password:raise ValueError('Unapproved endpoint')
  if parsed.hostname=='api.morpho.org' and not parsed.path.startswith('/v0/midnight/'):raise ValueError('Unapproved API path')
  if self.count>=self.limit:raise Stop('request budget reached')
  time.sleep(max(0,1.8-(time.monotonic()-self.last)));self.count+=1
  rec={'url':url,'payload':payload,'started_utc':utc()};body=b'';ret=None;stop=False
  try:
   req=urllib.request.Request(url,data=None if payload is None else json.dumps(payload).encode(),headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'QT-read-only-research/phase2'})
   with urllib.request.urlopen(req,timeout=18) as r:
    body=r.read(2_000_001);rec['http_status']=r.status
    if len(body)>2_000_000:raise ValueError('response byte budget exceeded')
   ret=json.loads(body)
  except urllib.error.HTTPError as e:rec['http_status']=e.code;body=e.read(2_000_000);rec['error']=str(e);stop=e.code in (401,403,429)
  except Exception as e:rec['error']=repr(e)
  rec.update(completed_utc=utc(),body_sha256=hashlib.sha256(body).hexdigest());p=self.root/f'{self.count:04d}'
  p.with_suffix('.json').write_text(json.dumps(rec,indent=2));p.with_suffix('.body').write_bytes(body);self.last=time.monotonic();self.last_http_status=rec.get('http_status')
  if stop:raise Stop('access/rate boundary; no retry or bypass')
  return ret
 def get(self,path,**params):return self.request(API+path+('?' +urllib.parse.urlencode(params) if params else ''))
 def rpc(self,method,params):
  if method not in {'eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call'}:raise ValueError('RPC method not allowlisted')
  return self.request(RPC,{'jsonrpc':'2.0','id':self.count+1,'method':method,'params':params})
 def value(self,method,params):
  r=self.rpc(method,params)
  if not isinstance(r,dict) or 'error' in r or 'result' not in r:raise ValueError('RPC unavailable: '+str(r)[:300])
  return r['result']
 def view(self,to,sig,args,block):return decode_words(self.value('eth_call',[{'to':to,'data':view_data(sig,*args)},block]))
def rows(r):
 if not isinstance(r,dict) or not isinstance(r.get('data'),list):raise ValueError('missing list response')
 return r['data']
def valid_offer(raw,m):
 o=raw['offer'];om=o['market']
 return om.get('midnight','').lower()==CORE.lower() and om['chain_id']==8453 and om['loan_token'].lower()==USDC.lower() and market_id(om)==m['market_id'] and raw.get('market_id')==m['market_id'] and o['buy'] is False and int(raw['units'])>0

def maximum_lif(c):return WAD*WAD//(WAD-int(c['liquidation_cursor'])*(WAD-int(c['lltv']))//WAD)
def ceildiv(a,b):return (a+b-1)//b

def legal_cash_sizes(m,debt,amounts,prices,now):
 maximum_debt=0;recovery=0
 for i,cp in enumerate(m['collaterals']):
  amount=amounts.get(i,0);price=prices.get(i,0)
  if amount and price<=0:raise ValueError('unknown oracle')
  maximum_debt+=(amount*price//O)*int(cp['lltv'])//WAD
  recovery+=ceildiv(ceildiv(amount*price,O)*WAD,maximum_lif(cp))
 if debt>recovery:return [],'bad_debt_unsupported'
 modes=[]
 if debt>maximum_debt:modes.append(False)
 if now>int(m['maturity']):modes.append(True)
 candidates=[]
 for i,cp in enumerate(m['collaterals']):
  if cp['token'].lower()!=USDC.lower() or not amounts.get(i):continue
  for post in modes:
   lif=maximum_lif(cp)
   if post:lif=min(lif,WAD+(lif-WAD)*(now-int(m['maturity']))//3600)
   cap=(amounts[i]*prices[i]//O)*WAD//lif;limit=min(debt,cap)
   if not post and int(cp['lltv'])<WAD:
    rcf=ceildiv((debt-maximum_debt)*WAD*WAD,WAD*WAD-lif*int(cp['lltv']))
    if max(0,cap-rcf)>=int(m['rcf_threshold']):limit=min(limit,rcf)
   for den in (1,2,4):
    q=limit//den
    if q>0 and (i,post,q) not in candidates:candidates.append((i,post,q))
 return candidates,'candidate_sizes' if candidates else 'no_current_supported_cash_liquidation'

def probe(c,runtime,data,B,context):
 r=c.rpc('eth_call',[{'from':CALLER,'to':PROBE,'gas':hex(12_000_000),'data':data},B,{PROBE:{'code':runtime}}])
 out={'context':context,'rpc_response':r,'block':B,'observed_utc':utc(),'only_code_overridden':True,'status':'UNAVAILABLE_OR_REVERTED_NOT_GLOBAL_REJECTION'}
 if isinstance(r,dict) and 'result' in r:
  try:
   v=decode_words(r['result'])
   if len(v)!=2 or v[0]<=0:raise ValueError('invalid positive cash result')
   out.update(status='CASH_POSITIVE_SIMULATION_BEFORE_COSTS_AND_CAPTURE',cash_raw=str(v[0]),cash_USDC=v[0]/1e6,internal_gas=v[1])
  except Exception as e:out.update(status='UNRECOGNIZED_RETURN',error=repr(e))
 return out

def collect(limit=300,market_limit=12,position_limit=32):
 out=ROOT/('public_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(exist_ok=True);c=Client(out/'raw',limit)
 s={'started_utc':utc(),'markets':[],'probes':[],'transactions_sent':0,'profit_claimed':False,'warnings':['REST and RPC not atomic.','Independent reset-state profits cannot be added.','Internal gas excludes full transaction, L1, deployment and inclusion costs.','Bad debt outside supported probe.','Listed Base USDC only; bounded borrower discovery.']}
 try:
  listing=[];cursor=None;seen=set()
  for page in range(3):
   params={'chain_ids':8453,'loan_assets':USDC,'listed':'true','limit':100}
   if cursor:params['cursor']=cursor
   r=c.get('/v0/midnight/markets',**params);listing.extend(rows(r));cursor=r.get('cursor')
   if not cursor:break
   if cursor in seen:break
   seen.add(cursor)
  s['listing_census_incomplete']=bool(cursor);s['market_listing']=listing
  chosen=[];seen_ids=set();s['identity_rejections']=[]
  for m in listing:
   mid=m['market_id']
   if mid in seen_ids:continue
   seen_ids.add(mid)
   try:
    if m['chain_id']!=8453 or m['loan_token'].lower()!=USDC.lower() or market_id(m)!=mid:raise ValueError('domain/id mismatch')
    chosen.append(m)
   except Exception as e:s['identity_rejections'].append({'market_id':mid,'error':repr(e)})
  chosen.sort(key=lambda m:(not m.get('listed',False),-int(m.get('total_units',0))))
  s['omitted_ids']=[m['market_id'] for m in chosen[market_limit:]];chosen=chosen[:market_limit]
  books={};s['book_acquisition']=books
  for m in chosen:
   mid=m['market_id'];books[mid]={}
   for side in ('asks','bids'):books[mid][side]=c.get(f'/v0/midnight/books/{mid}/{side}/takeable-offers')
  for m in chosen:
   mid=m['market_id'];books[mid]['quote']=c.get(f'/v0/midnight/books/{mid}/asks/quote',units=1_000_000);books[mid]['quote_http_status']=c.last_http_status
  if int(c.value('eth_chainId',[]),16)!=8453:raise Stop('wrong chain')
  block=c.value('eth_getBlockByNumber',['latest',False]);B=block['number'];now=int(block['timestamp'],16)
  s['snapshot']={k:block.get(k) for k in ('number','hash','timestamp','baseFeePerGas')}
  code=c.value('eth_getCode',[CORE,B]);s['core_runtime_sha256']=hashlib.sha256(bhex(code)).hexdigest();runtime=None
  status_file=ROOT/'build/compile_status.json';status=json.loads(status_file.read_text()) if status_file.exists() else {}
  s['build_status']=status
  if status.get('compiled') and status.get('source_hash')==hashlib.sha256((ROOT/'CashProbe.sol').read_bytes()).hexdigest() and s['core_runtime_sha256']==EXPECTED_RUNTIME_SHA:
   candidate=(ROOT/'build/probe_runtime.hex').read_text().strip()
   if hashlib.sha256(bhex(candidate)).hexdigest()!=status['runtime_sha256']:raise Stop('probe hash mismatch')
   if c.value('eth_getCode',[PROBE,B])!='0x':raise Stop('probe address not empty')
   control=c.rpc('eth_call',[{'from':CALLER,'to':PROBE,'gas':hex(1_000_000),'data':selector('environment()')},B,{PROBE:{'code':candidate}}]);s['override_control']=control
   if isinstance(control,dict) and 'result' in control and decode_words(control['result'])==[8453,int(B,16),now,0]:runtime=candidate
  s['execution_enabled']=runtime is not None
  if not runtime:s['execution_blocker']='Compilation, core fingerprint, empty address, or code-override environment control unavailable.'
  if c.view(USDC,'decimals()',[],B)!=[6]:raise Stop('USDC decimals mismatch')
  custody=c.view(USDC,'balanceOf(address)',[CORE],B)[0];s['USDC_core_custody_raw']=str(custody)
  for m in chosen:
   mid=m['market_id'];rec={'market_id':mid,'definition':m};s['markets'].append(rec)
   try:
    stored=c.value('eth_getCode',['0x'+mid[-40:],B]);rec['stored_market_matches_abi']=bhex(stored)==word(32)+market_body(m)
    if not rec['stored_market_matches_abi']:rec['status']='STORED_MARKET_MISMATCH';continue
    state=c.view(CORE,'marketState(bytes32)',[mid],B)
    if len(state)!=13:raise ValueError('marketState schema')
    rec['market_state_words']=[str(x) for x in state];W=state[2];rec['withdrawable_raw']=str(W);rec['canonical_market_debt_raw']=str(state[0]-W)
    rec['fee_wad']=str(c.view(CORE,'settlementFee(bytes32,uint256)',[mid,max(0,m['maturity']-now)],B)[0])
    asks=None
    for side in ('asks','bids'):
     rec[side]=books[mid][side]
     try:
      rr=rows(rec[side]);rec[side+'_count']=len(rr)
      if side=='asks':asks=rr
     except ValueError as e:rec.setdefault('book_errors',{})[side]=str(e)
    quote=books[mid].get('quote')
    if isinstance(quote,dict) and isinstance(quote.get('data'),dict):
     qrows=quote['data'].get('takeable_offers')
     if isinstance(qrows,list) and qrows:
      seen_offer={hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest() for x in (asks or [])};asks=asks or []
      for x in qrows:
       h=hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
       if h not in seen_offer:asks.append(x);seen_offer.add(h)
    if asks is None:rec['withdrawal_route_status']='API_UNAVAILABLE_NOT_EMPTY'
    elif not asks:rec['withdrawal_route_status']='NO_API_ASK_AT_RESPONSE_TIME'
    elif W==0:rec['withdrawal_route_status']='NO_SAME_MARKET_WITHDRAWAL_CASH'
    elif not runtime:rec['withdrawal_route_status']='SIMULATION_ENVIRONMENT_UNAVAILABLE'
    else:
     rec['withdrawal_route_status']='ATTEMPTED_SUPPORTED_ASKS'
     used=0
     for raw in asks:
      if used>=6:break
      try:
       if not valid_offer(raw,m):continue
       cap=min(int(raw['units']),W,100_000*10**6,custody)
       if cap<=0:continue
       for q in sorted({cap//den for den in (1,4,16)}-{0},reverse=True):s['probes'].append(probe(c,runtime,run_take(raw['offer'],raw['ratifier_data'],q),B,{'route':'ask_to_withdraw','market_id':mid,'maker':raw['offer']['maker'],'units':str(q)}))
       used+=1
      except Stop:raise
      except Exception as e:rec.setdefault('offer_errors',[]).append(repr(e))
    if not any(cp['token'].lower()==USDC.lower() for cp in m['collaterals']):continue
    positions=[];cursor=None;seen_cursor=set()
    for page in range(3):
     params={'types':'borrow','limit':100,'sort_by':'debt','sort_direction':'desc'}
     if cursor:params['cursor']=cursor
     r=c.get(f'/v0/midnight/markets/{mid}/positions',**params);positions.extend(rows(r));cursor=r.get('cursor')
     if not cursor:break
     if cursor in seen_cursor:break
     seen_cursor.add(cursor)
    rec['borrower_discovery']=positions;rec['borrower_api_incomplete']=bool(cursor)
    positions=sorted(positions,key=lambda p:-int(p.get('debt',0)));rec['unread_borrowers']=max(0,len(positions)-position_limit);checks=[];rec['borrower_checks']=checks;prices={}
    for p in positions[:position_limit]:
     user=p.get('user_address')
     if not user:continue
     check={'borrower':user};checks.append(check)
     ps=c.view(CORE,'position(bytes32,address)',[mid,user],B)
     if len(ps)!=6:raise ValueError('position schema')
     D=ps[4];bitmap=ps[5];check['position_words']=[str(x) for x in ps];check['debt_raw']=str(D);check['activated_collateral_count']=bitmap.bit_count()
     if D==0:check['status']='NO_DEBT_AT_BLOCK';continue
     if not any(cp['token'].lower()==USDC.lower() and bitmap&(1<<i) for i,cp in enumerate(m['collaterals'])):check['status']='NO_ACTIVE_CASH_COLLATERAL';continue
     amounts={}
     for i,cp in enumerate(m['collaterals']):
      if not bitmap&(1<<i):continue
      amounts[i]=c.view(CORE,'collateral(bytes32,address,uint256)',[mid,user,i],B)[0]
      if i not in prices:prices[i]=c.view(cp['oracle'],'price()',[],B)[0]
     sizes,reason=legal_cash_sizes(m,D,amounts,prices,now)
     check.update(collateral_raw={str(k):str(v) for k,v in amounts.items()},status=reason,candidate_sizes=sizes,mixed_cash_and_other_collateral=len(amounts)>1)
     if runtime:
      for idx,post,q in sizes:s['probes'].append(probe(c,runtime,run_liquidation(m,idx,user,q,post),B,{'route':'USDC_collateral_liquidation','market_id':mid,'borrower':user,'repaid_units':str(q),'post_maturity':post}))
    rec['oracle_prices_raw']={str(i):str(v) for i,v in prices.items()};rec['sum_read_borrower_debt_raw']=str(sum(int(x.get('debt_raw',0)) for x in checks))
    rec['all_borrower_debt_reconciled']=not cursor and not rec['unread_borrowers'] and len(checks)==len(positions) and int(rec['sum_read_borrower_debt_raw'])==int(rec['canonical_market_debt_raw'])
   except Stop:raise
   except Exception as e:rec['error']=repr(e)
  s['status']='BOUNDED_RUN_COMPLETE_NOT_CAPTURE_VERIFIED'
 except Stop as e:s.update(status='STOPPED_PARTIAL',error=str(e))
 except Exception as e:s.update(status='UNAVAILABLE_OR_PARTIAL',error=repr(e))
 finally:
  s.update(completed_utc=utc(),http_requests=c.count,positive_simulations=sum(p.get('status')=='CASH_POSITIVE_SIMULATION_BEFORE_COSTS_AND_CAPTURE' for p in s['probes']))
  (out/'SUMMARY.json').write_text(json.dumps(s,indent=2));print(json.dumps({k:v for k,v in s.items() if k not in ('market_listing','book_acquisition','markets','probes')},indent=2));print('Evidence:',out)
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-public',action='store_true');p.add_argument('--max-requests',type=int,default=300);p.add_argument('--max-markets',type=int,default=12);p.add_argument('--max-positions',type=int,default=32);a=p.parse_args()
 if not a.run_public:print('OFFLINE: --run-public required')
 elif not (10<=a.max_requests<=500 and 1<=a.max_markets<=20 and 1<=a.max_positions<=64):p.error('outside fixed bounds')
 else:collect(a.max_requests,a.max_markets,a.max_positions)
