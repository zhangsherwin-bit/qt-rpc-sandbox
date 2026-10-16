"""Selected historical cash-settlement comparison. Not live deployment or capture.
Preserve actual transferred ETH compensation and USDC. Code overrides at two unused
research addresses only. Synthetic caller is not charged gas; an explicit native
reserve is purchased and delivered, then checked against measured gas at base fee.
"""
from pathlib import Path
import datetime as dt,hashlib,json,sys,traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'replay'))
import run as old
from eth_abi import decode
import solcx
ROOT=Path(__file__).resolve().parent
SETTLE='0x00000000000000000000000000000000DeaD7713'
CASH=old.PROBE;CALLER=old.CALLER
original_rpc=old.rpc
def paced(name,method,params,cost=1):return original_rpc(name,method,params,35 if method=='eth_simulateV1' else cost)
old.rpc=paced
CASES=[dict(old.SEEDS[0],exit=old.USTB,fee=500,direct=11087584263217595832,producer=11087584263219454765,reserve=110008011545352),dict(old.SEEDS[1],exit=old.CUST,fee=100,direct=0,producer=2819936283644016,reserve=213886026009576)]
def compile_all():
 cashrt,cb=old.compile_probe();src=(ROOT/'SettlementProbe.sol').read_text();inp={'language':'Solidity','sources':{'S.sol':{'content':src}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.methodIdentifiers','evm.deployedBytecode.object']}}}}
 old.save('settlement_compiler_input.json',inp);co=solcx.compile_standard(inp,solc_version='0.8.34');old.save('settlement_compiler_output.json',co);obj=co['contracts']['S.sol']['SettlementProbe'];sig='execute(address,uint256,address,uint24,uint256,uint256,uint256)'
 if obj['evm']['methodIdentifiers'][sig]!=old.selector(sig).hex():raise ValueError('ABI mismatch')
 rt='0x'+obj['evm']['deployedBytecode']['object'];(old.OUT/'settlement_runtime.hex').write_text(rt)
 return cashrt,rt,{'cash':cb,'settlement_source_sha256':hashlib.sha256(src.encode()).hexdigest(),'settlement_runtime_sha256':hashlib.sha256(bytes.fromhex(rt[2:])).hexdigest()}

def main():
 s={'started_utc':old.utc(),'transactions_sent':0,'live_profit':False,'cases':[],'scope':'Two index-zero historical discovery cases; deliberately selected routes from earlier results. No independent holdout or capture claim.'}
 try:
  cashrt,rt,s['build']=compile_all()
  if old.val('chain','eth_chainId',[])!='0x1':raise ValueError('chain')
  for i,e in enumerate(CASES):
   c={'seed':e};s['cases'].append(c)
   try:
    h=old.val('header_'+str(i),'eth_getBlockByNumber',[hex(e['block']),False]);p=old.val('parent_'+str(i),'eth_getBlockByNumber',[hex(e['block']-1),False]);receipt=old.val('receipt_'+str(i),'eth_getTransactionReceipt',[e['tx']]);c.update(header=h,parent=p,receipt=receipt)
    if receipt['blockHash']!=h['hash'] or int(receipt['transactionIndex'],16)!=0 or h['transactions'][0]!=e['tx']:raise ValueError('not original index-zero state')
    if int(receipt['gasUsed'],16)*(int(receipt['effectiveGasPrice'],16)-int(h['baseFeePerGas'],16))+e['direct']!=e['producer']:raise ValueError('producer compensation mismatch')
    for tag,a in [('cash',CASH),('settlement',SETTLE),('caller',CALLER)]:
     if old.val(tag+'_code_'+str(i),'eth_getCode',[a,p['number']])!='0x' or old.val(tag+'_ETH_'+str(i),'eth_getBalance',[a,p['number']])!='0x0':raise ValueError('research account occupied')
    bo={'number':h['number'],'time':h['timestamp'],'gasLimit':h['gasLimit'],'baseFeePerGas':h['baseFeePerGas'],'feeRecipient':h['miner'],'prevRandao':h['mixHash']}
    env={'from':CALLER,'to':SETTLE,'input':old.data('environment()'),'gas':hex(200000),'gasPrice':'0x0'}
    execution={'from':CALLER,'to':SETTLE,'input':old.data('execute(address,uint256,address,uint24,uint256,uint256,uint256)',['address','uint256','address','uint24','uint256','uint256','uint256'],[e['borrower'],e['seize'],e['exit'],e['fee'],e['producer'],e['reserve'],1]),'gas':hex(10000000),'gasPrice':'0x0'}
    payload={'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{CASH:{'code':cashrt},SETTLE:{'code':rt}},'calls':[env,execution,env]}],'validation':False,'traceTransfers':True}
    r=old.rpc('full_settlement_'+str(i),'eth_simulateV1',[payload,p['number']]);c['response']=r
    if not isinstance(r,dict) or not r.get('result'):raise ValueError('simulation unavailable')
    calls=r['result'][0]['calls'];c['execution_status']=calls[1].get('status');c['execution_error']=calls[1].get('error')
    if calls[1].get('status')=='0x1':
     before=decode(['uint256']*9,bytes.fromhex(calls[0]['returnData'][2:]));after=decode(['uint256']*9,bytes.fromhex(calls[2]['returnData'][2:]));v=decode(['uint256']*5,bytes.fromhex(calls[1]['returnData'][2:]));gas=int(calls[1]['gasUsed'],16);burn=gas*int(h['baseFeePerGas'],16)
     assert before[:3]==(1,e['block'],int(h['timestamp'],16));assert before[3:8]==(0,0,0,0,0);assert after[3:6]==(0,0,0)
     assert after[6]-before[6]==e['reserve']==v[4];assert after[7]-before[7]==v[2];assert after[8]-before[8]==e['producer']==v[3];assert v[0]-v[1]==v[2]
     c['values']={k:str(x) for k,x in zip(['gross_USDC_raw','swap_cost_USDC_raw','paid_USDC_raw','producer_paid_wei','native_reserve_paid_wei'],v)}
     c.update(gas_used=gas,base_fee_cost_wei=str(burn),gas_reserve_covers_measured_base_fee=e['reserve']>=burn,unvalued_native_after_base_fee_wei=str(e['reserve']-burn),checks='all initial/principal/output/producer and terminal balance checks passed')
    if i==0:
     negative={'blockStateCalls':[{'stateOverrides':{CASH:{'code':cashrt},SETTLE:{'code':rt}},'calls':[execution]}],'validation':False,'traceTransfers':True}
     c['post_winner_control']=old.rpc('post_winner_negative','eth_simulateV1',[negative,h['number']])
   except Exception as err:c.update(error=repr(err),traceback=traceback.format_exc())
   old.save('SUMMARY.json',s)
 except Exception as err:s.update(error=repr(err),traceback=traceback.format_exc())
 s.update(completed_utc=old.utc(),request_count=old.COUNT,estimated_RU=old.RU);old.save('SUMMARY.json',s)
 print(json.dumps({'completed_utc':s['completed_utc'],'error':s.get('error'),'requests':s['request_count'],'cases':[{k:v for k,v in c.items() if k not in ('response','post_winner_control','header','parent','receipt')} for c in s['cases']]},indent=2))
if __name__=='__main__':main()
