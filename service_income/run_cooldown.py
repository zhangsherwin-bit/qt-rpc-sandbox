"""A lower-rate continuation after an HTTP429, not a new endpoint or identity.
Uses verified prior boundaries rather than repeating 80 discovery calls. Waits
at least 10 minutes after the observed refusal; 2000-block chunks, 5.5 seconds
minimum per request. No immediate retry; a second refusal stops this job too.
"""
import collections,datetime as dt,json,time
import reward_census as r
BOUNDS=[51579727,51622927,51666127,51709327]
HASHES=['0x707fe30ea821476211bdb091e7e1ced521a9dd3144cbc2d87c4024e32f54ff62','0xd0b95d71f5dc983e4dce4c10646e728c1f0672916f37e38b915415617d807cd6','0x3422cda6ab380abb294d24e1d81c60602b68e137f25960ff29f1f9e2d8ef4894','0x5f0afab5c56c3adf05dda01bbadf274187a007b4f2aa43b6a0be1babfe786d8c']
PREVIOUS_REFUSAL=dt.datetime.fromisoformat('2026-10-17T07:35:33.423058+00:00').timestamp()
class Slow(r.Client):
 def val(self,*args):
  time.sleep(5)
  return super().val(*args)
def run():
 wait=max(0,PREVIOUS_REFUSAL+600-time.time())
 if wait>600:raise ValueError('unexpected clock')
 time.sleep(wait);r.OUT.mkdir(exist_ok=True);c=Slow()
 summary={'scope':'Base claim service fees September 21–24 UTC','previous_refusal_preserved':True,'same_endpoint_no_identity_rotation':True,'cooldown_seconds_at_start':time.time()-PREVIOUS_REFUSAL,'boundary_origin':'prior run 39014141886, raw headers verified again','signed_or_sent':0,'profit_established':False,'all_prizes_are_not_caller_revenue':True}
 r.save('PLAN.json',{'bounds':BOUNDS,'boundary_hashes':HASHES,'range_chunk':2000,'minimum_interval_seconds':5.5,'max_receipts':40,'max_calls':360,'max_seconds':780,'claim_rewards_separate_from_draw_rewards_and_prizes':True})
 try:
  if c.val('chain','eth_chainId',[])!='0x2105':raise ValueError('wrong chain')
  for i,b in enumerate(BOUNDS):
   h=c.head(b);p=c.head(b-1);t=r.START+i*86400
   if h['hash']!=HASHES[i] or int(h['timestamp'],16)<t or int(p['timestamp'],16)>=t:raise ValueError('boundary mismatch')
  end=BOUNDS[-1]-1;token=r.addr(r.uint(c.view(r.POOL,'prizeToken()',end)));dec=r.uint(c.view(token,'decimals()',end));summary.update(token=token,decimals=dec)
  logs=[]
  for a in range(BOUNDS[0],BOUNDS[-1],2000):
   got=c.val('events_'+str(a),'eth_getLogs',[{'address':r.POOL,'fromBlock':hex(a),'toBlock':hex(min(a+1999,end)),'topics':[list(r.TOPICS.values())]}]);logs+=got
  if len({(x['transactionHash'],x['logIndex']) for x in logs})!=len(logs):raise ValueError('duplicate events')
  rows=sorted((r.decode(x) for x in logs),key=lambda x:(x['block'],x['index']));r.save('events.json',rows)
  claims=[x for x in rows if x['kind']=='claims'];draw=[x for x in rows if x['kind']=='draw_rewards'];wd=[x for x in rows if x['kind']=='withdrawals'];inc=[x for x in rows if x['kind']=='increases']
  fees=collections.Counter();counts=collections.Counter()
  for x in claims:fees[x['reward_recipient']]+=x['reward'];counts[x['reward_recipient']]+=1
  daily=[]
  for i,(a,b) in enumerate(zip(BOUNDS,BOUNDS[1:])):
   day=[x for x in claims if a<=x['block']<b];dr=[x for x in draw if a<=x['block']<b]
   daily.append({'date':dt.datetime.fromtimestamp(r.START+i*86400,dt.timezone.utc).date().isoformat(),'claims':len(day),'claim_transactions':len({x['tx'] for x in day}),'claim_reward_raw':sum(x['reward'] for x in day),'winner_payout_raw':sum(x['winner_payout'] for x in day),'reserve_reward_raw':sum(x['amount'] for x in dr)})
  txs=list(dict.fromkeys(x['tx'] for x in rows));sample=txs if len(txs)<=40 else [txs[round(i*(len(txs)-1)/39)] for i in range(40)]
  r.save('RECEIPTS_SELECTED_BEFORE_READ.json',sample)
  summary.update(complete_log_window=True,events=len(rows),claims=len(claims),claim_transactions=len({x['tx'] for x in claims}),claim_reward_raw=sum(x['reward'] for x in claims),winner_payout_raw=sum(x['winner_payout'] for x in claims),draw_reward_raw=sum(x['amount'] for x in draw),withdrawn_raw=sum(x['amount'] for x in wd),increase_events_raw=sum(x['amount'] for x in inc),recipient_rewards=dict(fees),recipient_claim_counts=dict(counts),daily=daily,transactions_total=len(txs),all_receipts_requested=len(txs)<=40)
  r.save('SUMMARY.json',summary);receipts=[]
  for tx in sample:
   rec=c.val('receipt_'+tx,'eth_getTransactionReceipt',[tx]);observed=[x for x in logs if x['transactionHash']==tx];canon={(x['address'].lower(),x['logIndex'],tuple(x['topics']),x['data']) for x in rec['logs']}
   if any((x['address'].lower(),x['logIndex'],tuple(x['topics']),x['data']) not in canon for x in observed):raise ValueError('receipt mismatch')
   rr={'tx':tx,'from':rec['from'],'to':rec['to'],'block':int(rec['blockNumber'],16),'gas':int(rec['gasUsed'],16),'l2_fee_wei':int(rec['gasUsed'],16)*int(rec['effectiveGasPrice'],16),'l1_fee_wei':int(rec['l1Fee'],16) if rec.get('l1Fee') else None,'canonical_events_matched':True,'claim_rewards':sum(x['reward'] for x in claims if x['tx']==tx),'draw_rewards':sum(x['amount'] for x in draw if x['tx']==tx)}
   rr['token_transfers']=[{'from':'0x'+x['topics'][1][-40:],'to':'0x'+x['topics'][2][-40:],'amount':int(x['data'],16)} for x in rec['logs'] if x['address'].lower()==token and len(x['topics'])==3 and x['topics'][0].lower()==r.TRANSFER]
   receipts.append(rr);r.save('receipts.json',receipts)
  summary.update(receipts_checked=len(receipts),receipt_failures=0)
 except Exception as e:summary['exception']=repr(e)
 summary.update(requests=c.n,provider_stopped=c.stopped);r.save('SUMMARY.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
