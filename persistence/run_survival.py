"""Read-only fixed-route historical survival test. Each delay resets to canonical state.
No signing, broadcasting, account funding or production balance/storage/oracle overrides.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from Crypto.Hash import keccak
from eth_abi import encode, decode
import solcx
RPC='https://rpc-eth.blockmachine.io'
SOURCE='https://raw.githubusercontent.com/zhangsherwin-bit/qt-rpc-sandbox/75b67d7efbd6c96920872075f3c093f0c5ecb842/standalone/ConversionProbe.sol'
SOURCE_SHA='260aa95cc1dbb42b29b6c3d9c3d544d99428037e9d3bc814c6be25dffb0eff9b'
RUNTIME_SHA='d09a975447d21d41e9a459bdae81d93e4f145f390695d922723b3c388d1d342e'
PROBE='0x00000000000000000000000000000000DeaD7714'
CALLER='0x00000000000000000000000000000000DeaD7712'
WINNER_BLOCK=25643399
WINNER_HASH='0x61212afaf0084a1ef50a718ef4b49032bc2f979eadc465f574ecab626d90100a'
OFFSETS=(1,2,4,8,16,32,64)
PRINCIPAL,RESERVE,MINIMUM=20_000*10**6,200_000_000_000_000,10**6
ALLOWED={'eth_chainId','eth_getBlockByNumber','eth_getCode','eth_getBalance','eth_simulateV1'}
OUT=Path('evidence');COUNT=0;STOP=False;LAST=0.0;START=time.monotonic()
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def save(name,value):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2),encoding='utf-8')
def selector(sig):
 h=keccak.new(digest_bits=256);h.update(sig.encode());return h.digest()[:4]
def calldata(sig,types=(),vals=()):return '0x'+(selector(sig)+encode(list(types),list(vals))).hex()
def rpc(name,method,params):
 global COUNT,STOP,LAST
 if method not in ALLOWED:raise ValueError('non-read method rejected')
 if STOP or COUNT>=60 or time.monotonic()-START>1050:raise RuntimeError('budget/access stop')
 pause=70 if method=='eth_simulateV1' else 0.8;time.sleep(max(0,pause-(time.monotonic()-LAST)))
 COUNT+=1;payload={'jsonrpc':'2.0','id':COUNT,'method':method,'params':params};rec={'name':name,'url':RPC,'payload':payload,'started_utc':utc()};body=b'';response=None
 try:
  req=urllib.request.Request(RPC,json.dumps(payload).encode(),{'Content-Type':'application/json','User-Agent':'QT-ReadOnly-Fixed-Route-Survival/1'})
  with urllib.request.urlopen(req,timeout=55) as r:rec['http_status']=r.status;body=r.read(12_000_001)
  if len(body)>12_000_000:raise ValueError('response cap')
  response=json.loads(body);rec['status']='RPC_ERROR' if 'error' in response else 'OK'
 except urllib.error.HTTPError as e:
  body=e.read(100_000);rec.update(status='HTTP_ERROR',http_status=e.code,error=str(e))
  if e.code in (401,403,429):STOP=True
 except Exception as e:rec.update(status='UNAVAILABLE',error=repr(e))
 LAST=time.monotonic();rec.update(completed_utc=utc(),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body));(OUT/'raw').mkdir(parents=True,exist_ok=True);(OUT/'raw'/f'{COUNT:04d}.body').write_bytes(body);save(f'raw/{COUNT:04d}.json',rec)
 if STOP:raise RuntimeError('access/rate refusal; no retries or endpoint switching')
 return response
def val(*args):
 r=rpc(*args)
 if not isinstance(r,dict) or 'result' not in r or r['result'] is None:raise ValueError('unavailable RPC: '+str(r)[:500])
 return r['result']
def build():
 req=urllib.request.Request(SOURCE,headers={'User-Agent':'QT-ReadOnly-Research/1'})
 with urllib.request.urlopen(req,timeout=30) as r:body=r.read(60_001)
 if hashlib.sha256(body).hexdigest()!=SOURCE_SHA:raise ValueError('pinned source hash mismatch')
 (OUT/'ConversionProbe.sol').write_bytes(body)
 inp={'language':'Solidity','sources':{'C.sol':{'content':body.decode()}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.methodIdentifiers','evm.deployedBytecode.object']}}}}
 solcx.install_solc('0.8.34');out=solcx.compile_standard(inp,solc_version='0.8.34');save('compiler_input.json',inp);save('compiler_output.json',out)
 c=out['contracts']['C.sol']['ConversionProbe'];raw=c['evm']['deployedBytecode']['object']
 if hashlib.sha256(bytes.fromhex(raw)).hexdigest()!=RUNTIME_SHA:raise ValueError('frozen runtime mismatch')
 if c['evm']['methodIdentifiers']['execute(uint256,uint256,uint256)']!=selector('execute(uint256,uint256,uint256)').hex():raise ValueError('ABI mismatch')
 (OUT/'runtime.hex').write_text('0x'+raw);return '0x'+raw
def check_success(calls,header):
 before=decode(['uint256']*9,bytes.fromhex(calls[0]['returnData'][2:]));assert calls[0]['status']=='0x1' and before[:3]==(1,int(header['number'],16),int(header['timestamp'],16));assert before[3:]==(0,0,0,0,0,0),'executor or caller starts funded'
 trade=calls[1];out={'status':trade.get('status'),'gas_used':int(trade['gasUsed'],16),'error':trade.get('error'),'environment_verified':True};after=decode(['uint256']*9,bytes.fromhex(calls[2]['returnData'][2:]));assert calls[2]['status']=='0x1'
 if trade.get('status')!='0x1':
  assert after==before,'failed candidate did not roll back';out['rollback_verified']=True;return out
 v=decode(['uint256']*6,bytes.fromhex(trade['returnData'][2:]));assert after[:3]==before[:3] and after[3:7]==(0,0,0,0);assert v[0]==PRINCIPAL and v[1]-v[2]==v[3] and v[3]>=MINIMUM;assert after[7]-before[7]==v[4]==RESERVE and after[8]-before[8]==v[3]
 out['values']={k:str(n) for k,n in zip(('loan_repaid_USDC_raw','gross_profit_USDC_raw','native_reserve_cost_USDC_raw','cash_paid_USDC_raw','native_reserve_paid_wei','frxUSD_redeemed_raw'),v)};burn=out['gas_used']*int(header['baseFeePerGas'],16);out.update(base_fee_cost_wei=str(burn),reserve_covers_base_fee=RESERVE>=burn,unvalued_native_after_base_fee_wei=str(RESERVE-burn),cash_and_repayment_verified=True);return out
def main():
 OUT.mkdir(exist_ok=True);s={'started_utc':utc(),'scope':'fixed route and 20k USDC; seven alternative states of ONE previously selected episode; no recurrence or capture claim','source_url':SOURCE,'source_sha256':SOURCE_SHA,'expected_runtime_sha256':RUNTIME_SHA,'offsets':list(OFFSETS),'principal_raw':str(PRINCIPAL),'native_reserve_wei':str(RESERVE),'minimum_cash_raw':str(MINIMUM),'explicit_competitive_bid_wei':'0','zero_gas_price_in_simulation':True,'transactions_sent':0,'live_profit':False,'cases':[]};save('PLAN.json',{**s,'note':'Offsets, source and size frozen before new outcome calls; +1 is a reproduction control.'})
 try:
  runtime=build();s['compiled_runtime_verified']=True;assert val('chain','eth_chainId',[])=='0x1';original=val('original_winner_header','eth_getBlockByNumber',[hex(WINNER_BLOCK),False]);assert original['hash']==WINNER_HASH;s['original_header']=original
  for offset in OFFSETS:
   c={'block_offset':offset};s['cases'].append(c)
   try:
    target=WINNER_BLOCK+offset;parent=val(f'parent_{offset}','eth_getBlockByNumber',[hex(target-1),False]);header=val(f'target_{offset}','eth_getBlockByNumber',[hex(target),False]);assert header['parentHash']==parent['hash'];c.update(parent_header=parent,header=header,seconds_after_winner=int(header['timestamp'],16)-int(original['timestamp'],16))
    assert val(f'probe_code_{offset}','eth_getCode',[PROBE,parent['number']])=='0x';assert val(f'caller_code_{offset}','eth_getCode',[CALLER,parent['number']])=='0x'
    env={'from':CALLER,'to':PROBE,'input':calldata('environment()'),'gas':hex(200_000),'gasPrice':'0x0'};trade={'from':CALLER,'to':PROBE,'input':calldata('execute(uint256,uint256,uint256)',['uint256']*3,[PRINCIPAL,RESERVE,MINIMUM]),'gas':hex(10_000_000),'gasPrice':'0x0'}
    overrides={'number':header['number'],'time':header['timestamp'],'gasLimit':header['gasLimit'],'baseFeePerGas':header['baseFeePerGas'],'feeRecipient':header['miner'],'prevRandao':header['mixHash']};payload={'blockStateCalls':[{'blockOverrides':overrides,'stateOverrides':{PROBE:{'code':runtime}},'calls':[env,trade,env]}],'validation':False,'traceTransfers':False};response=rpc(f'survival_{offset}','eth_simulateV1',[payload,parent['number']]);c['response']=response
    if not isinstance(response,dict) or not response.get('result'):raise ValueError('simulation unavailable')
    c.update(check_success(response['result'][0]['calls'],header))
   except Exception as e:c.update(exception=repr(e),traceback=traceback.format_exc())
   save('SUMMARY.json',s);print(json.dumps({k:v for k,v in c.items() if k not in ('response','header','parent_header')},indent=2),flush=True)
   if STOP:break
 except Exception as e:s.update(exception=repr(e),traceback=traceback.format_exc())
 s.update(completed_utc=utc(),rpc_requests=COUNT);save('SUMMARY.json',s);print(json.dumps({'completed_utc':s['completed_utc'],'rpc_requests':COUNT,'case_count':len(s['cases']),'exception':s.get('exception'),'live_profit':False}),flush=True)
if __name__=='__main__':main()
