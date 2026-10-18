"""Zero-principal, code-only, historical EVM test for GHO GSM apparent cash edge.
No live contract deployment, keys, signing, sending, state/storage/balance/oracle editing.
Initial USDC comes ONLY from genuine Morpho Blue zero-fee flashLoan.
"""
import json,datetime,time,hashlib,urllib.request,urllib.error,traceback
from pathlib import Path
from Crypto.Hash import keccak
from solcx import compile_standard,install_solc

OUT=Path('gho_cash_evidence');OUT.mkdir(exist_ok=True)
RPC='https://rpc-eth.blockmachine.io'
ETH=1
PROBE='0x000000000000000000000000000000000000a11c'
BEN='0x000000000000000000000000000000000000babe'
GSM='0x3a3868898305f04bec7fea77becff04c13444112'
MORPHO='0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb'
USDC='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
GHO='0x40d16fc0246ad3160ccc09b8d0d3a2cd28ae6c2f'
STATES=[{'name':'sep30','block':26090422,'trials':[(100,100),(1000,100)]},
        {'name':'oct17','block':26220131,'trials':[(100,500),(1000,500)]}]
N=0;HEAVY=0;STOP=False;LAST=-99999999999;START=time.monotonic()
def save(name,obj):
 path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,default=str)+'\n')
def khash(src):
 k=keccak.new(digest_bits=256);k.update(src.encode());return '0x'+k.hexdigest()[:8]
def word(n):return format(n,'064x')
def decode_words(x,n):
 if not isinstance(x,str) or not x.startswith('0x') or len(x)<2+64*n:raise ValueError('Short/missing ABI result')
 return [int(x[2+64*i:2+64*(i+1)],16) for i in range(n)]
def rpc(label,method,params):
 global N,HEAVY,STOP,LAST
 if STOP:raise RuntimeError('Provider denied before this call')
 if N>=55 or time.monotonic()-START>1480:raise RuntimeError('Bounded research request/time limit')
 if method not in {'eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call','eth_simulateV1'}:raise ValueError('Read only method')
 if method=='eth_simulateV1':
  time.sleep(max(0,70-(time.monotonic()-LAST)))
  LAST=time.monotonic();HEAVY+=1
  if HEAVY>8:raise RuntimeError('Maximum heavy simulations')
 else:time.sleep(.4)
 N+=1;payload={'jsonrpc':'2.0','id':N,'method':method,'params':params}
 body=b'';record={'name':label,'method':method,'requested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'params_digest':hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest()}
 try:
  req=urllib.request.Request(RPC,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','User-Agent':'QT-Stage1-CodeOnly-EVM'})
  with urllib.request.urlopen(req,timeout=65 if method=='eth_simulateV1' else 22) as f:
   body=f.read(7_000_001);record['http_status']=f.status
  if len(body)>7_000_000:raise ValueError('RPC evidence body too large')
  resp=json.loads(body)
  if resp.get('error'):
   record['rpc_error']=resp['error'];msg=str(resp['error']).lower()
   if any(z in msg for z in ('access denied','rate limit','client adjustable limit','unauthorized','missing trie node')):
    STOP=True
   raise RuntimeError(str(resp['error'])[:450])
  if 'result' not in resp:raise ValueError('Missing result')
  record['status']='OK';return resp['result']
 except urllib.error.HTTPError as ex:
  record.update(http_status=ex.code,error=str(ex));body=ex.read(100000)
  if ex.code in (401,403,429):STOP=True
  raise
 except Exception as ex:record['error']=repr(ex);raise
 finally:
  record['raw_sha256']=hashlib.sha256(body).hexdigest()
  record['bytes']=len(body)
  save(f'requests/{N:03d}.json',record)
  raw=(OUT/f'raw/{N:03d}.body');raw.parent.mkdir(parents=True,exist_ok=True);raw.write_bytes(body)
def compile_probe():
 source=Path('gho_cash/GhoCashProbe.sol').read_text()
 install_solc('0.8.24')
 inp={'language':'Solidity','sources':{'GhoCashProbe.sol':{'content':source}},
      'settings':{'optimizer':{'enabled':True,'runs':200},
                  'outputSelection':{'*':{'*':['evm.deployedBytecode.object','abi']}}}}
 compiled=compile_standard(inp,solc_version='0.8.24')
 save('compiler_settings.json',inp['settings'])
 code=compiled['contracts']['GhoCashProbe.sol']['GhoCashProbe']['evm']['deployedBytecode']['object']
 if not code or len(code)>45000:raise ValueError('Unexpected runtime size')
 runtime='0x'+code
 save('compiler_hashes.json',{'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
   'runtime_sha256':hashlib.sha256(bytes.fromhex(code)).hexdigest(),
   'solc_version':'0.8.24','runtime_bytes':len(code)//2})
 return runtime
def read_view(to,signature,h,basefee):
 return rpc(signature,'eth_call',[{'to':to,'data':khash(signature),'gasPrice':hex(basefee)},hex(h)])
def state_calls(header,code,amount,fee):
 env=khash('env()')
 trial=khash('run(uint256,uint24)')+word(amount)+word(fee)
 def tx(data,gas):
  return {'from':BEN,'to':PROBE,'input':data,'gas':hex(gas),'gasPrice':'0x0'}
 parent=int(header['number'],16)-1
 # Actual block header, no fabricated timestamp, oracle or gas capacity
 block_overrides={'number':header['number'],'time':header['timestamp'],'gasLimit':header['gasLimit'],
  'baseFeePerGas':header['baseFeePerGas'],'feeRecipient':header['miner'],
  'prevRandao':header['mixHash']}
 calls=[tx(env,180000),tx(trial,7000000),tx(env,180000)]
 params={'blockStateCalls':[{'blockOverrides':block_overrides,'stateOverrides':{PROBE:{'code':code}},
      'calls':calls}],'validation':False,'traceTransfers':False}
 return params,hex(parent)
def audit_sim(resp,h,amount,fee):
 out={'amount_usdc':amount//10**6,'fee_tier':fee,'status':'UNKNOWN',
      'synthetic_caller_gas_price_zero':True,'competitive_bid_wei':'0'}
 if not isinstance(resp,list) or len(resp)!=1:raise ValueError('Bad simulation envelope')
 calls=resp[0].get('calls',[])
 if len(calls)!=3:raise ValueError('Expected exactly 3 calls')
 for k in (0,2):
  if calls[k].get('status')!='0x1':raise ValueError('Environment probe reverted')
 e=decode_words(calls[0]['returnData'],10)
 z=decode_words(calls[2]['returnData'],10)
 target=(1,int(h['number'],16),int(h['timestamp'],16),int(h['baseFeePerGas'],16))
 if tuple(e[:4])!=target or tuple(z[:4])!=target:raise ValueError('Wrong historical environment')
 if any(e[4:8]):raise ValueError('Unfunded research wallet requirement violated')
 out.update(environment_verified=True,initial_token_balances=e[4:8],initial_gsm_asset_balance=e[8],
             initial_gsm_gho_balance=e[9],gas_used=int(calls[1].get('gasUsed','0x0'),16))
 trade=calls[1];out['status']=trade.get('status')
 out['revert_error']=trade.get('error')
 if out['status']=='0x1':
  paid=decode_words(trade.get('returnData','0x'),1)[0]
  if z[4] or z[5] or z[7]:raise ValueError('Residual balance at test executor')
  if z[6]-e[6]!=paid or paid==0:raise ValueError('Final beneficiary USDC transfer missing')
  if z[8]-e[8]!=amount:raise ValueError('GSM did not receive exactly borrowed USDC')
  out.update(terminal_usdc_profit_units=str(paid),gas_cost_wei=str(out['gas_used']*target[3]),
             gas_cost_usdc_unvalued=True,
             output_transfer_verified=True,flash_principal_repayment_verified=True,
             profitable_before_gas=paid>0)
 else:
  if z[4:8]!=e[4:8]:raise ValueError('EVM revert state not rolled back')
  out['rollback_verified']=True
 return out
def main():
 report={'scope':'Read-only real historical EVM Morpho USDC flash -> current Aave GHO GSM -> UniV3 USDC -> repay',
   'tests':[],'finished':False,'zero_initial_principal_required':True,
   'no_production_state_balance_or_oracle_overrides':True,'no_signing_or_broadcast':True,
   'disclaimer':['GSM quotes without actual Reserve use are not profits',
        'Even successful simulated payout is NOT proof of builder inclusion or live capture',
        'Synthetic zero gas price requires pricing actual gas and upfront ETH',
        'Chosen states/tokens/routes are retrospective development, not prospective validation']}
 save('REPORT.json',report)
 try:
  runtime=compile_probe()
  if int(rpc('eth_chainId','eth_chainId',[]),16)!=1:raise ValueError('Wrong chain')
  for scenario in STATES:
   h=rpc('historical_header','eth_getBlockByNumber',[hex(scenario['block']),False])
   parent=rpc('historical_parent','eth_getBlockByNumber',[hex(scenario['block']-1),False])
   if h['parentHash']!=parent['hash']:raise ValueError('Mismatched parent')
   c=rpc('unused_contract_address','eth_getCode',[PROBE,parent['number']])
   if c!='0x':raise ValueError('Research executor already deployed at target address')
   for addr in (MORPHO,GSM,USDC,GHO):
    if rpc('verified_deployed_code','eth_getCode',[addr,parent['number']])=='0x':
     raise ValueError('Missing genuine production contract '+addr)
   snapshot={'name':scenario['name'],'block':scenario['block'],'timestamp':h['timestamp'],
     'canonical_parent':parent['hash'],'reserve_views':{},'alternatives':[]}
   report['tests'].append(snapshot)
   basefee=int(h['baseFeePerGas'],16)
   for sig in ('getAvailableLiquidity()','getAvailableUnderlyingExposure()','getLimit()','getUsed()','getIsFrozen()','getIsSeized()','canSwap()'):
    try:snapshot['reserve_views'][sig]=str(decode_words(read_view(GSM,sig,scenario['block'],basefee),1)[0])
    except Exception as exc:snapshot['reserve_views'][sig+'_error']=repr(exc)
   save('REPORT.json',report)
   for value,fee in scenario['trials']:
    item={'amount_usdc':value,'fee':fee,'economic_status':'PENDING'}
    snapshot['alternatives'].append(item);save('REPORT.json',report)
    try:
     params,parent_ref=state_calls(h,runtime,value*10**6,fee)
     result=rpc('historical_cash_replay_'+scenario['name']+'_'+str(value)+'_'+str(fee),'eth_simulateV1',[params,parent_ref])
     outcome=audit_sim(result,h,value*10**6,fee)
     item.update(outcome,economic_status='SETTLED_CASH_IN_SIMULATION' if outcome['status']=='0x1' else 'ONCHAIN_REVERT')
    except Exception as exc:item.update(economic_status='RPC_OR_ACCOUNTING_FAILURE',error=repr(exc))
    save('REPORT.json',report)
    if STOP:raise RuntimeError('Provider refusal/limit, stop without retry')
   check=rpc('block_hash_recheck','eth_getBlockByNumber',[h['number'],False])
   if check['hash']!=h['hash']:raise ValueError('Canonical historical block changed')
  report['finished']=True
 except Exception as exc:report['exception']=repr(exc);report['traceback']=traceback.format_exc()
 report['requests']=N;report['heavy_simulations']=HEAVY;report['provider_stopped']=STOP
 save('REPORT.json',report)
 print(json.dumps({'finished':report['finished'],'requests':N,'heavy':HEAVY,
   'results':[{'name':x['name'],'reserve':x['reserve_views'],
       'alternatives':[{'size':a['amount_usdc'],'fee':a['fee'],
                       'state':a.get('economic_status'),'profit':a.get('terminal_usdc_profit_units'),
                       'error':a.get('error') or a.get('revert_error')} for a in x['alternatives']]} for x in report['tests']],
    'exception':report.get('exception')},indent=2),flush=True)
 if not report['finished']:raise SystemExit('Historical EVM incomplete: preserve raw evidence, no profit claim')
if __name__=='__main__':main()
