"""Permissionless Curve V2 keeper service-reward census; public reads only."""
import sys,time,json,pathlib,collections
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'service_income'))
import reward_census as base
base.RPC='https://rpc-eth.blockmachine.io'
P={'USDC':'0x9201da0d97caaaff53f01b2fb56767c7072de340','USDT':'0xfb726f57d251ab5c731e5c64ed4f5f94351ef9f3','PYUSD':'0x3fa20eaa107de08b38a8734063d605d5842fe09c','FRXUSD':'0x338cb2d827112d989a861cde87cd9ffd913a1f9d'}
SIG={'pool':'16f0115b','regulator':'dd8fee14','fee_receiver':'cab4d3db','estimate':'d0d18491','vp':'bb7b8b80','share':'df81cd3f','debt':'0dca59c1','coins':'c6610657','withdraw_quote':'cc2b27d7','decimals':'313ce567'}
EVENTS=['0x8d685bd3f45d861c759ed7a46ea3d30eb5cc6ce9fe06c526931f94c963bca7d2','0x5b6b431d4476a211bb7d41c20d1aab9ae2321deee0d20be3d9fc9b1093fa6e3d']
class Client(base.Client):
 def __init__(self):super().__init__();self.last=0
 def val(self,name,method,params):
  gap=70 if method=='eth_getLogs' else (5 if method=='eth_call' else 1.5)
  time.sleep(max(0,gap-(time.monotonic()-self.last)))
  try:return super().val(name,method,params)
  finally:self.last=time.monotonic()
 def view(self,to,key,block,args=()):
  return base.uint(self.val(key+'_'+to,'eth_call',[{'to':to,'data':'0x'+SIG[key]+''.join(f'{x:064x}' for x in args)},hex(block)]))
def first_per_day_proxy(rows,max_n=12):
 if len(rows)<=max_n:return rows
 return [rows[round(i*(len(rows)-1)/(max_n-1))] for i in range(max_n)]
def main():
 base.OUT.mkdir(exist_ok=True);c=Client();summary={'window':['2026-09-21','2026-09-24 exclusive'],'new_run':True,'signed_or_sent':0,'cash_profit_verified':False,'scope':'four documented V2 keepers, not every keeper version','limitations':['LP rewards are not cash earnings. Fee-receiver transfers are excluded; receiver changes within window not yet ruled out.','Only sampled transactions receive canonical receipt and finite-size exit quotes.','Exit quotes use actual end-of-winning-block state, not the exact state during reward receipt.','Bundled winning transaction gas is not necessarily cost attributable solely to the keeper.','No active deployment migration or present-day earning claim.']}
 base.save('PLAN.json',{'keepers':P,'start':base.START,'end':base.END,'request_limit':360,'time_limit_seconds':780,'max_receipts':12,'no_holdout':True})
 try:
  if c.val('chain','eth_chainId',[])!='0x1':raise ValueError('wrong chain')
  hi=int(c.head('latest')['number'],16);a=c.first(base.START,hi);end=c.first(base.END,hi)-1
  base.save('BOUNDARIES.json',{'start':c.head(a),'before':c.head(a-1),'last':c.head(end),'after':c.head(end+1)})
  info={}
  for label,pk in P.items():
   try:
    pool=base.addr(c.view(pk,'pool',end));reg=base.addr(c.view(pk,'regulator',end));receiver=base.addr(c.view(reg,'fee_receiver',end));coins=[base.addr(c.view(pool,'coins',end,(i,))) for i in (0,1)]
    info[pk]={'label':label,'pool':pool,'fee_receiver':receiver,'coins':coins,'caller_share':c.view(pk,'share',end),'debt':c.view(pk,'debt',end),'end_snapshot_estimate_lp':c.view(pk,'estimate',end)}
   except Exception as e:
    info[pk]={'label':label,'unavailable':repr(e)}
    if c.stopped:raise
  base.save('keepers.json',info)
  active=[k for k,v in info.items() if 'pool' in v];pools=list({info[k]['pool'] for k in active});summary['keepers']=info
  actions=c.val('all_keeper_actions','eth_getLogs',[{'address':active,'fromBlock':hex(a),'toBlock':hex(end),'topics':[EVENTS]}])
  transfers=c.val('all_keeper_lp_transfers','eth_getLogs',[{'address':pools,'fromBlock':hex(a),'toBlock':hex(end),'topics':[base.TRANSFER,['0x'+k[2:].rjust(64,'0') for k in active]]}])
  actset={(x['transactionHash'],x['address'].lower()) for x in actions};rewards=[];excluded=[]
  for x in transfers:
   pk='0x'+x['topics'][1][-40:].lower();to='0x'+x['topics'][2][-40:].lower();amount=int(x['data'],16)
   row={'keeper':pk,'pool':x['address'].lower(),'recipient':to,'lp_raw':amount,'block':int(x['blockNumber'],16),'block_hash':x['blockHash'],'tx':x['transactionHash'],'log_index':int(x['logIndex'],16)}
   if x['address'].lower()!=info[pk]['pool'] or to==info[pk]['fee_receiver'] or (x['transactionHash'],pk) not in actset:excluded.append(row)
   elif amount:rewards.append(row)
  rewards.sort(key=lambda r:(r['block'],r['log_index']));base.save('reward_candidates.json',rewards);base.save('excluded_transfers.json',excluded)
  # Select evenly spaced chronological rewards, not the largest payouts.
  selected=first_per_day_proxy(rewards);base.save('SELECTED_BEFORE_EXIT_QUOTES.json',selected);samples=[]
  for x in selected:
   r=dict(x)
   try:
    receipt=c.val('receipt_'+x['tx'],'eth_getTransactionReceipt',[x['tx']]);hit=[z for z in receipt['logs'] if z['address'].lower()==x['pool'] and int(z['logIndex'],16)==x['log_index']]
    if len(hit)!=1 or int(hit[0]['data'],16)!=x['lp_raw'] or receipt['blockHash']!=x['block_hash']:raise ValueError('canonical reward mismatch')
    header=c.head(x['block']);r.update(sender=receipt['from'],gas_used=int(receipt['gasUsed'],16),network_fee_wei=int(receipt['gasUsed'],16)*int(receipt['effectiveGasPrice'],16),base_fee_wei=int(header['baseFeePerGas'],16),timestamp=int(header['timestamp'],16),canonical_reward_verified=True)
    coins=info[x['keeper']]['coins'];i=next(j for j,t in enumerate(coins) if t!='0xf939e0a03fb07f59a73314e73794be0e57ac1b4e')
    r['cash_token']=coins[i];r['cash_decimals']=c.view(coins[i],'decimals',x['block']);r['exit_quote_raw']=c.view(x['pool'],'withdraw_quote',x['block'],(x['lp_raw'],i))
   except Exception as e:
    r['unavailable']=repr(e)
    if c.stopped:raise
   samples.append(r);base.save('samples.json',samples)
  totals=collections.Counter();recipients=collections.Counter()
  for r in rewards:totals[r['keeper']]+=r['lp_raw'];recipients[r['recipient']]+=1
  summary.update(complete_requested_logs=True,action_events=len(actions),reward_candidates=len(rewards),reward_transactions=len(set(x['tx'] for x in rewards)),lp_totals_by_keeper=dict(totals),recipient_event_counts=dict(recipients),excluded_transfers=len(excluded),samples=samples)
 except Exception as e:summary['exception']=repr(e)
 summary.update(requests=c.n,provider_stopped=c.stopped);base.save('SUMMARY.json',summary);print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
