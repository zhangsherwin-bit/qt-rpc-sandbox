"""Read-only Phase 2. Explicit --run-public required. No keys/signing/funding.
Adapted from the previously prepared Phase2 harness, with deployment-time provenance,
canonical health cross-checks and independent negative-control EVM calls.
"""
import argparse,json,pathlib,time,urllib.request,urllib.parse,urllib.error,hashlib,datetime
from midnight_codec import *
ROOT=pathlib.Path(__file__).resolve().parent
API='https://api.morpho.org';RPC='https://mainnet.base.org'
EXPECTED_RUNTIME_SHA='7884845d7adfa271bc0715c0f6205a006f053921128680defea915fa8a8a831d'
WAD=10**18;O=10**36

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class Stop(Exception):pass
class Client:
 def __init__(self,root,limit):
  self.root=root;root.mkdir(parents=True,exist_ok=True);self.count=0;self.limit=limit;self.last=0;self.records=[]
 def request(self,url,payload=None):
  if self.count>=self.limit:raise Stop('request budget reached')
  parsed=urllib.parse.urlsplit(url)
  if parsed.scheme!='https' or parsed.hostname not in {'api.morpho.org','mainnet.base.org'}:raise ValueError('Unapproved public host')
  if parsed.hostname=='api.morpho.org' and not parsed.path.startswith('/v0/midnight/'):raise ValueError('Unapproved API path')
  if payload is not None and payload.get('method') not in {'eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call'}:raise ValueError('RPC method not allowlisted')
  time.sleep(max(0,1.8-(time.monotonic()-self.last)));self.count+=1
  rec={'url':url,'payload':payload,'started_utc':utc()};body=b'';stop=False;ret=None
  try:
   req=urllib.request.Request(url,data=None if payload is None else json.dumps(payload).encode(),headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'QT-read-only-research/2.1'})
   with urllib.request.urlopen(req,timeout=18) as r:
    body=r.read(2_000_001);rec['http_status']=r.status
    if len(body)>2_000_000:raise ValueError('response byte budget exceeded')
   ret=json.loads(body)
  except urllib.error.HTTPError as e:
   rec['http_status']=e.code;body=e.read(200000);rec['error']=str(e);stop=e.code in (401,403,429)
  except Exception as e:rec['error']=repr(e)
  rec.update(completed_utc=utc(),body_sha256=hashlib.sha256(body).hexdigest())
  if isinstance(ret,dict) and 'error' in ret:rec['provider_error']=ret['error']
  name=self.root/f'{self.count:04d}';name.with_suffix('.json').write_text(json.dumps(rec,indent=2));name.with_suffix('.body').write_bytes(body)
  self.records.append(rec);self.last=time.monotonic();self.last_http_status=rec.get('http_status')
  if stop:raise Stop('access/rate boundary; stopped without bypass')
  return ret
 def get(self,path,**params):return self.request(API+path+('?' +urllib.parse.urlencode(params) if params else ''))
 def rpc(self,method,params):return self.request(RPC,{'jsonrpc':'2.0','id':self.count+1,'method':method,'params':params})
 def value(self,method,params):
  r=self.rpc(method,params)
  if not isinstance(r,dict) or 'error' in r or 'result' not in r:raise ValueError('RPC unavailable: '+str(r)[:300])
  return r['result']
 def view(self,to,signature,args,block):return decode_words(self.value('eth_call',[{'to':to,'data':view_data(signature,*args)},block]))

def rows(r):
 if not isinstance(r,dict) or not isinstance(r.get('data'),list):raise ValueError('missing list response')
 return r['data']
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
    maxrepay=ceildiv((debt-maximum_debt)*WAD*WAD,WAD*WAD-lif*int(cp['lltv']))
    if max(0,cap-maxrepay)>=int(m['rcf_threshold']):limit=min(limit,maxrepay)
   for denom in (1,2,4):
    q=limit//denom
    if q>0 and (i,post,q) not in candidates:candidates.append((i,post,q))
 return candidates,'candidate_sizes' if candidates else 'no_current_supported_cash_liquidation'

def probe(c,runtime,data,block,context):
 response=c.rpc('eth_call',[{'from':CALLER,'to':PROBE,'gas':hex(12_000_000),'data':data},block,{PROBE:{'code':runtime}}])
 r={'context':context,'rpc_response':response,'block':block,'only_code_overridden':True,'observed_utc':utc()}
 if not isinstance(response,dict) or 'result' not in response:r['status']='UNAVAILABLE_OR_REVERTED_NOT_GLOBAL_REJECTION';return r
 try:
  w=decode_words(response['result'])
  if len(w)!=2 or w[0]<=0:raise ValueError('invalid positive cash result')
  r.update(status='CASH_POSITIVE_SIMULATION_BEFORE_COSTS_AND_CAPTURE',cash_raw=str(w[0]),internal_gas=w[1])
 except Exception as e:r.update(status='UNRECOGNIZED_RETURN',error=repr(e))
 return r

def collect(limit=300,market_limit=12,position_limit=32):
 out=ROOT/('public_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(exist_ok=True)
 c=Client(out/'raw',limit);s={'started_utc':utc(),'markets':[],'probes':[],'controls':[],'transactions_sent':0,'trade_profit_claimed':False,'scope':'Fresh listed Base USDC cohort; no retrospective outcome selection','warnings':['REST discovery is not atomic with RPC state.','Reset-state simulations cannot be summed.','Internal gas excludes complete fees, bids and failed attempts.','No historical final evaluation sample used.']}
 try:
  listing=[];cursor=None;seen=set()
  for page in range(3):
   params={'chain_ids':8453,'loan_assets':USDC,'listed':'true','limit':100}
   if cursor:params['cursor']=cursor
   r=c.get('/v0/midnight/markets',**params);listing.extend(rows(r));cursor=r.get('cursor')
   if not cursor:break
   if cursor in seen:raise Stop('repeated listing cursor')
   seen.add(cursor)
  s['listing_complete']=not bool(cursor);s['market_listing']=listing
  comparable=[];ids=set()
  for m in listing:
   if m['market_id'] in ids:continue
   ids.add(m['market_id'])
   if m['chain_id']==8453 and m['loan_token'].lower()==USDC.lower() and market_id(m)==m['market_id']:comparable.append(m)
   else:s.setdefault('rejected_definition_ids',[]).append(m['market_id'])
  comparable.sort(key=lambda m:(not m['listed'],-int(m['total_units'])))
  chosen=comparable[:market_limit];s['omitted_ids']=[m['market_id'] for m in comparable[market_limit:]]
  books={};s['book_acquisition']=books
  for m in chosen:
   mid=m['market_id'];books[mid]={}
   for side in ('asks','bids'):books[mid][side]=c.get(f'/v0/midnight/books/{mid}/{side}/takeable-offers')
  for m in chosen:
   mid=m['market_id'];books[mid]['quote']=c.get(f'/v0/midnight/books/{mid}/asks/quote',units=1_000_000)
   books[mid]['quote_http_status']=getattr(c,'last_http_status',None)
  if int(c.value('eth_chainId',[]),16)!=8453:raise Stop('wrong chain')
  block=c.value('eth_getBlockByNumber',['latest',False]);B=block['number'];now=int(block['timestamp'],16)
  s['snapshot']={k:block.get(k) for k in ('number','hash','timestamp','baseFeePerGas')}
  code=c.value('eth_getCode',[CORE,B]);sha=hashlib.sha256(bhex(code)).hexdigest();s['core_runtime_sha256']=sha
  runtime=None;status={}
  if (ROOT/'build/compile_status.json').exists():status=json.loads((ROOT/'build/compile_status.json').read_text())
  s['compile_status']=status
  if status.get('compiled') and status.get('source_hash')==hashlib.sha256((ROOT/'CashProbe.sol').read_bytes()).hexdigest() and sha==EXPECTED_RUNTIME_SHA:
   candidate=(ROOT/'build/probe_runtime.hex').read_text().strip()
   if hashlib.sha256(bhex(candidate)).hexdigest()!=status['runtime_sha256']:raise Stop('probe hash mismatch')
   if c.value('eth_getCode',[PROBE,B])!='0x':raise Stop('probe address occupied')
   r=c.rpc('eth_call',[{'from':CALLER,'to':PROBE,'gas':hex(1_000_000),'data':selector('environment()')},B,{PROBE:{'code':candidate}}]);s['override_control']=r
   if isinstance(r,dict) and 'result' in r and decode_words(r['result'])==[8453,int(B,16),now,0]:runtime=candidate
  s['execution_enabled']=runtime is not None
  if runtime is None:s['execution_blocker']='Compiler, pinned core hash or code-only override control did not pass.'
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
    rec['fee_wad']=str(c.view(CORE,'settlementFee(bytes32,uint256)',[mid,max(0,int(m['maturity'])-now)],B)[0])
    asks=None
    for side in ('asks','bids'):
     try:
      items=rows(books[mid][side]);rec[side+'_count']=len(items)
      if side=='asks':asks=items
     except Exception as e:rec.setdefault('book_errors',{})[side]=repr(e)
    quoted=books[mid].get('quote')
    qrows=quoted.get('data',{}).get('takeable_offers') if isinstance(quoted,dict) else None
    if isinstance(qrows,list) and qrows:
     if asks==[]:rec['book_quote_disagreement']=True
     asks=(asks or [])+qrows
    if asks is None:rec['conversion_status']='ASKS_UNAVAILABLE'
    elif not asks:rec['conversion_status']='NO_API_ASK_AT_RESPONSE_TIME'
    elif W==0:rec['conversion_status']='NO_WITHDRAWAL_CASH'
    elif runtime:
     used=set()
     for raw in asks:
      if len(used)>=6:break
      try:
       o=raw['offer'];om=o['market'];key=hashlib.sha256(json.dumps(o,sort_keys=True).encode()).hexdigest()
       if key in used or o['buy'] or int(raw['units'])<=0 or market_id(om)!=mid or raw['market_id']!=mid:continue
       if om.get('midnight','').lower()!=CORE.lower():continue
       cap=min(int(raw['units']),W,100_000*10**6,custody)
       used.add(key)
       for q in sorted({cap//d for d in (1,4,16)},reverse=True):
        if q>0:s['probes'].append(probe(c,runtime,run_take(o,raw['ratifier_data'],q),B,{'route':'ask_withdraw','market_id':mid,'maker':o['maker'],'units':str(q)}))
      except Stop:raise
      except Exception as e:rec.setdefault('offer_errors',[]).append(repr(e))
    else:rec['conversion_status']='INPUTS_AVAILABLE_EXECUTION_DISABLED'
    if not any(cp['token'].lower()==USDC.lower() for cp in m['collaterals']):continue
    positions=[];cur=None;seen_cur=set()
    for page in range(3):
     params={'types':'borrow','limit':100,'sort_by':'debt','sort_direction':'desc'}
     if cur:params['cursor']=cur
     p=c.get(f'/v0/midnight/markets/{mid}/positions',**params);positions.extend(rows(p));cur=p.get('cursor')
     if not cur:break
     if cur in seen_cur:break
     seen_cur.add(cur)
    # Deduplicate discovery identities, retaining a coverage warning.
    unique={p['user_address'].lower():p for p in positions if p.get('user_address')}
    rec['duplicate_or_invalid_discovery_rows']=len(positions)-len(unique)
    positions=sorted(unique.values(),key=lambda p:-int(p.get('debt',0)))
    rec['borrower_discovery']=positions;rec['borrower_api_incomplete']=bool(cur)
    rec['unread_borrower_count']=max(0,len(positions)-position_limit);rec['borrower_checks']=[];prices={};control_done=False
    for p in positions[:position_limit]:
     user=p['user_address'];check={'borrower':user};rec['borrower_checks'].append(check)
     ps=c.view(CORE,'position(bytes32,address)',[mid,user],B)
     if len(ps)!=6:raise ValueError('position schema')
     D=ps[4];bitmap=ps[5];check.update(position_words=[str(x) for x in ps],debt_raw=str(D))
     if D==0:check['status']='NO_DEBT_AT_BLOCK';continue
     cash_indexes=[i for i,cp in enumerate(m['collaterals']) if cp['token'].lower()==USDC.lower() and bitmap&(1<<i)]
     if not cash_indexes:check['status']='NO_ACTIVE_CASH_COLLATERAL';continue
     amounts={}
     for i,cp in enumerate(m['collaterals']):
      if not bitmap&(1<<i):continue
      amounts[i]=c.view(CORE,'collateral(bytes32,address,uint256)',[mid,user,i],B)[0]
      if i not in prices:prices[i]=c.view(cp['oracle'],'price()',[],B)[0]
     sizes,reason=legal_cash_sizes(m,D,amounts,prices,now)
     maxdebt=sum((amounts.get(i,0)*prices.get(i,0)//O)*int(cp['lltv'])//WAD for i,cp in enumerate(m['collaterals']))
     check.update(collateral_raw={str(k):str(v) for k,v in amounts.items()},max_debt_raw=str(maxdebt),status=reason,candidate_sizes=sizes,mixed_collateral=len(amounts)>1)
     if runtime:
      for idx,post,q in sizes:s['probes'].append(probe(c,runtime,run_liquidation(m,idx,user,0,q,post),B,{'route':'USDC_liquidation','market_id':mid,'borrower':user,'repaid_units':str(q),'post_maturity':post}))
      if not sizes and not control_done:
       s['controls'].append(probe(c,runtime,run_liquidation(m,cash_indexes[0],user,0,1,False),B,{'route':'negative_control_known_no_eligible_size','market_id':mid,'borrower':user}));control_done=True
    rec['oracle_prices_raw']={str(k):str(v) for k,v in prices.items()}
    read=sum(int(x.get('debt_raw',0)) for x in rec['borrower_checks']);rec['sum_read_borrower_debt_raw']=str(read)
    rec['all_borrower_debt_reconciled']=not cur and rec['unread_borrower_count']==0 and len(rec['borrower_checks'])==len(positions) and read==state[0]-W
   except Stop:raise
   except Exception as e:rec['error']=repr(e)
  # Confirm canonical block hash after the serial snapshot reads.
  final=c.value('eth_getBlockByNumber',[B,False]);s['snapshot_hash_unchanged']=final.get('hash')==block['hash']
  s['status']='BOUNDED_RUN_COMPLETE_NOT_CAPTURE_VERIFIED'
 except Stop as e:s.update(status='STOPPED_PARTIAL',error=str(e))
 except Exception as e:s.update(status='UNAVAILABLE_OR_PARTIAL',error=repr(e))
 finally:
  s.update(completed_utc=utc(),http_requests=c.count,positive_simulations=sum(p.get('status')=='CASH_POSITIVE_SIMULATION_BEFORE_COSTS_AND_CAPTURE' for p in s['probes']))
  (out/'SUMMARY.json').write_text(json.dumps(s,indent=2))
  print(json.dumps({k:v for k,v in s.items() if k not in ('markets','market_listing','book_acquisition','probes','controls')},indent=2))
  print('MARKET_SUMMARY',json.dumps([{k:v for k,v in m.items() if k in ('market_id','asks_count','bids_count','withdrawable_raw','all_borrower_debt_reconciled','conversion_status','error')} for m in s['markets']]))
  print('Evidence:',out)
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run-public',action='store_true');p.add_argument('--max-requests',type=int,default=300);p.add_argument('--max-markets',type=int,default=12);p.add_argument('--max-positions',type=int,default=32);a=p.parse_args()
 if not a.run_public:print('OFFLINE. Explicit --run-public required.')
 elif not(10<=a.max_requests<=500 and 1<=a.max_markets<=20 and 1<=a.max_positions<=64):p.error('outside budget')
 else:collect(a.max_requests,a.max_markets,a.max_positions)
