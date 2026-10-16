"""No-liquidation counterfactual. Frozen route and size derived from one historical
winner; three historical states, NOT independent events. No production overrides.
"""
from pathlib import Path
import sys,json,hashlib,traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'replay'))
import run as old
from eth_abi import decode
import solcx
ROOT=Path(__file__).resolve().parent;PROBE='0x00000000000000000000000000000000DeaD7714';CALLER=old.CALLER;PRINCIPAL=20000*10**6;RESERVE=200000000000000
request=old.rpc
def paced(name,method,params,cost=1):return request(name,method,params,35 if method=='eth_simulateV1' else cost)
old.rpc=paced

def main():
 s={'started_utc':old.utc(),'transactions_sent':0,'live_profit':False,'fixed_principal_raw':str(PRINCIPAL),'fixed_native_reserve_wei':str(RESERVE),'explicit_inclusion_bid_wei':'0','scope':'one historical event; chosen route and 20k size; no discovery/recurrence claim; no liquidation in candidate','scenarios':[]}
 try:
  src=(ROOT/'ConversionProbe.sol').read_text();inp={'language':'Solidity','sources':{'C.sol':{'content':src}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.methodIdentifiers','evm.deployedBytecode.object']}}}}
  solcx.install_solc('0.8.34');out=solcx.compile_standard(inp,solc_version='0.8.34');old.save('compiler_input.json',inp);old.save('compiler_output.json',out);ob=out['contracts']['C.sol']['ConversionProbe'];assert ob['evm']['methodIdentifiers']['execute(uint256,uint256,uint256)']==old.selector('execute(uint256,uint256,uint256)').hex();runtime='0x'+ob['evm']['deployedBytecode']['object'];(old.OUT/'runtime.hex').write_text(runtime)
  s['runtime_sha256']=hashlib.sha256(bytes.fromhex(runtime[2:])).hexdigest()
  assert old.val('chain','eth_chainId',[])=='0x1'
  e=old.SEEDS[0];h=old.val('winner_block','eth_getBlockByNumber',[hex(e['block']),True],4);p=old.val('parent','eth_getBlockByNumber',[hex(e['block']-1),False]);n=old.val('next_block','eth_getBlockByNumber',[hex(e['block']+1),False]);rec=old.val('winner_receipt','eth_getTransactionReceipt',[e['tx']]);assert h['transactions'][0]['hash']==e['tx'] and rec['blockHash']==h['hash'] and int(rec['transactionIndex'],16)==0;s.update(header=h,parent=p,next_header=n,winner_receipt=rec)
  assert old.val('probe_empty_code','eth_getCode',[PROBE,p['number']])=='0x' and old.val('probe_empty_ETH','eth_getBalance',[PROBE,p['number']])=='0x0'
  env={'from':CALLER,'to':PROBE,'input':old.data('environment()'),'gas':hex(200000),'gasPrice':'0x0'}
  trade={'from':CALLER,'to':PROBE,'input':old.data('execute(uint256,uint256,uint256)',['uint256']*3,[PRINCIPAL,RESERVE,10**6]),'gas':hex(10000000),'gasPrice':'0x0'}
  for label,state,header,prefix in [('before_winner',p['number'],h,[]),('immediately_after_winner',p['number'],h,[old.ascall(h['transactions'][0])]),('next_block_start',h['number'],n,[])]:
   c={'label':label,'state_block':state,'prefix_count':len(prefix)};s['scenarios'].append(c)
   try:
    bo={'number':header['number'],'time':header['timestamp'],'gasLimit':header['gasLimit'],'baseFeePerGas':header['baseFeePerGas'],'feeRecipient':header['miner'],'prevRandao':header['mixHash']}
    payload={'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{PROBE:{'code':runtime}},'calls':prefix+[env,trade,env]}],'validation':False,'traceTransfers':False}
    result=old.rpc('standalone_'+label,'eth_simulateV1',[payload,state]);c['response']=result
    if not isinstance(result,dict) or not result.get('result'):raise ValueError('simulation unavailable')
    calls=result['result'][0]['calls'];c['prefix_verified']=True
    if prefix:
     x=calls[0];c['prefix_verified']=x.get('status')==rec['status'] and int(x['gasUsed'],16)==int(rec['gasUsed'],16) and old.normlogs(x.get('logs',[]))==old.normlogs(rec['logs'])
    before=decode(['uint256']*9,bytes.fromhex(calls[-3]['returnData'][2:]));c['environment_verified']=before[:3]==(1,int(header['number'],16),int(header['timestamp'],16)) and before[3:]==(0,0,0,0,0,0)
    a=calls[-2];c['status']=a.get('status');c['error']=a.get('error');c['gas_used']=int(a['gasUsed'],16)
    if a.get('status')=='0x1':
     v=decode(['uint256']*6,bytes.fromhex(a['returnData'][2:]));after=decode(['uint256']*9,bytes.fromhex(calls[-1]['returnData'][2:]));assert after[3:7]==(0,0,0,0);assert after[7]-before[7]==v[4]==RESERVE;assert after[8]-before[8]==v[3];assert v[0]==PRINCIPAL and v[1]-v[2]==v[3]
     c['values']={k:str(x) for k,x in zip(['loan_repaid_USDC_raw','gross_profit_USDC_raw','native_reserve_cost_USDC_raw','cash_paid_USDC_raw','native_reserve_paid_wei','frxUSD_redeemed_raw'],v)}
     burn=c['gas_used']*int(header['baseFeePerGas'],16);c['base_fee_cost_wei']=str(burn);c['reserve_sufficient']=RESERVE>=burn;c['unvalued_native_after_base_fee_wei']=str(RESERVE-burn)
     c['conditional_cash_result_valid']=c['prefix_verified'] and c['environment_verified'] and c['reserve_sufficient']
   except Exception as err:c.update(error=repr(err),traceback=traceback.format_exc())
   old.save('SUMMARY.json',s)
 except Exception as err:s.update(error=repr(err),traceback=traceback.format_exc())
 s.update(completed_utc=old.utc(),requests=old.COUNT);old.save('SUMMARY.json',s);print(json.dumps({k:v for k,v in s.items() if k not in ('header','parent','next_header','winner_receipt','scenarios')},indent=2));print(json.dumps([{k:v for k,v in c.items() if k!='response'} for c in s['scenarios']],indent=2))
if __name__=='__main__':main()
