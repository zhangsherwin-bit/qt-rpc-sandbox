"""Public Base service-fee census. No credentials, signing, broadcasting, or trades."""
import collections,datetime as dt,hashlib,json,pathlib,time,urllib.request,urllib.error
RPC='https://mainnet.base.org'
POOL='0x45b2010d8a4f08b53c9fa7544c51dfd9733732cb'
START=int(dt.datetime(2026,9,21,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,9,24,tzinfo=dt.timezone.utc).timestamp())
OUT=pathlib.Path('evidence')
TOPICS={'claims':'0x81d4e3306aa30f56dc9c3949abd8c27539b445f9ef380425f39f3f7114888e4f','withdrawals':'0xf4e9e956ba4b65051e84982c3ade043c89890cdbc452e9e446afe09cd4db40c8','draw_rewards':'0xecb1c952c58fd78de1639daecf690934ce9017bbd60ceaf3355f80ee8d24e737','increases':'0xeeb4ea63ac93d08466c88060e80ed42f0641debf45e931025fbb35faf5f2ad1a'}
SELECTORS={'prizeToken()':'0xd0ef024a','decimals()':'0x313ce567'}
TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ALLOWED={'eth_chainId','eth_getBlockByNumber','eth_getLogs','eth_call','eth_getCode','eth_getTransactionReceipt'}
def save(n,v):
 p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2))
def uint(s):
 if not isinstance(s,str) or not s.startswith('0x') or len(s)!=66:raise ValueError('uint return shape')
 return int(s,16)
def words(s):
 if not isinstance(s,str) or not s.startswith('0x') or (len(s)-2)%64:raise ValueError('ABI shape')
 return [int(s[2+i:66+i],16) for i in range(0,len(s)-2,64)]
def addr(n):
 if not 0<=n<2**160:raise ValueError('address overflow')
 return '0x'+format(n,'040x')
def decode(log):
 t=log['topics'];w=words(log['data']);kind=next((k for k,v in TOPICS.items() if v==t[0].lower()),None)
 r={'kind':kind,'block':int(log['blockNumber'],16),'block_hash':log['blockHash'],'tx':log['transactionHash'],'index':int(log['logIndex'],16)}
 if kind=='claims':
  if len(w)!=6 or len(t)!=4 or w[0]>=2**24 or w[1]>=2**8 or w[2]>=2**32 or w[3]>=2**152 or w[4]>=2**96:raise ValueError('claim ABI mismatch')
  r.update(draw=w[0],tier=w[1],prize_index=w[2],winner_payout=w[3],reward=w[4],reward_recipient=addr(w[5]),vault='0x'+t[1][-40:],winner='0x'+t[2][-40:])
 elif kind=='withdrawals':
  if len(w)!=2 or len(t)!=3:raise ValueError('withdraw ABI mismatch')
  r.update(account='0x'+t[1][-40:],recipient='0x'+t[2][-40:],amount=w[0],available=w[1])
 elif kind in ('draw_rewards','increases'):
  if len(w)!=1 or len(t)!=2:raise ValueError('reward ABI mismatch')
  r.update(recipient='0x'+t[1][-40:],amount=w[0])
 else:raise ValueError('unknown log')
 return r
class Client:
 def __init__(self):self.n=0;self.started=time.monotonic();self.stopped=False;self.headers={}
 def val(self,name,method,params):
  if method not in ALLOWED or self.stopped or self.n>=360 or time.monotonic()-self.started>780:raise RuntimeError('method/budget/access stop')
  self.n+=1;time.sleep(.55);body=b'';record={'name':name,'url':RPC,'payload':{'jsonrpc':'2.0','id':self.n,'method':method,'params':params},'utc':dt.datetime.now(dt.timezone.utc).isoformat()}
  try:
   req=urllib.request.Request(RPC,json.dumps(record['payload']).encode(),{'Content-Type':'application/json','User-Agent':'QT-Public-Reward-Census/1'})
   with urllib.request.urlopen(req,timeout=22) as res:record['http']=res.status;body=res.read(12000001)
   if len(body)>12000000:raise ValueError('body cap')
   j=json.loads(body)
   if 'error' in j:
    record['status']='RPC_ERROR';record['error']=j['error']
    if any(x in str(j['error']).lower() for x in ('rate limit','quota','forbidden','unauthorized','api key')):self.stopped=True
    raise ValueError(str(j['error']))
   record['status']='OK';result=j['result']
  except urllib.error.HTTPError as e:
   body=e.read(100000);record.update(status='HTTP_ERROR',http=e.code,error=str(e));self.stopped=e.code in (401,403,429);raise
  except Exception as e:record.setdefault('status','UNAVAILABLE');record.setdefault('error',repr(e));raise
  finally:
   record['sha256']=hashlib.sha256(body).hexdigest();save(f'raw/{self.n:04}.json',record);(OUT/'raw'/f'{self.n:04}.body').write_bytes(body)
  return result
 def head(self,n):
  key=str(n)
  if key not in self.headers:self.headers[key]=self.val('header_'+key,'eth_getBlockByNumber',[hex(n) if isinstance(n,int) else n,False])
  return self.headers[key]
 def first(self,t,hi):
  lo=1
  while lo<hi:
   mid=(lo+hi)//2
   if int(self.head(mid)['timestamp'],16)<t:lo=mid+1
   else:hi=mid
  if int(self.head(lo)['timestamp'],16)<t or int(self.head(lo-1)['timestamp'],16)>=t:raise ValueError('boundary')
  return lo
 def view(self,to,sig,block):return self.val(sig,'eth_call',[{'to':to,'data':SELECTORS[sig]},hex(block)])
def run():
 OUT.mkdir(exist_ok=True);c=Client();summary={'experiment':'PoolTogether Base claim-fee census','window':['2026-09-21T00:00:00Z','2026-09-24T00:00:00Z'],'pool':POOL,'new_run':True,'signed_or_sent':0,'profit_established':False,'limitations':['Claim rewards are credits, not automatically cash paid in the same transaction.','Draw rewards and claim rewards are distinct; IncreaseClaimRewards is not added again.','Winner identities are retrospective; no own capture rate.','Official documented address; deployed source equivalence unverified.','Three days do not establish a recurring-income forecast.','L2 plus reported L1 receipt fees are not a complete bot P&L; hidden payments and ownership remain unknown.']}
 save('PLAN.json',{'start':START,'end_exclusive':END,'max_requests':360,'seconds_cap':780,'max_receipts':120,'chunk_blocks':8000,'read_only':True,'scope':'one documented Base PrizePool, all four specified event types, no holdout dates'})
 try:
  if c.val('chain','eth_chainId',[])!='0x2105':raise ValueError('wrong chain')
  latest=c.head('latest');hi=int(latest['number'],16)
  if int(latest['timestamp'],16)<END:raise ValueError('requested period not finished')
  bounds=[c.first(START+i*86400,hi) for i in range(4)];save('BOUNDARIES.json',[{'first':c.head(b),'prior':c.head(b-1)} for b in bounds]);end=bounds[-1]-1
  if c.val('pool_code','eth_getCode',[POOL,hex(end)])=='0x':raise ValueError('not deployed')
  token=addr(uint(c.view(POOL,'prizeToken()',end)));dec=uint(c.view(token,'decimals()',end));summary.update(token=token,decimals=dec,bounds=bounds)
  logs=[]
  for a in range(bounds[0],bounds[-1],8000):
   z=min(a+7999,end);logs+=c.val('reward_logs_'+str(a),'eth_getLogs',[{'address':POOL,'fromBlock':hex(a),'toBlock':hex(z),'topics':[list(TOPICS.values())]}])
  ids=[(x['transactionHash'],x['logIndex']) for x in logs]
  if len(ids)!=len(set(ids)):raise ValueError('duplicate logs')
  rows=[decode(x) for x in logs];rows.sort(key=lambda x:(x['block'],x['index']));save('events.json',rows)
  claims=[r for r in rows if r['kind']=='claims'];withdraw=[r for r in rows if r['kind']=='withdrawals'];draw=[r for r in rows if r['kind']=='draw_rewards'];increases=[r for r in rows if r['kind']=='increases']
  txs=list(dict.fromkeys(r['tx'] for r in rows));sample=txs if len(txs)<=120 else [txs[round(i*(len(txs)-1)/119)] for i in range(120)]
  save('RECEIPTS_SELECTED_BEFORE_READ.json',sample);receipts=[]
  for tx in sample:
   try:
    rec=c.val('receipt_'+tx,'eth_getTransactionReceipt',[tx]);observed=[x for x in logs if x['transactionHash']==tx];canon={(x['address'].lower(),x['logIndex'],tuple(x['topics']),x['data']) for x in rec['logs']}
    if any((x['address'].lower(),x['logIndex'],tuple(x['topics']),x['data']) not in canon for x in observed):raise ValueError('receipt mismatch')
    cost=int(rec['gasUsed'],16)*int(rec['effectiveGasPrice'],16);l1=int(rec['l1Fee'],16) if rec.get('l1Fee') else None
    rr={'tx':tx,'from':rec['from'],'to':rec['to'],'gas':int(rec['gasUsed'],16),'l2_fee_wei':cost,'l1_fee_wei':l1,'status':rec['status'],'canonical_events_matched':True,'claim_rewards':sum(x['reward'] for x in claims if x['tx']==tx),'draw_rewards':sum(x['amount'] for x in draw if x['tx']==tx)}
    rr['token_transfers']=[{'from':'0x'+x['topics'][1][-40:],'to':'0x'+x['topics'][2][-40:],'amount':int(x['data'],16)} for x in rec['logs'] if x['address'].lower()==token and len(x['topics'])==3 and x['topics'][0].lower()==TRANSFER]
    receipts.append(rr)
   except Exception as e:
    receipts.append({'tx':tx,'unavailable':repr(e)})
    if c.stopped:raise
  save('receipts.json',receipts);by=collections.Counter();daily=[]
  for x in claims:by[x['reward_recipient']]+=x['reward']
  for a,b in zip(bounds,bounds[1:]):
   day=[x for x in claims if a<=x['block']<b];dd=[x for x in draw if a<=x['block']<b]
   daily.append({'date':dt.datetime.fromtimestamp(int(c.head(a)['timestamp'],16),dt.timezone.utc).date().isoformat(),'claims':len(day),'claim_transactions':len(set(x['tx'] for x in day)),'claim_reward_raw':sum(x['reward'] for x in day),'winner_payout_raw':sum(x['winner_payout'] for x in day),'reserve_reward_raw':sum(x['amount'] for x in dd)})
  summary.update(complete_log_window=True,events=len(rows),claims=len(claims),claim_transactions=len(set(x['tx'] for x in claims)),claim_reward_raw=sum(x['reward'] for x in claims),winner_payout_raw=sum(x['winner_payout'] for x in claims),draw_reward_raw=sum(x['amount'] for x in draw),withdrawn_raw=sum(x['amount'] for x in withdraw),increase_events_raw=sum(x['amount'] for x in increases),distinct_reward_recipients=len(by),recipient_rewards=dict(by),daily=daily,transactions_total=len(txs),receipts_checked=len(receipts),all_receipts_requested=len(txs)<=120,receipt_failures=sum('unavailable' in x for x in receipts))
 except Exception as e:summary['exception']=repr(e)
 summary['requests']=c.n;summary['provider_stopped']=c.stopped;save('SUMMARY.json',summary);print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':run()
