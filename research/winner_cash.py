"""Public historical transaction observations and exact position reads only.
Selection is frozen after repayment-volume census, BEFORE reading winner cash.
No transaction submission, wallet, key, state override or private endpoint.
"""
import json,time,hashlib,urllib.request,urllib.error,datetime as dt,traceback
from pathlib import Path
import public_economics as p
OUT=Path('evidence');OUT.mkdir(exist_ok=True);(OUT/'winner_raw').mkdir(exist_ok=True)
CASES=[
 ['cbLTC','0x5bc6b67722b3e93d35cf01644401d9a145580c4337c65a2583672cc21569d25a'],
 ['SOL','0xd93e14f62bfb553efe9c680e854d23189527c7cfd14f6d2202c1913c7b615adc'],
 ['SOL_batch','0x0f054a7c9fe526aca1d6c2d18b83231415e9575e0de23a95b4ec8e5e78cc1f89'],
 ['cbDOGE','0x3c35def3e8c240fae27b94eec1c5b528122b43c0c4a07c796988b03b255ee23d'],
 ['cbLTC_later_day','0x25c144ac699679cd90733520396025b6117947cf9d69077cc509c2c9d93ed0a7'],
 ['cbZEC','0xbba451a6cade83a6e603463b2872fc15fee1b23f9b607baa45a06b7ff65d301f']]
COUNT=0;STOP=set();RECORDS=[]
def req(name,url,obj=None):
 global COUNT
 host=urllib.parse.urlsplit(url).hostname
 if host not in {'mainnet.base.org','base.blockscout.com'}:raise ValueError('host not approved')
 if host in STOP:raise ValueError('access boundary; not retried')
 if obj and obj['method'] not in {'eth_getTransactionReceipt','eth_getTransactionByHash','eth_getBlockByNumber','eth_call'}:raise ValueError('read only')
 if COUNT>=45:raise ValueError('bounded requests')
 COUNT+=1;time.sleep(1.8);r={'name':name,'url':url,'payload':obj,'started_utc':p.utc()};body=b'';answer=None
 try:
  q=urllib.request.Request(url,data=json.dumps(obj).encode() if obj else None,headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'QT-public-receipt-audit/1'})
  with urllib.request.urlopen(q,timeout=20) as response:body=response.read(8000001);r['http_status']=response.status
  if len(body)>8000000:raise ValueError('response cap')
  answer=json.loads(body);r['status']='API_ERROR' if isinstance(answer,dict) and ('error' in answer or 'errors' in answer) else 'OK'
 except urllib.error.HTTPError as e:
  r.update(status='HTTP_ERROR',http_status=e.code,error=str(e));body=e.read(50000)
  if e.code in (401,403,429):STOP.add(host)
 except Exception as e:r.update(status='UNAVAILABLE',error=repr(e))
 r.update(completed_utc=p.utc(),sha256=hashlib.sha256(body).hexdigest());RECORDS.append(r)
 (OUT/'winner_raw'/f'{COUNT:03d}.body').write_bytes(body);(OUT/'winner_raw'/f'{COUNT:03d}.json').write_text(json.dumps(r,indent=2))
 return answer
def rpc(n,method,params):
 r=req(n,p.RPC,{'jsonrpc':'2.0','id':COUNT+1,'method':method,'params':params})
 return r.get('result') if isinstance(r,dict) else None
def winners():
 out={'selection':'Six largest distinct Base USDC transaction cases chosen from the earlier 247-event census; hindsight sample, not trading validation.','cases':[]}
 for symbol,txid in CASES:
  rec={'label':symbol,'hash':txid};out['cases'].append(rec)
  try:
   rec['receipt']=rpc(symbol+'_receipt','eth_getTransactionReceipt',[txid])
   rec['transaction']=rpc(symbol+'_transaction','eth_getTransactionByHash',[txid])
   if rec['receipt']:rec['block_header']=rpc(symbol+'_block','eth_getBlockByNumber',[rec['receipt']['blockNumber'],False])
   rec['raw_trace']=req(symbol+'_trace','https://base.blockscout.com/api/v2/transactions/'+txid+'/raw-trace')
  except Exception as e:rec['error']=repr(e)
  p.save('winner_observations.json',out)
 return out

def complete_positions():
 out={'purpose':'Complete two previously truncated borrower cohorts; same-block reads of every returned position.','markets':[]}
 ids=['0x6cb9f4a081803895ee5f8cb611c9a7ad7ccadd88d8a8343f478d9e5646efecac','0x0ff32a563814a0e5822441b77c1b463da99f095d686cb09b637d5d80418cffed']
 ls,lc,le=p.paged('all_ge100','/v0/midnight/markets',{'chain_ids':8453,'loan_assets':p.USDC,'total_units_gte':str(100*10**6),'limit':100},4)
 out.update(ge100_markets=ls,ge100_listing_complete=lc,listing_error=le)
 ps={}
 for mid in ids:
  rs,ok,err=p.paged('all_positions_'+mid[:10],f'/v0/midnight/markets/{mid}/positions',{'types':'borrow','limit':100,'sort_by':'debt','sort_direction':'desc'},12)
  ps[mid]=(rs,ok,err)
 head=p.rpc('complete_snapshot','eth_getBlockByNumber',['latest',False]);B=head['number'];now=int(head['timestamp'],16);out['snapshot']={k:head[k] for k in ['number','hash','timestamp']}
 for mid in ids:
  r={'market_id':mid,'positions':[]};out['markets'].append(r)
  try:
   res=p.batch('market_'+mid[:10],[(p.CORE,p.data('toMarket(bytes32)',['bytes32'],[bytes.fromhex(mid[2:])])),(p.CORE,p.data('marketState(bytes32)',['bytes32'],[bytes.fromhex(mid[2:])]))],B)
   if not all(x[0] for x in res):raise ValueError('market views failed')
   m=p.decode([p.MT],res[0][1])[0];state=p.words(res[1][1]);r.update(definition=m,state=state)
   orc=p.batch('price_'+mid[:10],[(cp[3],p.data('price()')) for cp in m[3]],B);prices=[p.words(v)[0] if ok else None for ok,v in orc];r['prices']=prices
   cohort,complete,err=ps[mid];r.update(discovery_complete=complete,api_error=err,api_count=len(cohort));debt_sum=0;failed=0
   for off in range(0,len(cohort),40):
    cs=cohort[off:off+40];items=[]
    for x in cs:
     u=x['user_address'];items.append((p.CORE,p.data('position(bytes32,address)',['bytes32','address'],[bytes.fromhex(mid[2:]),u])))
     items.extend((p.CORE,p.data('collateral(bytes32,address,uint256)',['bytes32','address','uint256'],[bytes.fromhex(mid[2:]),u,j])) for j in range(len(m[3])))
    br=p.batch('positions_'+mid[:10]+'_'+str(off),items,B);step=len(m[3])+1
    for j,x in enumerate(cs):
     row={'borrower':x['user_address']};r['positions'].append(row);vals=br[j*step:(j+1)*step]
     if not all(v[0] for v in vals):row['error']='missing';failed+=1;continue
     pos=p.words(vals[0][1]);am=[p.words(v[1])[0] for v in vals[1:]];debt_sum+=pos[4]
     active=[a if pos[5]&(1<<i) else 0 for i,a in enumerate(am)]
     if any(a and price is None for a,price in zip(active,prices)):row['error']='unknown active oracle';failed+=1;continue
     md=sum((a*(price or 0)//p.SCALE)*cp[1]//p.W for a,price,cp in zip(active,prices,m[3]))
     row.update(position_words=pos,amounts=am,max_debt_raw=md,health_eligible=pos[4]>md,post_maturity_eligible=pos[4]>0 and now>m[4])
   r.update(debt_sum_raw=debt_sum,canonical_debt_raw=state[0]-state[2],reconciles=complete and failed==0 and debt_sum==state[0]-state[2])
  except Exception as e:r['error']=repr(e)
  p.save('complete_positions.json',out)
 return out
if __name__=='__main__':
 summary={'no_transactions':True,'no_state_overrides':True,'started_utc':p.utc()}
 for name,fn in [('winners',winners),('positions',complete_positions)]:
  try:
   result=fn();summary[name]={'cases':len(result.get('cases',[]))} if name=='winners' else {'markets':[{'id':m['market_id'],'count':len(m['positions']),'reconciles':m.get('reconciles'),'error':m.get('error')} for m in result['markets']],'listing_count':len(result.get('ge100_markets',[])),'listing_complete':result.get('ge100_listing_complete')}
  except Exception as e:summary[name]={'error':repr(e),'traceback':traceback.format_exc()}
  p.save('followup_summary.json',summary)
 summary.update(finished_utc=p.utc(),winner_request_count=COUNT,position_request_count=p.COUNT);p.save('followup_summary.json',summary);print(json.dumps(summary,indent=2))
