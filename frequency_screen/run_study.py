"""Read-only finite-route quotes followed by bounded cash simulations. No signing."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error

BASE=Path(__file__).resolve().parent
OUT=Path('evidence')
RPC='https://rpc-eth.blockmachine.io'
QUOTE='0x00000000000000000000000000000000dead7730'
CASH='0x00000000000000000000000000000000dead7731'
CALLER='0x00000000000000000000000000000000dead7732'
USDC='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
MORPHO='0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb'
TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ALLOWED={'eth_chainId','eth_getCode','eth_getBlockByNumber','eth_call','eth_simulateV1'}
SIZES=(100,250,500,1000,2000,2500,5000,20000)
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def save(name,obj):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2))
def encode(selector,*v):
 if len(selector)!=8 or any(type(x)!=int or x<0 or x>=2**256 for x in v):raise ValueError('uint encoding')
 return '0x'+selector+''.join(f'{x:064x}' for x in v)
def words(raw,n):
 if not isinstance(raw,str) or not raw.startswith('0x') or len(raw)!=2+n*64:raise ValueError('return shape')
 return [int(raw[2+i*64:66+i*64],16) for i in range(n)]
def decode_quotes(raw,h):
 w=words(raw,260)
 if w[:4]!=[1,int(h['number'],16),int(h['timestamp'],16),int(h['baseFeePerGas'],16)]:raise ValueError('quote environment')
 out=[]
 for i in range(32):
  r=w[4+i*8:12+i*8];amount,fee,rev,ok,output,a,b,diag=r
  if (amount,fee,rev)!=(SIZES[i//4]*10**6,100 if (i//2)%2==0 else 500,i%2):raise ValueError('row identity')
  out.append({'principal_raw':amount,'fee':fee,'reverse':bool(rev),'quote_success':ok==1,'output_raw':output if ok else None,'gross_raw':output-amount if ok else None,'leg1_raw':a if ok else None,'leg2_raw':b if ok else None,'diagnostic':diag})
 return out
class Client:
 def __init__(self):self.count=0;self.last=0.;self.start=time.monotonic();self.stop=False
 def val(self,name,method,params):
  if method not in ALLOWED:raise ValueError('method not permitted')
  if self.stop or self.count>=100 or time.monotonic()-self.start>1000:raise RuntimeError('budget/access stop')
  gap=70 if method=='eth_simulateV1' else (6 if method=='eth_call' else 2)
  time.sleep(max(0,gap-(time.monotonic()-self.last)));self.count+=1
  payload={'jsonrpc':'2.0','id':self.count,'method':method,'params':params};m={'name':name,'url':RPC,'payload':payload,'started_utc':utc()};body=b'';result=None
  try:
   request=urllib.request.Request(RPC,json.dumps(payload).encode(),{'Content-Type':'application/json','User-Agent':'QT-ReadOnly-Two-Direction-Research/1'})
   with urllib.request.urlopen(request,timeout=55) as r:m['http_status']=r.status;body=r.read(12000001)
   if len(body)>12000000:raise ValueError('body cap')
   result=json.loads(body);m['status']='RPC_ERROR' if 'error' in result else 'OK'
   if 'error' in result and any(x in str(result['error']).lower() for x in ('rate limit','unauthorized','quota exceeded','api key required','forbidden')):self.stop=True
  except urllib.error.HTTPError as e:
   body=e.read(100000);m.update(status='HTTP_ERROR',http_status=e.code,error=str(e));self.stop=e.code in (401,403,429)
  except Exception as e:m.update(status='UNAVAILABLE',error=repr(e))
  self.last=time.monotonic();m.update(completed_utc=utc(),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body));save(f'raw/{self.count:04d}.json',m);(OUT/'raw'/f'{self.count:04d}.body').write_bytes(body)
  if self.stop:raise RuntimeError('provider denied request; no retry or alternate endpoint')
  if not isinstance(result,dict) or 'error' in result or 'result' not in result:raise ValueError('RPC unavailable: '+str(result)[:400])
  return result['result']

def build():
 import solcx
 src=(BASE/'RouteStudy.sol').read_text();inp={'language':'Solidity','sources':{'RouteStudy.sol':{'content':src}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.methodIdentifiers','evm.deployedBytecode.object']}}}}
 solcx.install_solc('0.8.34');ob=solcx.compile_standard(inp,solc_version='0.8.34');save('compiler_input.json',inp);save('compiler_output.json',ob)
 out={}
 for name in ('QuoteStudy','CashStudy'):
  evm=ob['contracts']['RouteStudy.sol'][name]['evm'];code='0x'+evm['deployedBytecode']['object'];(OUT/(name+'.hex')).write_text(code);out[name]=(code,evm['methodIdentifiers'])
 save('build.json',{'source_sha256':hashlib.sha256(src.encode()).hexdigest(),'runtime_sha256':{k:hashlib.sha256(bytes.fromhex(v[0][2:])).hexdigest() for k,v in out.items()}})
 return out

def simulate(c,h,row,code,ids,offset=1):
 block=int(h['number'],16)+offset
 parent=h if offset==1 else c.val('delay_parent','eth_getBlockByNumber',[hex(block-1),False])
 target=c.val('cash_target_'+str(block),'eth_getBlockByNumber',[hex(block),False])
 if target['parentHash']!=parent['hash']:raise ValueError('ancestry')
 for a in (CASH,CALLER):
  if c.val('unused_'+a[-4:],'eth_getCode',[a,parent['number']])!='0x':raise ValueError('research address occupied')
 reserve=max(1,int(target['baseFeePerGas'],16)*800000)
 env={'from':CALLER,'to':CASH,'input':'0x'+ids['environment()'],'gas':hex(200000),'gasPrice':'0x0'}
 data=encode(ids['execute(uint256,uint24,bool,uint256,uint256)'],row['principal_raw'],row['fee'],int(row['reverse']),reserve,1)
 trade={'from':CALLER,'to':CASH,'input':data,'gas':hex(5000000),'gasPrice':'0x0'}
 overrides={'number':target['number'],'time':target['timestamp'],'gasLimit':target['gasLimit'],'baseFeePerGas':target['baseFeePerGas'],'feeRecipient':target['miner'],'prevRandao':target['mixHash']}
 result=c.val('cash_'+str(block)+'_'+str(row['fee'])+'_'+str(row['principal_raw']),'eth_simulateV1',[{'blockStateCalls':[{'blockOverrides':overrides,'stateOverrides':{CASH:{'code':code}},'calls':[env,trade,env]}],'validation':False,'traceTransfers':False},parent['number']])
 calls=result[0]['calls'];before=words(calls[0]['returnData'],9);after=words(calls[2]['returnData'],9)
 if calls[0]['status']!='0x1' or calls[2]['status']!='0x1' or before[:3]!=[1,block,int(target['timestamp'],16)] or before[3:]!=[0]*6:raise ValueError('cash environment')
 t=calls[1];d={'target_block':block,'target_hash':target['hash'],'target_timestamp':int(target['timestamp'],16),'selection':row,'status':t['status'],'gas_used':int(t['gasUsed'],16),'explicit_bid_wei':0,'upfront_gas_funding_not_removed':True}
 if t['status']!='0x1':
  if before!=after:raise ValueError('rollback mismatch')
  d.update(error=t.get('error'),rollback_verified=True);return d
 loan,gross,rescost,paid,native=words(t['returnData'],5)
 if loan!=row['principal_raw'] or gross-rescost!=paid or paid<1 or native!=reserve or after[3:7]!=[0]*4 or after[7:]!=[native,paid]:raise ValueError('cash accounting')
 flows=[]
 for log in t.get('logs',[]):
  topics=log.get('topics',[])
  if log.get('address','').lower()==USDC and len(topics)==3 and topics[0].lower()==TRANSFER:flows.append(('0x'+topics[1][-40:].lower(),'0x'+topics[2][-40:].lower(),int(log['data'],16)))
 incoming=sum(x for a,b,x in flows if a==MORPHO and b==CASH);repayment=sum(x for a,b,x in flows if a==CASH and b==MORPHO);payout=sum(x for a,b,x in flows if a==CASH and b==CALLER)
 if (incoming,repayment,payout)!=(loan,loan,paid):raise ValueError('repayment/payout transfers')
 d.update(gross_raw=gross,reserve_cost_raw=rescost,paid_cash_raw=paid,native_reserve_wei=native,base_fee_cost_wei=d['gas_used']*int(target['baseFeePerGas'],16),cash_transfer_reconciled=True)
 d['reserve_covers_base_fee']=native>=d['base_fee_cost_wei'];return d

def run():
 OUT.mkdir(exist_ok=True);states=json.loads((BASE/'selected_states.json').read_text())
 plan={'new_execution':True,'selection':'6 evenly spaced chronological block ranks among all crvUSD->WETH swaps on each Sep2/9/16 day; 3 prior failed controls and July discovery calibration; one duplicate collapsed','counts':'21 distinct states; 18 systematic September states; not a complete daily opportunity census or prospective holdout','sizes_USDC':SIZES,'fees':[100,500],'both_directions':True,'quote_state':'actual historical block-end state and timestamp; next-block timing is tested only for cash candidates','quote_method':'Uniswap QuoterV2 and Curve get_dy with fees; no real transfers; not validated profit','cash_selection':'mandatory July 20k fee500 forward calibration, then first chronological September state with a positive gross quote (best gross within that state), then same candidate delayed one extra actual block','max_quote_states':21,'max_cash_simulations':3,'request_cap':100,'seconds_cap':1000,'competitive_bid':0,'reserved_Oct3_9_untouched':True,'only_code_overrides_at_unused_research_addresses':True,'transactions_sent':0}
 save('PLAN.json',plan);save('SELECTED_BEFORE_QUOTES.json',states);c=Client();out={'plan':plan,'quotes':[],'cash_cases':[],'started_utc':utc()}
 try:
  compiled=build();qcode,qids=compiled['QuoteStudy'];ccode,cids=compiled['CashStudy']
  if c.val('chain','eth_chainId',[])!='0x1':raise ValueError('wrong chain')
  for s in states:
   try:
    h=c.val('header_'+str(s['block']),'eth_getBlockByNumber',[hex(s['block']),False])
    if h['hash']!=s['hash'] or int(h['number'],16)!=s['block']:raise ValueError('canonical hash changed')
    if c.val('unused_quote_'+str(s['block']),'eth_getCode',[QUOTE,h['number']])!='0x':raise ValueError('quote address occupied')
    raw=c.val('quotes_'+str(s['block']),'eth_call',[{'from':CALLER,'to':QUOTE,'data':'0x'+qids['quotes()'],'gas':hex(25000000)},h['number'],{QUOTE:{'code':qcode}}])
    rows=decode_quotes(raw,h);rec={'state':s,'header':{k:h[k] for k in ('number','hash','timestamp','baseFeePerGas','gasLimit','gasUsed')},'rows':rows,'positive_gross_rows':sum(r['quote_success'] and r['gross_raw']>0 for r in rows)}
    out['quotes'].append(rec);print(json.dumps({'block':s['block'],'positive_gross_rows':rec['positive_gross_rows'],'valid_quotes':sum(r['quote_success'] for r in rows),'best_gross_raw':max((r['gross_raw'] for r in rows if r['quote_success']),default=None)}),flush=True)
   except Exception as e:
    out['quotes'].append({'state':s,'unavailable':repr(e)});print('QUOTE UNAVAILABLE',repr(e),flush=True)
    if c.stop:raise
   save('SUMMARY.json',out)
  cal=next((r for r in out['quotes'] if r['state']['role']=='known_positive_calibration' and 'rows' in r),None)
  jobs=[]
  if cal:
   row=next(r for r in cal['rows'] if r['principal_raw']==20000*10**6 and r['fee']==500 and not r['reverse']);jobs.append((cal,row,1))
  candidates=sorted([r for r in out['quotes'] if r['state']['role']!='known_positive_calibration' and 'rows' in r and r['positive_gross_rows']>0],key=lambda r:r['state']['block'])
  if candidates:
   rec=candidates[0];row=max((r for r in rec['rows'] if r['quote_success']),key=lambda r:r['gross_raw']);jobs.extend([(rec,row,1),(rec,row,2)])
  save('CASH_SELECTION_BEFORE_SIMULATION.json',[{'state':r['state'],'row':row,'offset':off} for r,row,off in jobs])
  for rec,row,offset in jobs:
   try:case=simulate(c,rec['header'],row,ccode,cids,offset);out['cash_cases'].append(case);print(json.dumps(case),flush=True)
   except Exception as e:
    out['cash_cases'].append({'state':rec['state'],'offset':offset,'unavailable':repr(e)})
    if c.stop:raise
   save('SUMMARY.json',out)
 except Exception as e:out['exception']=repr(e)
 out.update(completed_utc=utc(),rpc_requests=c.count,provider_stop=c.stop,transactions_sent=0,actual_capture_measured=False);save('SUMMARY.json',out)
 print(json.dumps({k:v for k,v in out.items() if k not in ('quotes','cash_cases','plan')}),flush=True)

if __name__=='__main__':run()
