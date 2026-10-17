"""Bounded read-only view audit of the previously identified Tenor cash-claim vault.
No impersonated transfers, signing, broadcasting, storage edits or arbitrary execution.
Returned previews and accounting capacity are not successful redemptions or profit.
"""
import datetime as dt, hashlib, json, time, traceback, urllib.request, urllib.error
from pathlib import Path
from eth_abi import encode,decode
from Crypto.Hash import keccak
RPC='https://mainnet.base.org';OUT=Path('evidence');COUNT=0;STOP=False
CORE='0xAdedD8ab6dE832766Fedf0FaC4992E5C4D3EA18A';BLUE='0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb';USDC='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';VAULT='0xe690a58ef52854513462745237f6a213a0d54df1'
PROBE='0x00000000000000000000000000000000DeaD7714';ZERO='0x'+'00'*20
# Addresses of published Base callbacks; not assumed to be liquidation executors.
ROLES={'ordinary_probe':PROBE,'midnight_core':CORE,'documented_supply_callback':'0xAbae3A858f53C7010D07ee930b3a0621adcFBBA8','documented_withdraw_callback':'0x519d415bf44C623B8E1226E9959E4548cb289F42'}
CASES=[('0x379ae30c5fcb8988c4aac92ddabb13e15c247dd0104157257e6ecf686b7a69dd','0x8eb3a5db0b650bddd2ac457f5500b32c86505a14'),('0x8da96adc9a55288bda5f07eb062d501db04d0fa152dd0f78341f6232bc4f884d','0xd75ffb585ff88d3aa50b7cf9230b27a7eb923c20'),('0x5f21188cf50dcd269250911a64824736d09770d56796cae432a529a679351475','0x37572bf30f51a3076e1586000a856d7ee25800b6')]
MT='(uint256,address,address,(address,uint256,uint256,address)[],uint256,uint256,address,address)'
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def clean(x):
 if isinstance(x,bytes):return '0x'+x.hex()
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 return x
def save(n,x):
 p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean(x),indent=2))
def kh(x):h=keccak.new(digest_bits=256);h.update(x);return h.digest()
def data(sig,types=(),args=()):return '0x'+(kh(sig.encode())[:4]+encode(list(types),list(args))).hex()
def rpc(n,method,params):
 global COUNT,STOP
 if method not in {'eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call'}:raise ValueError('read methods only')
 if STOP or COUNT>=90:raise RuntimeError('budget/access stop')
 time.sleep(0.85);COUNT+=1;p={'jsonrpc':'2.0','id':COUNT,'method':method,'params':params};r={'name':n,'url':RPC,'payload':p,'started_utc':utc()};body=b'';value=None
 try:
  req=urllib.request.Request(RPC,json.dumps(p).encode(),{'Content-Type':'application/json','User-Agent':'QT-Vault-View-Research/1'})
  with urllib.request.urlopen(req,timeout=25) as res:r['http_status']=res.status;body=res.read(1_000_001)
  if len(body)>1_000_000:raise ValueError('body cap')
  j=json.loads(body);r['status']='RPC_ERROR' if 'error' in j else 'OK';value=j.get('result')
 except urllib.error.HTTPError as e:
  body=e.read(100_000);r.update(status='HTTP_ERROR',http_status=e.code,error=str(e))
  if e.code in (401,403,429):STOP=True
 except Exception as e:r.update(status='UNAVAILABLE',error=repr(e))
 r.update(completed_utc=utc(),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body));(OUT/'raw').mkdir(parents=True,exist_ok=True);(OUT/'raw'/f'{COUNT:04d}.body').write_bytes(body);save(f'raw/{COUNT:04d}.json',r)
 if STOP:raise RuntimeError('provider access/rate refusal; not retried')
 return value
def view(n,to,sig,types=(),args=(),returns=('uint256',)):
 r=rpc(n,'eth_call',[{'to':to,'data':data(sig,types,args)},BLOCK])
 if not isinstance(r,str) or r=='0x':return {'unavailable':True}
 try:
  v=decode(list(returns),bytes.fromhex(r[2:]));return v[0] if len(v)==1 else v
 except Exception as e:return {'unavailable':True,'decode_error':repr(e),'raw':r}
def main():
 global BLOCK
 s={'started_utc':utc(),'transactions_sent':0,'profit_verified':False,'vault':VAULT,'scope':'three preselected share-backed borrowers, four role-view controls, default liquidity-adapter accounting; not a complete liquidation simulation','notes':['maxRedeem/maxWithdraw may deliberately return zero in Vault V2; zero is not global zero capacity.','previewRedeem is not executed redemption.','Same-market accounting cash is not total Blue custody.','Documented callbacks are not assumed to be a deployed liquidation executor.']}
 OUT.mkdir(exist_ok=True);save('PLAN.json',{**s,'selected_cases':CASES,'roles':ROLES})
 try:
  assert rpc('chain','eth_chainId',[])=='0x2105';h=rpc('snapshot','eth_getBlockByNumber',['latest',False]);assert isinstance(h,dict);BLOCK=h['number'];s['header']=h
  s['vault_runtime']=rpc('vault_code','eth_getCode',[VAULT,BLOCK]);s['vault_views']={};v=s['vault_views']
  for sig,ret in [('asset()','address'),('totalAssets()','uint256'),('totalSupply()','uint256'),('liquidityAdapter()','address'),('liquidityData()','bytes'),('receiveSharesGate()','address'),('sendSharesGate()','address'),('receiveAssetsGate()','address'),('sendAssetsGate()','address'),('adaptersLength()','uint256')]:v[sig]=view(sig,VAULT,sig,returns=(ret,))
  assert isinstance(v['asset()'],str) and v['asset()'].lower()==USDC.lower()
  v['idle_usdc']=view('vault_USDC',USDC,'balanceOf(address)',['address'],[VAULT]);v['midnight_share_balance']=view('core_share_balance',VAULT,'balanceOf(address)',['address'],[CORE]);v['maxRedeem_core_not_capacity']=view('maxRedeem_core',VAULT,'maxRedeem(address)',['address'],[CORE]);s['role_checks']={}
  for label,a in ROLES.items():
   row={'address':a,'code_present':rpc('code_'+label,'eth_getCode',[a,BLOCK])!='0x'};s['role_checks'][label]=row
   for sig in ['canReceiveShares(address)','canSendShares(address)','canReceiveAssets(address)','canSendAssets(address)']:row[sig]=view(label+'_'+sig,VAULT,sig,['address'],[a],('bool',))
  s['positions']=[]
  for mid,user in CASES:
   row={'market_id':mid,'borrower':user};s['positions'].append(row);market=view('market_'+mid[:10],CORE,'toMarket(bytes32)',['bytes32'],[bytes.fromhex(mid[2:])],(MT,));row['market']=market
   if isinstance(market,dict):continue
   assert market[0]==8453 and market[1].lower()==CORE.lower() and market[2].lower()==USDC.lower()
   indices=[i for i,p in enumerate(market[3]) if p[0].lower()==VAULT.lower()];assert len(indices)==1;i=indices[0]
   row['debt']=view('debt_'+user[:10],CORE,'debt(bytes32,address)',['bytes32','address'],[bytes.fromhex(mid[2:]),user]);shares=view('shares_'+user[:10],CORE,'collateral(bytes32,address,uint256)',['bytes32','address','uint256'],[bytes.fromhex(mid[2:]),user,i]);row['shares']=shares
   row['healthy']=view('health_'+user[:10],CORE,'isHealthy('+MT+',bytes32,address)',[MT,'bytes32','address'],[market,bytes.fromhex(mid[2:]),user],('bool',));row['overdue']=int(h['timestamp'],16)>market[4]
   if isinstance(shares,int):row['previewRedeem_not_cash']=view('preview_'+user[:10],VAULT,'previewRedeem(uint256)',['uint256'],[shares])
  a=v['liquidityAdapter()'];ld=v['liquidityData()'];s['default_blue_liquidity']={};b=s['default_blue_liquidity']
  if isinstance(a,str) and a.lower()!=ZERO and isinstance(ld,bytes) and len(ld)==160:
   params=decode(['address','address','address','address','uint256'],ld);mid=kh(ld);b.update(adapter=a,market_params=params,market_id='0x'+mid.hex());assert params[0].lower()==USDC.lower()
   b['market']=view('blue_market',BLUE,'market(bytes32)',['bytes32'],[mid],('uint128',)*6);b['position']=view('adapter_blue_position',BLUE,'position(bytes32,address)',['bytes32','address'],[mid,a],('uint256','uint128','uint128'))
   if isinstance(b['market'],tuple) and isinstance(b['position'],tuple):
    supply,supplyshares,borrow,_,_,_=b['market'];position_assets=b['position'][0]*(supply+1)//(supplyshares+10**6);b['stored_market_cash']=max(0,supply-borrow);b['adapter_supply_assets_stored']=position_assets;b['default_route_accounting_capacity_not_executed']=min(position_assets,max(0,supply-borrow))+(v['idle_usdc'] if isinstance(v['idle_usdc'],int) else 0)
  else:b['status']='default adapter data shape unsupported or absent; not zero capacity'
  s['end_header']=rpc('same_block_identity','eth_getBlockByNumber',[BLOCK,False]);s['block_identity_verified']=s['end_header']['hash']==h['hash'];assert s['block_identity_verified']
 except Exception as e:s.update(exception=repr(e),traceback=traceback.format_exc())
 s.update(completed_utc=utc(),request_count=COUNT);save('SUMMARY.json',s);print(json.dumps(clean({k:v for k,v in s.items() if k not in ['vault_runtime','header','end_header']}),indent=2))
if __name__=='__main__':main()
