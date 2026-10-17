"""Read-only harvest service screen, not an investment or a trading executor."""
import collections,datetime as dt,hashlib,json,math,pathlib,time,urllib.request,urllib.error
API='https://api.beefy.finance';RPC='https://api.avax.network/ext/bc/C/rpc';OUT=pathlib.Path('evidence')
PATHS={'/vaults','/fees','/tvl','/apy/breakdown'};METHODS={'eth_chainId','eth_getBlockByNumber','eth_gasPrice','eth_call'}
SIG={'strategy':'a8c62e76','callReward':'97fd323d','native':'11b0b42d','lastHarvest':'f1a392da','paused':'5c975abb'}
WAVAX='0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7'
def save(n,o):
 p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2))
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def rate_budget(tvl,apr,call):
 if not all(finite(x) for x in (tvl,apr,call)) or min(tvl,apr,call)<0 or call>1:return None
 return tvl*apr*call  # static model only; no realised capture or recurrence inference
class Client:
 def __init__(self):self.n=0;self.start=time.monotonic();self.stop=False
 def req(self,path=None,method=None,params=None):
  if self.stop or self.n>=100 or time.monotonic()-self.start>480:raise RuntimeError('budget/access stop')
  if (path is not None and path not in PATHS) or (method is not None and method not in METHODS):raise ValueError('not allowlisted')
  self.n+=1;time.sleep(2);url=API+path if path else RPC;pl={'jsonrpc':'2.0','id':self.n,'method':method,'params':params} if method else None
  meta={'url':url,'payload':pl,'utc':dt.datetime.now(dt.timezone.utc).isoformat()};body=b''
  try:
   rq=urllib.request.Request(url,json.dumps(pl).encode() if pl else None,{'Content-Type':'application/json','Accept':'application/json','User-Agent':'QT-ReadOnly-Service-Screen/1'})
   with urllib.request.urlopen(rq,timeout=25) as res:body=res.read(20000001);meta['http']=res.status
   if len(body)>20000000:raise ValueError('response size cap')
   j=json.loads(body)
   if pl and 'error' in j:
    meta.update(status='RPC_ERROR',error=j['error'])
    if any(x in str(j['error']).lower() for x in ('rate limit','quota','api key','unauthorized','forbidden')):self.stop=True
    raise ValueError(str(j['error']))
   meta['status']='OK';return j['result'] if pl else j
  except urllib.error.HTTPError as e:
   body=e.read(100000);meta.update(status='HTTP_ERROR',http=e.code,error=str(e));self.stop=e.code in (401,403,429);raise
  except Exception as e:meta.setdefault('status','UNAVAILABLE');meta.setdefault('error',repr(e));raise
  finally:
   meta['sha256']=hashlib.sha256(body).hexdigest();save(f'raw/{self.n:03d}.json',meta);(OUT/'raw'/f'{self.n:03d}.body').write_bytes(body)
 def view(self,to,field,block):
  x=self.req(method='eth_call',params=[{'to':to,'data':'0x'+SIG[field]},block])
  if not isinstance(x,str) or len(x)!=66:raise ValueError('unexpected getter ABI')
  return int(x,16)
def run():
 OUT.mkdir(exist_ok=True);c=Client();s={'scope':'Metadata capacity across active Beefy vaults; actual Avalanche getter sample','signed_or_sent':0,'real_profit_verified':False,'limitations':['TVL and APR are API estimates, not measured harvest distributions.','APR-times-TVL-times-caller-fee is a static scenario, not a forecast or realised revenue.','Current metadata requests are not one atomic snapshot.','Actual harvest cash and gas have not been simulated.','callReward can be an approximation; returned units require underlying strategy verification.','No deposits or harvesting, only read calls.']}
 save('PLAN.json',{'api_paths':sorted(PATHS),'chain':43114,'max_vault_getter_sample':10,'selection':'largest reported static caller-fee budgets among active Avalanche vaults; before pending-reward reads','actual_profit_test':False,'cap':100,'seconds_cap':480,'no_reserved_historical_dates':True})
 try:
  vaults=c.req(path='/vaults');fees=c.req(path='/fees');tvls=c.req(path='/tvl');apy=c.req(path='/apy/breakdown')
  if not isinstance(vaults,list):raise ValueError('unexpected vault schema')
  ids={v['id'] for v in vaults};flat={}
  def flatten(x):
   if isinstance(x,dict):
    for k,v in x.items():
     if k in ids and finite(v):flat[k]=v
     elif isinstance(v,dict):flatten(v)
  flatten(tvls);rows=[]
  for v in vaults:
   if v.get('status')!='active':continue
   i=v['id'];a=apy.get(i,{}) if isinstance(apy,dict) else {};f=fees.get(i,{}) if isinstance(fees,dict) else {};fee=f.get('performance',{}).get('call');apr=a.get('vaultApr');tvl=flat.get(i)
   rows.append({'id':i,'chain':v.get('chain',v.get('network')),'vault':v.get('earnContractAddress'),'api_strategy':v.get('strategy'),'api_last_harvest':v.get('lastHarvest'),'reported_tvl_usd':tvl,'reported_reward_apr':apr,'reported_caller_fee_fraction':fee,'static_annual_caller_budget_usd':rate_budget(tvl,apr,fee)})
  save('vault_screen.json',rows);valid=[x for x in rows if x['static_annual_caller_budget_usd'] is not None];by=collections.Counter()
  for x in valid:by[x['chain']]+=x['static_annual_caller_budget_usd']
  picked=sorted([x for x in valid if x['chain'] in ('avax','avalanche') and isinstance(x['vault'],str)],key=lambda x:(-x['static_annual_caller_budget_usd'],x['id']))[:10];save('SELECTION_BEFORE_CHAIN_READS.json',picked)
  s.update(active_rows=len(rows),valid_static_rows=len(valid),missing_static_rows=len(rows)-len(valid),static_annual_by_chain=dict(by),static_annual_all=sum(by.values()),sample_count=len(picked));save('SUMMARY.json',s)
  if c.req(method='eth_chainId',params=[])!='0xa86a':raise ValueError('wrong chain')
  h=c.req(method='eth_getBlockByNumber',params=['latest',False]);block=h['number'];save('HEADER.json',h);gas=int(c.req(method='eth_gasPrice',params=[]),16);s['gas_price_wei']=gas;s['block']=block;obs=[]
  for v in picked:
   x=dict(v)
   try:
    st=c.view(v['vault'],'strategy',block)
    if st>=2**160:raise ValueError('strategy address overflow')
    st='0x'+f'{st:040x}';x['actual_strategy']=st
    for field in ('callReward','native','lastHarvest','paused'):
     try:x[field]=c.view(st,field,block)
     except Exception as e:
      x[field+'_unavailable']=repr(e)
      if c.stop:raise
    if 'native' in x and x['native']<2**160:x['native_address']='0x'+f"{x['native']:040x}"
    if 'callReward' in x and x.get('native_address')==WAVAX:
     x['reward_avax_estimate']=x['callReward']/1e18;x['illustrative_600k_gas_cost_avax']=600000*gas/1e18;x['illustrative_1_5m_gas_cost_avax']=1500000*gas/1e18
   except Exception as e:
    x['unavailable']=repr(e)
    if c.stop:raise
   obs.append(x);save('chain_views.json',obs)
  s['observations']=obs
 except Exception as e:s['exception']=repr(e)
 s.update(requests=c.n,provider_stopped=c.stop);save('SUMMARY.json',s);print(json.dumps(s,indent=2))
if __name__=='__main__':run()
