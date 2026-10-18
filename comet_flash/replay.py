"""Full, read-only historical EVM cash closure for the observed Compound III buy.
Aave USDC flashLoanSimple -> Comet.buyCollateral -> real Uniswap V3 swap
-> Aave repayment incl premium -> native USDC delivered to a blank beneficiary.
Only an unused research contract's CODE is overridden. Never deploys/trades.
"""
import datetime as dt,hashlib,json,time,urllib.request,urllib.error,traceback
from pathlib import Path
from Crypto.Hash import keccak
from solcx import install_solc,compile_standard

OUT=Path("flash_evidence");OUT.mkdir(exist_ok=True)
RPC="https://rpc-eth.blockmachine.io"
PROBE="0x00000000000000000000000000000000dead8842"
BENEF="0x00000000000000000000000000000000dead8821"
AAVE="0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"
COMET="0xc3d688b66703497daa19211eedff47f25384cdc3"
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WETH="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
SWAP="0xe592427a0aece92de3edee1f18e0157c05861564"
BLOCK=25984761
ORIGINAL_TX="0x9a710e9b980957f1418a3578d6601b5e85e4ef0784c42e97cdbf7fe864bd9a4a"
AMOUNT=9346567826
OBS_COLL=4138078068736368148
TRANSFER="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def k(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return h.hexdigest()
def pad(a):return format(int(a),'064x')
def method(s,*args):return "0x"+k(s)[:8]+''.join(pad(a) for a in args)
def words(s):
 if not isinstance(s,str) or not s.startswith('0x') or (len(s)-2)%64:raise ValueError('Malformed ABI uint array')
 return [int(s[x:x+64],16) for x in range(2,len(s),64)]
def save(path,obj):
 file=OUT/path;file.parent.mkdir(parents=True,exist_ok=True)
 file.write_text(json.dumps(obj,indent=2,default=str)+'\n')
def log_sig(l):return l.get('topics',[''])[0].lower()
class Reader:
 def __init__(self):self.n=0;self.last_heavy=-1e8;self.denied=False;self.cache={}
 def call(self,label,name,params):
  if name not in ('eth_chainId','eth_getCode','eth_getBlockByNumber','eth_getTransactionReceipt','eth_call','eth_simulateV1'):raise ValueError('Unapproved network method')
  if self.denied:raise RuntimeError('Provider denied; stopping')
  key=json.dumps([name,params],sort_keys=True)
  if key in self.cache:return self.cache[key]
  if self.n>=45:raise RuntimeError('Provider budget exceeded')
  if name=='eth_simulateV1':
   time.sleep(max(0,70-(time.monotonic()-self.last_heavy)))
   self.last_heavy=time.monotonic()
  else:time.sleep(1.3)
  self.n+=1;raw=b'';meta={'label':label,'id':self.n,'method':name,'status':'UNKNOWN'}
  try:
   payload={'jsonrpc':'2.0','id':self.n,'method':name,'params':params}
   request=urllib.request.Request(RPC,data=json.dumps(payload).encode(),
      headers={'Content-Type':'application/json','User-Agent':'QT-Stage1-ReadOnly-FlashSimulation/1'})
   with urllib.request.urlopen(request,timeout=80) as resp:
    meta['http_status']=resp.status;raw=resp.read(7_000_001)
   if len(raw)>7_000_000:raise ValueError('RPC body exceeds cap')
   answer=json.loads(raw)
   if answer.get('error'):
    meta['rpc_error']=answer['error']
    message=str(answer['error']).lower()
    if any(term in message for term in ('client adjustable limit','unauthorized','rate limit','access denied')):self.denied=True
    raise RuntimeError(str(answer['error'])[:400])
   meta['status']='OK';self.cache[key]=answer['result'];return answer['result']
  except urllib.error.HTTPError as e:
   meta['error']=str(e);raw=e.read(100000)
   if e.code in (401,403,429):self.denied=True
   raise
  except Exception as e:meta['error']=repr(e);raise
  finally:
   meta['sha256']=hashlib.sha256(raw).hexdigest();meta['response_bytes']=len(raw)
   (OUT/'raw').mkdir(exist_ok=True)
   (OUT/f'raw/{self.n:04d}.body').write_bytes(raw)
   save(f'raw/{self.n:04d}.json',meta)

def compile_contract():
 s=Path('comet_flash/CometCashProbe.sol').read_text()
 cfg={'language':'Solidity','sources':{'CometCashProbe.sol':{'content':s}},
  'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun',
    'outputSelection':{'*':{'*':['abi','evm.deployedBytecode.object']}}}}
 save('compiler_input.json',cfg)
 install_solc('0.8.24');build=compile_standard(cfg,solc_version='0.8.24')
 save('compiler_output.json',build)
 c=build['contracts']['CometCashProbe.sol']['CometCashProbe']
 runtime='0x'+c['evm']['deployedBytecode']['object']
 if len(runtime)//2-1>24576:raise ValueError('EIP-170 code size exceeded')
 names={x['name'] for x in c['abi'] if x.get('type')=='function'}
 if not {'env','run','executeOperation'}<=names:raise ValueError('Missing relevant methods')
 save('BUILD.json',{'source_sha256':hashlib.sha256(s.encode()).hexdigest(),
      'runtime_sha256':hashlib.sha256(bytes.fromhex(runtime[2:])).hexdigest(),'runtime_length':len(runtime)//2-1,
      'compiler':'0.8.24','override_only_unused_research_code':True})
 return runtime

def sourced_case():
 c=json.loads(Path('input_comet/REPORT.json').read_text())
 matches=[x for x in c['choices'] if x['tx']==ORIGINAL_TX and x['base_raw']==str(AMOUNT) and x['coll_raw']==str(OBS_COLL)]
 if len(matches)!=1 or not matches[0].get('receipt_verified'):raise ValueError('Frozen actual Compound purchase not present')
 if not any(q.get('gross_margin_base_raw')=='406016571' and q.get('fee')==500 for q in matches[0]['quote_cash_out']):
  raise ValueError('Historical price observation not preserved')
 return matches[0]

def header(r,n):
 h=r.call('actual_header','eth_getBlockByNumber',[hex(n),False])
 if int(h['number'],16)!=n:raise ValueError('Actual block number mismatch')
 return h
def pending_codes(r):
 for a in [PROBE,BENEF]:
  if r.call('research_empty_contract','eth_getCode',[a,hex(BLOCK-1)])!='0x':raise ValueError('Nonempty probe or beneficiary code')
 for a in [AAVE,COMET,USDC,WETH,SWAP]:
  if len(r.call('deployed_contract','eth_getCode',[a,hex(BLOCK-1)]))<10:raise ValueError('Production code missing')

def sim(r,b,fee,code,label):
 parent=header(r,b-1);h=header(r,b)
 if h['parentHash'].lower()!=parent['hash'].lower():raise ValueError('Header ancestry mismatch')
 def call(calldata,gas):
  return {'from':BENEF,'to':PROBE,'input':calldata,'gas':hex(gas),'gasPrice':'0x0'}
 pre=call(method('env()'),200000)
 action=call(method('run(uint256,uint24,uint256)',AMOUNT,fee,1_000_000),4500000)
 calls=[pre,action,pre]
 bo={'number':h['number'],'time':h['timestamp'],'gasLimit':h['gasLimit'],
     'baseFeePerGas':h['baseFeePerGas'],'feeRecipient':h['miner'],'prevRandao':h['mixHash']}
 params={'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{PROBE:{'code':code}},'calls':calls}],
     'validation':False,'traceTransfers':False}
 result=r.call(label,'eth_simulateV1',[params,parent['number']])
 save(f'cases/{label}.json',{'parent':parent,'target_header':h,'simulation':result,
       'expected_buy':ORIGINAL_TX,'borrowed_USDC_raw':str(AMOUNT),'fee_tier':fee})
 cs=result[0]['calls']
 if len(cs)!=3:raise ValueError('Unexpected simulation call count')
 before,trade,after=cs
 if before.get('status')!='0x1' or after.get('status')!='0x1':raise ValueError('Broken environment controls')
 old=words(before['returnData']);new=words(after['returnData'])
 if len(old)!=9 or len(new)!=9:raise ValueError('Wrong env ABI')
 expected=(1,b,int(h['timestamp'],16),int(h['baseFeePerGas'],16))
 if tuple(old[:4])!=expected or tuple(new[:4])!=expected:raise ValueError('Historical EVM environment invalid')
 if old[4]!=0 or old[5]!=0:raise ValueError('Probe already had inventory')
 if old[7]!=new[7] or old[8]!=new[8]:raise ValueError('Noncash inventory or native balance changed')
 rec={'id':label,'block':b,'fee':fee,'canonical_header_verified':True,
     'zero_initial_probe_USDC_WETH':True,'status':trade.get('status'),'gas_used':int(trade.get('gasUsed','0x0'),16),
     'basefee_gas_cost_wei':str(int(trade.get('gasUsed','0x0'),16)*old[3]),
     'beneficiary_USDC_delta_raw':str(new[6]-old[6]),'probe_USDC_end':str(new[4]),'probe_WETH_end':str(new[5]),
     'execution_proves_competitive_inclusion':False}
 if trade.get('status')=='0x1':
  payout=words(trade['returnData'])
  if len(payout)!=1 or payout[0]!=new[6]-old[6] or payout[0]<1_000_000:raise ValueError('Payout mismatch')
  if new[4]!=0 or new[5]!=0:raise ValueError('Unconverted residual token balances')
  dest='0x'+BENEF[2:].lower().zfill(64)
  logs=trade.get('logs',[])
  transfer=sum(int(l['data'],16) for l in logs if l['address'].lower()==USDC and log_sig(l)==TRANSFER
     and len(l['topics'])==3 and l['topics'][2].lower()==dest)
  if transfer!=payout[0]:raise ValueError('Cash transfer not proven')
  rec.update(actual_cash_payout_USDC_raw=str(payout[0]),cash_transfer_verified=True,
             flash_loan_repayment_status='Transaction succeeded; Aave pulled principal+fee in same call')
 else:
  rec.update(error=trade.get('error'),no_cash_payout=True,rollback_verified=(new[4:]==old[4:]))
  if not rec['rollback_verified']:raise ValueError('Rejected execution modified state')
 return rec

def main():
 report={'run_type':'Historical read-only Aave flash+Comet buy+Uniswap real USDC payout',
    'source_case':ORIGINAL_TX,'created_real_trade':False,'new_income_proven':False,
    'zero_principal_start':True,'no_signing_broadcast_keys_or_production_overrides':True,
    'limits':'4 distinct reset-state historical code-only simulations; up to 45 RPC reads; 70 second heavy pacing',
    'observations':[],'complete':False}
 save('REPORT.json',report);r=Reader()
 try:
  sourced_case()
  if int(r.call('chainid','eth_chainId',[]),16)!=1:raise ValueError('Wrong chain')
  receipt=r.call('original_buy_receipt','eth_getTransactionReceipt',[ORIGINAL_TX])
  if not receipt or receipt['status']!='0x1' or int(receipt['blockNumber'],16)!=BLOCK:raise ValueError('Original receipt anchor false')
  report['original_actual_buyer_gas_wei']=str(int(receipt['gasUsed'],16)*int(receipt['effectiveGasPrice'],16))
  pending_codes(r)
  for sig in ('getReserves()','targetReserves()','getCollateralReserves(address)'):
   p=(['0x'+WETH[2:].zfill(64)] if 'address' in sig else [])
   dat='0x'+k(sig)[:8]+''.join(x[2:] for x in p)
   raw=r.call('parent_Comet_state','eth_call',[{'to':COMET,'data':dat},hex(BLOCK-1)])
   report[sig]=str(words(raw)[0])
  save('REPORT.json',report)
  runtime=compile_contract()
  for block,fee in [(BLOCK,500),(BLOCK,3000),(BLOCK+1,500),(BLOCK-1,500)]:
   label=f'block_{block}_fee_{fee}'
   try:res=sim(r,block,fee,runtime,label)
   except Exception as e:res={'id':label,'exception':repr(e)}
   report['observations'].append(res);save('REPORT.json',report)
   if r.denied:raise RuntimeError('Provider refused further simulations')
  report['complete']=len(report['observations'])==4 and all('status' in q for q in report['observations'])
 except Exception as e:report['fatal']=repr(e);report['traceback']=traceback.format_exc()
 report['requests']=r.n;report['provider_denied']=r.denied
 report['verified_positive_cash_cases']=sum(bool(x.get('cash_transfer_verified')) for x in report['observations'])
 save('REPORT.json',report)
 print(json.dumps({'complete':report['complete'],'positive_cash_cases':report['verified_positive_cash_cases'],
    'requests':r.n,'cases':[{k:x.get(k) for k in ('id','status','actual_cash_payout_USDC_raw','error','exception')} for x in report['observations']],
    'fatal':report.get('fatal')},indent=2),flush=True)
 if not report['complete']:raise SystemExit('Research test incomplete; failures preserved, not zero profit')
if __name__=='__main__':main()
