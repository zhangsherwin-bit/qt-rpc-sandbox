"""Public getter-only research. No state overrides, transaction execution,
wallets, private keys, deployment, signing, or broadcasting.
"""
import datetime as dt,hashlib,json,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from Crypto.Hash import keccak
from eth_abi import encode,decode
CORE='0xadedd8ab6de832766fedf0fac4992e5c4d3ea18a'
BLUE='0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb'
HELPER='0xb03015b3aa6f5eda3ad03c8b3e5553b2665174a2'
ORDINARY='0x00000000000000000000000000000000dead7716'
USDC='0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
WETH='0x4200000000000000000000000000000000000006'
VAULTS={'WETH_USDC':'0xe690a58ef52854513462745237f6a213a0d54df1','cbBTC_USDC':'0xf6a70085b7f79fa76b04ebf7a2d7d87c3c5c04bc','cbETH_WETH':'0xfa750dd0099eadb72d401244de73ce7b89edf90f'}
API='https://api.morpho.org';RPC='https://mainnet.base.org'
MULTI='0xca11bde05977b3631167028862be2a173976ca11'
MT='(uint256,address,address,(address,uint256,uint256,address)[],uint256,uint256,address,address)'
GETTERS={'asset()','decimals()','totalAssets()','totalSupply()','liquidityAdapter()','liquidityData()','receiveSharesGate()','sendSharesGate()','receiveAssetsGate()','sendAssetsGate()','adaptersLength()','balanceOf(address)','MORPHO_MIDNIGHT()','canReceiveShares(address)','canSendShares(address)','canReceiveAssets(address)','owner()','market(bytes32)','position(bytes32,address)','collateral(bytes32,address,uint256)','toMarket(bytes32)','marketState(bytes32)','price()','previewRedeem(uint256)'}
OUT=Path('evidence');OUT.mkdir(exist_ok=True)
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def h(b):return keccak.new(digest_bits=256,data=b).digest()
def clean(x):
 if isinstance(x,bytes):return '0x'+x.hex()
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 return x
def save(path,x):(OUT/path).write_text(json.dumps(clean(x),indent=2))
def calldata(sig,types=(),args=()):
 if sig not in GETTERS:raise ValueError('Getter not permitted')
 return h(sig.encode())[:4]+encode(list(types),list(args))
class Client:
 def __init__(self):self.n=0;self.stop=False;self.records=[];(OUT/'raw').mkdir(exist_ok=True)
 def request(self,name,url,payload=None):
  p=urllib.parse.urlsplit(url)
  if p.scheme!='https' or p.username or p.password or p.hostname not in {'api.morpho.org','mainnet.base.org'}:raise ValueError('Unapproved host')
  if payload is not None and (url!=RPC or payload.get('method') not in {'eth_chainId','eth_getCode','eth_getBlockByNumber','eth_call'}):raise ValueError('Unapproved method')
  if payload is None and (p.hostname!='api.morpho.org' or not p.path.startswith('/v0/midnight/markets')):raise ValueError('Unapproved API path')
  if self.stop or self.n>=180:raise RuntimeError('Request budget/access stop')
  self.n+=1;time.sleep(.85);body=b'';r={'name':name,'url':url,'payload':payload,'started_utc':utc()};j=None
  try:
   req=urllib.request.Request(url,json.dumps(payload).encode() if payload is not None else None,{'Content-Type':'application/json','User-Agent':'QT-Getter-Research/20261016'})
   with urllib.request.urlopen(req,timeout=25) as resp:r['http_status']=resp.status;body=resp.read(2_000_001)
   if len(body)>2_000_000:raise ValueError('Body limit')
   j=json.loads(body);r['status']='RPC_ERROR' if isinstance(j,dict) and 'error' in j else 'OK'
  except urllib.error.HTTPError as e:
   body=e.read(50000);r.update(status='HTTP_ERROR',error=str(e),http_status=e.code)
   if e.code in (401,403,429):self.stop=True
  except Exception as e:r.update(status='UNAVAILABLE',error=str(e));self.stop=True
  r.update(completed_utc=utc(),sha256=hashlib.sha256(body).hexdigest());(OUT/'raw'/f'{self.n:03d}.body').write_bytes(body);save(f'raw/{self.n:03d}.json',r);self.records.append(r)
  if self.stop:raise RuntimeError('Provider/network stop; no retry')
  return j
 def rpc(self,name,method,params):
  r=self.request(name,RPC,{'jsonrpc':'2.0','id':self.n+1,'method':method,'params':params})
  if not isinstance(r,dict) or 'result' not in r:raise ValueError('Missing result: '+str(r))
  return r['result']
 def api(self,name,path,params):return self.request(name,API+path+'?'+urllib.parse.urlencode(params))
 def batch(self,name,items):
  # Every item is assembled exclusively by the fixed public-getter allowlist.
  calls=[(to,True,calldata(sig,types,args)) for to,sig,types,args,ret in items]
  data='0x'+(h(b'aggregate3((address,bool,bytes)[])')[:4]+encode(['(address,bool,bytes)[]'],[calls])).hex()
  raw=self.rpc(name,'eth_call',[{'to':MULTI,'data':data,'gas':hex(12000000)},self.block])
  ans=decode(['(bool,bytes)[]'],bytes.fromhex(raw[2:]))[0]
  if len(ans)!=len(items):raise ValueError('Result count mismatch')
  out=[]
  for (ok,b),item in zip(ans,items):
   try:
    if not ok:raise ValueError('View reverted')
    v=decode(item[4],b);out.append(v[0] if len(v)==1 else v)
   except Exception as e:out.append({'unavailable':True,'error':str(e),'data':'0x'+b.hex()})
  return out
 def one(self,n,to,sig,types=(),args=(),ret=('uint256',)):return self.batch(n,[(to,sig,types,args,ret)])[0]
def pages(c,path,params,maxpages=3):
 rows=[];cursor=None;seen=set()
 for i in range(maxpages):
  r=c.api('page_'+str(i),path,dict(params,**({'cursor':cursor} if cursor else {})))
  if not isinstance(r,dict) or not isinstance(r.get('data'),list):raise ValueError('API shape')
  rows.extend(r['data']);cursor=r.get('cursor')
  if not cursor:return rows,True
  if cursor in seen:break
  seen.add(cursor)
 return rows,False
def main():
 c=Client();s={'started_utc':utc(),'transactions_sent':0,'state_overrides':0,'profit_verified':False,'scope':'three documented Tenor collateral vaults, helper permissions and bounded matching Midnight borrowers; previews/accounting are not cash execution','vaults':{},'markets':[]}
 save('PLAN.json',{**s,'vault_addresses':VAULTS,'helper':HELPER,'max_requests':180,'max_market_pages_per_asset':3,'max_matching_markets':20,'max_borrower_pages_per_market':2,'notes':['No credential or private data','All RPC contract calls are public getters','No liquidations, redemptions, transfers or arbitrary probes are invoked','No privileged callers or state modifications','API discovery may differ from pinned RPC state']})
 try:
  if c.rpc('chain','eth_chainId',[])!='0x2105':raise ValueError('wrong chain')
  b=c.rpc('snapshot','eth_getBlockByNumber',['latest',False]);c.block=b['number'];s['snapshot']={k:b[k] for k in ['number','hash','timestamp','baseFeePerGas']};now=int(b['timestamp'],16)
  code=c.rpc('helper_code','eth_getCode',[HELPER,c.block]);s['helper']={'address':HELPER,'code_present':code!='0x','runtime_sha256':hashlib.sha256(bytes.fromhex(code[2:])).hexdigest(),'midnight_getter':c.one('helper_core',HELPER,'MORPHO_MIDNIGHT()',ret=['address'])}
  for label,v in VAULTS.items():
   sigs=[('asset()','address'),('decimals()','uint256'),('totalAssets()','uint256'),('totalSupply()','uint256'),('liquidityAdapter()','address'),('liquidityData()','bytes'),('receiveSharesGate()','address'),('sendSharesGate()','address'),('receiveAssetsGate()','address'),('sendAssetsGate()','address'),('adaptersLength()','uint256')]
   values=c.batch('vault_'+label,[(v,sig,(),(),[ret]) for sig,ret in sigs]);r=dict(zip([x[0] for x in sigs],values));s['vaults'][label]=r;r['address']=v
   asset=r['asset()']
   if not isinstance(asset,str):continue
   r['asset_decimals'],r['idle_assets'],r['midnight_shares']=c.batch('balances_'+label,[(asset,'decimals()',(),(),['uint256']),(asset,'balanceOf(address)',['address'],[v],['uint256']),(v,'balanceOf(address)',['address'],[CORE],['uint256'])])
   roles={}
   for nm,a in [('ordinary',ORDINARY),('helper',HELPER),('core',CORE)]:
    values=c.batch('roles_'+label+'_'+nm,[(v,f+'(address)',['address'],[a],['bool']) for f in ['canReceiveShares','canSendShares','canReceiveAssets']]);roles[nm]=dict(zip(['receive_shares','send_shares','receive_assets'],values))
   r['permissions']=roles;gate=r['receiveSharesGate()']
   if isinstance(gate,str) and gate!='0x'+'00'*20:r['gate_owner']=c.one('gate_owner_'+label,gate,'owner()',ret=['address'])
   if isinstance(r['midnight_shares'],int):r['preview_core_shares_not_cash']=c.one('preview_core_'+label,v,'previewRedeem(uint256)',['uint256'],[r['midnight_shares']])
   ld=r['liquidityData()'];a=r['liquidityAdapter()']
   if isinstance(ld,bytes) and len(ld)==160 and isinstance(a,str):
    params=decode(['address','address','address','address','uint256'],ld);mid=h(ld)
    market,pos=c.batch('blue_'+label,[(BLUE,'market(bytes32)',['bytes32'],[mid],['uint128']*6),(BLUE,'position(bytes32,address)',['bytes32','address'],[mid,a],['uint256','uint128','uint128'])])
    r['underlying']={'params':params,'market_id':'0x'+mid.hex(),'market':market,'adapter_position':pos}
    if isinstance(market,tuple) and isinstance(pos,tuple):
     supply,ss,borrow,bs,last,fee=market;assets=pos[0]*(supply+1)//(ss+10**6);cash=max(0,supply-borrow)
     r['underlying'].update(stored_market_cash=cash,adapter_assets=assets,accounting_capacity_not_execution=min(assets,cash)+r['idle_assets'])
  listing=[];s['listing_complete']={}
  for asset,minimum in [(USDC,1000000),(WETH,10**14)]:
   rows,done=pages(c,'/v0/midnight/markets',{'chain_ids':8453,'loan_assets':asset,'total_units_gte':minimum,'limit':100});listing.extend(rows);s['listing_complete'][asset]=done
  s['listing']=listing;wanted=set(VAULTS.values());chosen=[];seen=set()
  for m in listing:
   mid=m.get('market_id');cp=m.get('collaterals',[])
   if mid in seen:continue
   seen.add(mid)
   if any(x.get('token','').lower() in wanted for x in cp):chosen.append(m)
  chosen.sort(key=lambda m:(m.get('loan_token',''),-int(m.get('total_units',0))));s['omitted_market_ids']=[m['market_id'] for m in chosen[20:]]
  for j,source in enumerate(chosen[:20]):
   mid=source['market_id'];i=bytes.fromhex(mid[2:]);r={'market_id':mid,'api_definition':source,'borrowers':[]};s['markets'].append(r)
   m,st=c.batch('canonical_market_'+str(j),[(CORE,'toMarket(bytes32)',['bytes32'],[i],[MT]),(CORE,'marketState(bytes32)',['bytes32'],[i],['uint128']*4+['uint16']*7+['uint32','uint8'])]);r.update(market=m,state=st)
   if not isinstance(m,tuple) or not isinstance(st,tuple):r['unavailable']=True;continue
   if m[0]!=8453 or m[1].lower()!=CORE:raise ValueError('market domain')
   r['canonical_debt']=st[0]-st[2];ps,done=pages(c,f'/v0/midnight/markets/{mid}/positions',{'types':'borrow','limit':100,'sort_by':'debt','sort_direction':'desc'},2);r['borrower_listing_complete']=done
   users=sorted({p['user_address'].lower() for p in ps});prices=c.batch('prices_'+str(j),[(x[3],'price()',(),(),['uint256']) for x in m[3]]);r['prices']=prices;total=0;fail=False
   for start in range(0,len(users),30):
    cohort=users[start:start+30];items=[]
    for u in cohort:
     items.append((CORE,'position(bytes32,address)',['bytes32','address'],[i,u],['uint128']*6))
     items.extend((CORE,'collateral(bytes32,address,uint256)',['bytes32','address','uint256'],[i,u,k],['uint128']) for k in range(len(m[3])))
    vals=c.batch('borrowers_'+str(j)+'_'+str(start),items);stride=1+len(m[3])
    for index,u in enumerate(cohort):
     v=vals[index*stride:(index+1)*stride];row={'borrower':u,'position':v[0],'collateral':v[1:]};r['borrowers'].append(row)
     if not isinstance(v[0],tuple) or any(not isinstance(q,int) for q in v[1:]):fail=True;row['unavailable']=True;continue
     d=v[0][4];bitmap=v[0][5];total+=d;active=[q if bitmap&(1<<k) else 0 for k,q in enumerate(v[1:])]
     if any(q and not isinstance(pr,int) for q,pr in zip(active,prices)):fail=True;row['unavailable']=True;continue
     capacity=sum(q*(pr if isinstance(pr,int) else 0)//10**36*cp[1]//10**18 for q,pr,cp in zip(active,prices,m[3]))
     row.update(debt=d,capacity=capacity,health_eligible=d>capacity,overdue=d>0 and now>m[4],claim_shares={cp[0]:q for cp,q in zip(m[3],active) if q and cp[0].lower() in wanted})
   r['read_debt']=total;r['debt_reconciles']=done and not fail and total==r['canonical_debt']
  end=c.rpc('block_recheck','eth_getBlockByNumber',[c.block,False]);s['block_identity_verified']=end['hash']==b['hash']
 except Exception as e:s['incomplete_reason']=repr(e)
 finally:
  s.update(completed_utc=utc(),requests=c.n);save('SUMMARY.json',s)
  print(json.dumps(clean({k:v for k,v in s.items() if k not in ['listing','markets']}),indent=2))
  for m in s['markets']:print('MARKET',m['market_id'],'debt',m.get('canonical_debt'),'coverage',m.get('debt_reconciles'),'eligible',sum(bool(x.get('health_eligible') or x.get('overdue')) for x in m['borrowers']))
if __name__=='__main__':main()
