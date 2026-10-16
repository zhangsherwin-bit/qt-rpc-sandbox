"""Read-only follow-up. Quotes are not complete execution or capture evidence.
No trade sending, approvals, private keys, production modifications or gate bypass.
"""
import json,time
from pathlib import Path
import research as r
r.SIG.update({'quoteExactOutputSingle((address,address,uint256,uint24,uint160))':'bd21704a','MORPHO_MIDNIGHT()':'04e94e04'})
GATE='0x3d7f6b28f46e44e3c40391f2b5f9f27ba067b8b7'
TOPIC='0x5aa2c38263e4b2017df66cfc5381d49c6d788fb63e847c27be3052ea67cc18dc'
QUOTER='0x61ffe014ba17989e743c5f6cb21bf9697530b21e'
USDC='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48';WETH='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
CASES=[{'case':0,'block':25643398,'gross_usdc_raw':'21771872624','candidate_gas':1978572,'modeled_extra_gas':300000,'base_fee_wei':48279366,'producer_wei':'11087584263219454765','eth_to_purchase_wei':'11087694271231000117'}, {'case':1,'block':25649157,'gross_usdc_raw':'451852652','candidate_gas':1728084,'modeled_extra_gas':300000,'base_fee_wei':105462114,'producer_wei':'2819936283644016','eth_to_purchase_wei':'3033822309653592'}, {'case':2,'block':25868887,'gross_usdc_raw':'773613094','candidate_gas':1522681,'modeled_extra_gas':300000,'base_fee_wei':47191488,'producer_wei':'13734909956719340','eth_to_purchase_wei':'13820924985258668'}]

def gate_diagnostic():
 if r.rpc(r.BASE,'base_chain','eth_chainId',[])!='0x2105':raise ValueError('chain')
 h=r.rpc(r.BASE,'base_head','eth_getBlockByNumber',['latest',False]);hi=int(h['number'],16);lo=0;out={'snapshot':h,'scope':'creation-time gate events only, current rights verified independently; not exhaustive permission history'}
 def code(n):return r.rpc(r.BASE,'gate_code_'+str(n),'eth_getCode',[GATE,hex(n)])
 if code(hi) in ('0x',None) or code(0)!='0x':raise ValueError('gate existence controls failed')
 while hi-lo>1:
  mid=(lo+hi)//2;x=code(mid)
  if x is None:raise ValueError('creation search unavailable')
  if x=='0x':lo=mid
  else:hi=mid
 out['first_code_block']=hi
 end=min(hi+8191,int(h['number'],16))
 ls=r.rpc(r.BASE,'initial_gate_roles','eth_getLogs',[{'address':GATE,'fromBlock':hex(hi),'toBlock':hex(end),'topics':[TOPIC]}]);out['logs']=ls
 if not isinstance(ls,list):return out
 users=sorted({'0x'+x['topics'][1][-40:] for x in ls if len(x.get('topics',[]))==2})[:20];out['candidate_count']=len(users);out['candidates']=[]
 for account in users:
  values=r.reads(r.BASE,h['number'],[('receive_shares',r.VAULTS[0],r.call('canReceiveShares(address)',account)),('receive_assets',r.VAULTS[0],r.call('canReceiveAssets(address)',account)),('declared_midnight',account,r.call('MORPHO_MIDNIGHT()'))])
  c=r.rpc(r.BASE,'candidate_code_'+account[-8:],'eth_getCode',[account,h['number']]);out['candidates'].append({'address':account,'views':values,'has_onLiquidate_selector':isinstance(c,str) and '80e49e02' in c,'runtime':c})
 out['hash_check']=r.rpc(r.BASE,'base_hash_check','eth_getBlockByNumber',[h['number'],False])
 return out

def financing_quotes():
 if r.rpc(r.ETH,'eth_chain','eth_chainId',[])!='0x1':raise ValueError('chain')
 out=[]
 for c in CASES:
  item={**c,'quotes':[],'scope':'parent-state finite-size cost, NOT full candidate+swap+producer-payment execution; case 2 parent precedes 18 prefix transactions'};out.append(item)
  for fee in (100,500,3000):
   time.sleep(max(0,10-(time.monotonic()-r.rpc.last.get(r.ETH,0))))
   data=r.call('quoteExactOutputSingle((address,address,uint256,uint24,uint160))',USDC,WETH,int(c['eth_to_purchase_wei']),fee,0)
   x=r.rpc(r.ETH,f'quote_{c["case"]}_{fee}','eth_call',[{'to':QUOTER,'data':data,'gas':hex(3000000)},hex(c['block'])]);q={'fee':fee,'raw':x};item['quotes'].append(q)
   if isinstance(x,str) and len(x)==258:
    b=bytes.fromhex(x[2:]);amount=r.num(b,0);q['USDC_cost_raw']=str(amount);q['model_residual_USDC_raw']=str(int(c['gross_usdc_raw'])-amount);q['quote_gas_estimate']=str(r.num(b,96))
  valid=[q for q in item['quotes'] if 'USDC_cost_raw' in q];item['best']=min(valid,key=lambda q:int(q['USDC_cost_raw'])) if valid else None
 return out

def main():
 s={'started_utc':r.utc(),'transactions_sent':0,'profit_verified':False,'extra_gas_is_assumed_not_measured':300000}
 for name,f in [('gate',gate_diagnostic),('funding',financing_quotes)]:
  try:s[name]=f()
  except Exception as e:s[name]={'error':repr(e)}
  (r.OUT/'SUMMARY.json').write_text(json.dumps(s,indent=2))
 s.update(completed_utc=r.utc(),request_count=r.rpc.count,stopped_endpoints=sorted(r.rpc.stopped));(r.OUT/'SUMMARY.json').write_text(json.dumps(s,indent=2));print(json.dumps({k:v for k,v in s.items() if k not in ('gate','funding')},indent=2))
if __name__=='__main__':main()
