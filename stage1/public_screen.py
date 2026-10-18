"""Public market-data screening only. No trades, signatures, state overrides or executor code.
Quote outputs are not cash executions. Provider refusals stop that provider.
"""
import json,time,hashlib,datetime,pathlib,urllib.request,urllib.error,urllib.parse,traceback
from decimal import Decimal as D
OUT=pathlib.Path('stage1_evidence');OUT.mkdir(exist_ok=True)
RPC='https://rpc-eth.blockmachine.io';GAMMA='https://gamma-api.polymarket.com';CLOB='https://clob.polymarket.com'
DAI='0x6B175474E89094C44Da98b954EedeAC495271d0F';USDS='0xdC035D45d973E3EC169d2276DDab16f1e407384F'
WETH='0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2';WST='0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0'
ST='0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84';CURVE='0xDC24316b9AE028F1497c275EB9192a3Ea0f67022'
CONVERTER='0x3225737a9Bbb6473CB4a45b7244ACa2BeFdB276A';FACTORY='0x1F98431c8aD98523631AE4a59f267346ea31F984'
QUOTER='0x61fFE014bA17989E743c5F6cB21bF9697530B21e'
DATES=['2026-09-10T12:00:00+00:00','2026-09-20T12:00:00+00:00','2026-09-30T12:00:00+00:00']
def save(n,x):(OUT/n).write_text(json.dumps(x,indent=2,default=str))
def allowed(url,payload):
 if url==RPC:return isinstance(payload,dict) and payload.get('method') in {'eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call'}
 p=urllib.parse.urlparse(url)
 return p.scheme=='https' and ((p.netloc=='gamma-api.polymarket.com' and p.path=='/markets' and payload is None) or(p.netloc=='clob.polymarket.com' and p.path=='/books' and isinstance(payload,list)))
class Client:
 def __init__(self):self.n=0;self.last=0.;self.start=time.monotonic();self.blocked=set();self.records=[]
 def request(self,name,url,payload=None):
  assert allowed(url,payload),'Request not allowlisted'
  host=urllib.parse.urlparse(url).netloc
  if host in self.blocked:raise RuntimeError('Provider previously refused; stopped')
  if self.n>=360 or time.monotonic()-self.start>1250:raise RuntimeError('Research budget reached')
  time.sleep(max(0,2-(time.monotonic()-self.last)));self.n+=1;body=b''
  meta={'name':name,'url':url,'payload':payload,'requested_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'UNAVAILABLE'}
  try:
   req=urllib.request.Request(url,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'QT-Public-Research/1'})
   with urllib.request.urlopen(req,timeout=45) as r:meta['http_status']=r.status;body=r.read(8000001)
   if len(body)>8000000:raise ValueError('Body limit')
   data=json.loads(body);meta['status']='OK'
   if isinstance(payload,dict) and 'error' in data:
    meta['status']='RPC_ERROR';meta['error']=data['error']
    if any(s in json.dumps(data['error']).lower() for s in ['rate limit','too many requests','forbidden','unauthorized','access denied','client adjustable limit']):self.blocked.add(host)
   return data
  except urllib.error.HTTPError as e:
   meta.update(http_status=e.code,error=str(e),status='HTTP_ERROR');body=e.read(20000)
   if e.code in (401,403,429):self.blocked.add(host)
   return None
  except Exception as e:meta['error']=repr(e);return None
  finally:
   self.last=time.monotonic();meta.update(received_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),body_sha256=hashlib.sha256(body).hexdigest(),response_bytes=len(body))
   p=OUT/'raw'/f'{self.n:04d}';p.parent.mkdir(exist_ok=True);p.with_suffix('.body').write_bytes(body);p.with_suffix('.json').write_text(json.dumps(meta,indent=2));self.records.append(meta)
 def rpc(self,name,method,params):
  x=self.request(name,RPC,{'jsonrpc':'2.0','id':self.n+1,'method':method,'params':params})
  if not isinstance(x,dict) or 'error' in x:raise RuntimeError('RPC unavailable: '+name)
  return x['result']
def depth(levels,q,buy):
 left=D(q);out=D(0)
 for p,s in sorted([(D(x['price']),D(x['size'])) for x in levels if D(x['size'])>0],reverse=not buy):
  if not D(0)<=p<=D(1):raise ValueError('Invalid price')
  amount=min(left,s);out+=amount*p;left-=amount
  if left==0:return out
 return None
def pair(a,b):
 if a['market']!=b['market'] or a.get('neg_risk') is not False or b.get('neg_risk') is not False:raise ValueError('Wrong condition or market type')
 out=[]
 for q in (5,25,100):
  if D(q)<max(D(a['min_order_size']),D(b['min_order_size'])):continue
  asks=[depth(x['asks'],q,True) for x in (a,b)];bids=[depth(x['bids'],q,False) for x in (a,b)]
  out.append({'quantity':q,'buy_both_gross':str(D(q)-sum(asks)) if None not in asks else None,'split_sell_gross':str(sum(bids)-D(q)) if None not in bids else None,'cash_execution':False,'fees_excluded':True})
 return out
def prediction(c):
 report={'scope':'Gross complete-set upper bounds, not executed trades or fee-adjusted profit','selection':[],'observations':[]}
 save('PREDICTION.json',report)
 data=c.request('prediction_discovery',GAMMA+'/markets?active=true&closed=false&limit=100&order=liquidityNum&ascending=false')
 if not isinstance(data,list):report['error']='discovery unavailable';save('PREDICTION.json',report);return
 for m in data:
  try:ts=json.loads(m['clobTokenIds']) if isinstance(m['clobTokenIds'],str) else m['clobTokenIds']
  except Exception:continue
  if m.get('negRisk') is not False or len(ts)!=2 or m.get('closed') or m.get('enableOrderBook') is False:continue
  report['selection'].append({'id':m['id'],'question':m.get('question'),'condition':m.get('conditionId'),'tokens':ts,'feesEnabled':m.get('feesEnabled')})
  if len(report['selection'])==30:break
 save('PREDICTION.json',report)
 req=[{'token_id':t} for m in report['selection'] for t in m['tokens']]
 for round_ in (0,1):
  if not req:break
  if round_:time.sleep(20)
  books=c.request('books_'+str(round_),CLOB+'/books',req)
  if not isinstance(books,list):report['error']='books unavailable';break
  byid={b.get('asset_id'):b for b in books}
  for m in report['selection']:
   row={'id':m['id'],'round':round_}
   try:
    a,b=[byid[t] for t in m['tokens']]
    if a['market']!=m['condition']:raise ValueError('Condition mismatch')
    row.update(rows=pair(a,b),timestamps=[a.get('timestamp'),b.get('timestamp')],hashes=[a.get('hash'),b.get('hash')])
   except Exception as e:row['error']=repr(e)
   report['observations'].append(row)
  save('PREDICTION.json',report)
 save('PREDICTION.json',report)
def native_parity(c):
 from eth_abi import encode,decode
 from Crypto.Hash import keccak
 def data(sig,types,args):return '0x'+(keccak.new(digest_bits=256,data=sig.encode()).digest()[:4]+encode(types,args)).hex()
 report={'scope':'Deployed public getter and QuoterV2 outputs; not complete financing/settlement executions','rows':[],'pools':[],'warnings':['Quotes are not cash profits.','DAI or WETH unit balances are not assumed fiat USD.','No personal trading eligibility or inclusion probability established.']};save('PARITY.json',report)
 assert c.rpc('chain','eth_chainId',[])=='0x1'
 top=c.rpc('latest','eth_getBlockByNumber',['latest',False]);hi=int(top['number'],16);heads={hi:top}
 def header(n):
  if n not in heads:heads[n]=c.rpc('header','eth_getBlockByNumber',[hex(n),False])
  return heads[n]
 def boundary(ts):
  lo=max(0,hi-600000);up=hi
  if int(header(lo)['timestamp'],16)>ts:lo=0
  while lo<up:
   mid=(lo+up)//2
   if int(header(mid)['timestamp'],16)<ts:lo=mid+1
   else:up=mid
  assert int(header(lo-1)['timestamp'],16)<ts<=int(header(lo)['timestamp'],16)
  return header(lo)
 def view(name,to,sig,types,args,h):
  return c.rpc(name,'eth_call',[{'to':to,'data':data(sig,types,args),'gas':hex(1500000),'gasPrice':h['baseFeePerGas']},h['number']])
 def num(name,to,sig,types,args,h):return int(view(name,to,sig,types,args,h),16)
 def quote(a,b,fee,n,h):
  res=view('uniswap_quote',QUOTER,'quoteExactInputSingle((address,address,uint256,uint24,uint160))',['(address,address,uint256,uint24,uint160)'],[(a,b,n,fee,0)],h)
  return decode(['uint256','uint160','uint32','uint256'],bytes.fromhex(res[2:]))[0]
 for when in DATES:
  h=boundary(int(datetime.datetime.fromisoformat(when).timestamp()));save('HEADERS.json',list(heads.values()))
  # Confirm token units and native wrapper/converter identity at this exact block.
  for token in (DAI,USDS,WETH,WST,ST):assert num('decimals',token,'decimals()',[],[],h)==18
  assert view('converter_dai',CONVERTER,'dai()',[],[],h)[-40:].lower()==DAI[2:].lower()
  assert view('converter_usds',CONVERTER,'usds()',[],[],h)[-40:].lower()==USDS[2:].lower()
  assert view('wrapper_identity',WST,'stETH()',[],[],h)[-40:].lower()==ST[2:].lower()
  assert view('curve_coin',CURVE,'coins(uint256)',['uint256'],[1],h)[-40:].lower()==ST[2:].lower()
  for family,a,b,amounts in [('DAI_USDS',DAI,USDS,[100*10**18,1000*10**18,10000*10**18]),('LIDO_WRAP',WETH,WST,[10**17,10**18,10**19])]:
   for fee in (100,500):
    addr='0x'+view('pool',FACTORY,'getPool(address,address,uint24)',['address','address','uint24'],[a,b,fee],h)[-40:]
    report['pools'].append({'family':family,'fee':fee,'date':when,'address':addr})
    if int(addr,16)==0:continue
    for direction in (0,1):
     for n in amounts:
      row={'family':family,'date':when,'block':int(h['number'],16),'hash':h['hash'],'fee':fee,'direction':direction,'input_raw':str(n),'status':'UNAVAILABLE'}
      try:
       if family=='DAI_USDS':q=quote(USDS,DAI,fee,n,h) if direction==0 else quote(DAI,USDS,fee,n,h)
       elif direction==0:
        w=quote(WETH,WST,fee,n,h);s=num('unwrap_quote',WST,'getStETHByWstETH(uint256)',['uint256'],[w],h);q=num('curve_exit',CURVE,'get_dy(int128,int128,uint256)',['int128','int128','uint256'],[1,0,s],h)
       else:
        s=num('curve_entry',CURVE,'get_dy(int128,int128,uint256)',['int128','int128','uint256'],[0,1,n],h);w=num('wrap_quote',WST,'getWstETHByStETH(uint256)',['uint256'],[s],h);q=quote(WST,WETH,fee,w,h)
       row.update(status='QUOTE_ONLY',output_raw=str(q),gross_margin_raw=str(q-n),cash_execution=False)
      except Exception as e:row['error']=repr(e)
      report['rows'].append(row);save('PARITY.json',report)
      if c.blocked:raise RuntimeError('Provider refusal; stopped')
  save('PARITY.json',report)
 save('HEADERS.json',list(heads.values()))
def main():
 c=Client();summary={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'methods':'Read-only public APIs and contract quotation only','errors':[],'cash_simulation_upload_blocked':True,'no_new_cash_execution_claim':True}
 for fn in (prediction,native_parity):
  try:fn(c)
  except Exception as e:summary['errors'].append({'scope':fn.__name__,'error':repr(e),'traceback':traceback.format_exc()})
  save('SUMMARY.json',summary)
 summary.update(requests=c.n,blocked_hosts=sorted(c.blocked),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),http_status_counts={k:sum(x['status']==k for x in c.records) for k in ['OK','RPC_ERROR','HTTP_ERROR','UNAVAILABLE']})
 save('SUMMARY.json',summary);print(json.dumps(summary,indent=2))
 for name in ('PARITY.json','PREDICTION.json'):
  if (OUT/name).exists():
   x=json.loads((OUT/name).read_text());print(name,json.dumps({'rows':len(x.get('rows',[])),'markets':len(x.get('selection',[])),'observations':len(x.get('observations',[])),'error':x.get('error')}))
 if summary['errors']:raise SystemExit('Incomplete public data scope; evidence preserved')
if __name__=='__main__':main()
