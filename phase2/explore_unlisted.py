"""Bounded unlisted Base USDC credit-market and collateral-identity screen.
Read-only views, no keys/signing/transactions/state overrides. Oracle value is not cash.
Selection frozen before acquisition: >=100 USDC face, max16 unlisted markets,
max500 discovered borrowers per market, all canonical state read at one block.
"""
import datetime,json,pathlib
from codec import *
from run import Client,Stop,rows,utc
MULTI='0xcA11bde05977b3631167028862bE2a173976CA11'
W=10**18;SCALE=10**36

def aggregate_data(items):
 entries=[tuple_body([(False,addr(to)),(False,word(1)),(True,dyn_bytes(bhex(data)))]) for to,data in items]
 offset=32*len(entries);heads=[]
 for entry in entries:heads.append(word(offset));offset+=len(entry)
 return selector('aggregate3((address,bool,bytes)[])')+(word(32)+word(len(entries))+b''.join(heads+entries)).hex()

def aggregate_decode(raw,count):
 b=bhex(raw)
 def u(i):
  if i<0 or i+32>len(b):raise ValueError('truncated ABI')
  return int.from_bytes(b[i:i+32],'big')
 base=u(0);n=u(base)
 if n!=count:raise ValueError('multicall count mismatch')
 out=[];start=base+32
 for i in range(n):
  pos=start+u(start+i*32);success=u(pos);data_start=pos+u(pos+32);length=u(data_start)
  if success not in (0,1) or length>200000 or data_start+32+length>len(b):raise ValueError('invalid multicall result')
  out.append({'ok':bool(success),'data':'0x'+b[data_start+32:data_start+32+length].hex()})
 return out

def batch(c,items,B):
 raw=c.value('eth_call',[{'to':MULTI,'data':aggregate_data(items),'gas':hex(14_000_000)},B])
 return aggregate_decode(raw,len(items))

def vword(result):
 if not result['ok']:return None
 x=decode_words(result['data']);return x[0] if x else None

def textresult(result):
 if not result['ok']:return None
 b=bhex(result['data'])
 try:
  if len(b)==32:return b.rstrip(b'\0').decode('utf-8')
  if len(b)<64 or int.from_bytes(b[:32],'big')!=32:return None
  n=int.from_bytes(b[32:64],'big')
  if n>128 or len(b)<64+n:return None
  return b[64:64+n].decode('utf-8')
 except (ValueError,UnicodeError):return None

def paged(c,path,params,pages):
 total=[];cursor=None;seen=set()
 for _ in range(pages):
  r=c.get(path,**dict(params,**({'cursor':cursor} if cursor else {})));total.extend(rows(r));cursor=r.get('cursor')
  if not cursor:return total,True
  if cursor in seen:break
  seen.add(cursor)
 return total,False

def run():
 out=pathlib.Path(__file__).resolve().parent/('unlisted_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(exist_ok=True)
 c=Client(out/'raw',180);s={'started_utc':utc(),'new_market_universe_rule':'Base USDC face >=100, up to16 unlisted markets, <=500 borrowers per market','profit_verified':False,'transactions_sent':0,'state_overrides':0,'markets':[],'tokens':{},'warnings':['Oracle values are not executable cash.','No redemption or liquidation simulation is implemented here.','REST discovery predates pinned blockchain snapshot.']}
 try:
  universe,complete=paged(c,'/v0/midnight/markets',{'chain_ids':8453,'loan_assets':USDC,'total_units_gte':100000000,'limit':100},3)
  s['universe']=universe;s['listing_complete']=complete
  candidates=[]
  for m in universe:
   if m['chain_id']==8453 and m['loan_token'].lower()==USDC.lower() and not m.get('listed',False) and market_id(m)==m['market_id']:candidates.append(m)
  candidates.sort(key=lambda m:-int(m['total_units']));s['omitted_ids']=[x['market_id'] for x in candidates[16:]];candidates=candidates[:16]
  discovery={}
  for m in candidates:
   try:
    ps,done=paged(c,f"/v0/midnight/markets/{m['market_id']}/positions",{'types':'borrow','limit':100,'sort_by':'debt','sort_direction':'desc'},5)
    seen=set();unique=[]
    for p in ps:
     u=p['user_address'].lower()
     if u not in seen:unique.append(p);seen.add(u)
    discovery[m['market_id']]={'positions':unique,'complete':done,'duplicates':len(ps)-len(unique)}
   except Stop:raise
   except Exception as e:discovery[m['market_id']]={'error':repr(e)}
  s['discovery']=discovery
  if int(c.value('eth_chainId',[]),16)!=8453:raise Stop('wrong chain')
  head=c.value('eth_getBlockByNumber',['latest',False]);B=head['number'];now=int(head['timestamp'],16);s['snapshot']={k:head[k] for k in ['number','hash','timestamp']}
  control=batch(c,[(USDC,view_data('decimals()'))],B)
  if vword(control[0])!=6:raise Stop('multicall control or token precision mismatch')
  tokens=sorted({p['token'].lower() for m in candidates for p in m['collaterals']})
  for token in tokens:
   signatures=['symbol()','name()','decimals()','asset()','totalAssets()','totalSupply()']
   values=batch(c,[(token,selector(sig)) for sig in signatures],B);rec={'raw':dict(zip(signatures,values))};s['tokens'][token]=rec
   rec.update(symbol=textresult(values[0]),name=textresult(values[1]),decimals=vword(values[2]))
   asset=vword(values[3]);rec['asset']='0x'+format(asset,'040x') if asset is not None and asset<2**160 else None
   rec['reported_total_assets_raw']=str(vword(values[4])) if vword(values[4]) is not None else None
   rec['asset_identification_is_not_redemption_proof']=True
  for m in candidates:
   mid=m['market_id'];rec={'market_id':mid,'definition':m,'borrowers':[]};s['markets'].append(rec)
   try:
    state=c.view(CORE,'marketState(bytes32)',[mid],B)
    if len(state)!=13:raise ValueError('state shape')
    rec['state']=[str(x) for x in state];rec['withdrawable_raw']=str(state[2]);rec['canonical_debt_raw']=str(state[0]-state[2])
    oracles=batch(c,[(p['oracle'],selector('price()')) for p in m['collaterals']],B);prices=[vword(x) for x in oracles];rec['oracle_prices_raw']=[str(x) if x is not None else None for x in prices]
    d=discovery[mid]
    if 'error' in d:raise ValueError(d['error'])
    ps=d['positions'];total_debt=0;failures=0
    for start in range(0,len(ps),40):
     cohort=ps[start:start+40];items=[]
     for p in cohort:
      u=p['user_address'];items.append((CORE,view_data('position(bytes32,address)',mid,u)))
      for i in range(len(m['collaterals'])):items.append((CORE,view_data('collateral(bytes32,address,uint256)',mid,u,i)))
     ans=batch(c,items,B);step=1+len(m['collaterals'])
     for i,p in enumerate(cohort):
      a=ans[i*step:(i+1)*step];r={'borrower':p['user_address']};rec['borrowers'].append(r)
      if not all(v['ok'] for v in a):r['error']='view failed';failures+=1;continue
      pos=decode_words(a[0]['data']);amount=[vword(v) for v in a[1:]]
      if len(pos)!=6 or any(v is None for v in amount):r['error']='shape';failures+=1;continue
      D=pos[4];total_debt+=D;active=[v if pos[5]&(1<<j) else 0 for j,v in enumerate(amount)]
      r.update(debt_raw=str(D),bitmap=pos[5],collateral_raw=[str(x) for x in amount],active_collateral_raw=[str(x) for x in active])
      if any(v and (pr is None or pr==0) for v,pr in zip(active,prices)):r['error']='unknown oracle';failures+=1;continue
      capacity=sum((v*(pr or 0)//SCALE)*int(cp['lltv'])//W for v,pr,cp in zip(active,prices,m['collaterals']))
      r.update(capacity_raw=str(capacity),health_eligible=D>capacity,post_maturity_eligible=D>0 and now>m['maturity'])
    rec.update(read_debt_raw=str(total_debt),debt_reconciles=d['complete'] and failures==0 and total_debt==state[0]-state[2],current_eligible_positions=sum(bool(r.get('health_eligible') or r.get('post_maturity_eligible')) for r in rec['borrowers']))
   except Stop:raise
   except Exception as e:rec['error']=repr(e)
  reread=c.value('eth_getBlockByNumber',[B,False]);s['snapshot_hash_unchanged']=reread['hash']==head['hash'];s['status']='BOUNDED_VIEW_SCREEN_COMPLETE'
 except Exception as e:s.update(status='PARTIAL_OR_UNAVAILABLE',error=repr(e))
 finally:
  s.update(completed_utc=utc(),requests=c.count);(out/'SUMMARY.json').write_text(json.dumps(s,indent=2))
  print(json.dumps({k:v for k,v in s.items() if k not in ['universe','markets','discovery','tokens']},indent=2))
  for k,v in s['tokens'].items():print('TOKEN',k,{x:v.get(x) for x in ['symbol','name','decimals','asset']})
  for m in s['markets']:print('MARKET',m['market_id'],m.get('canonical_debt_raw'),m.get('current_eligible_positions'),m.get('debt_reconciles'),m.get('error'))
 return out
if __name__=='__main__':run()
