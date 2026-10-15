"""Equal-inclusion-payment benchmark. Historical read-only simulation, not a trade.
One previously selected Aave event. Keep actual preceding calls and compare their logs/status/gas.
Only synthetic calls use gasPrice=0, then charge their measured gas at the winner's effective gas price.
"""
import json,pathlib,datetime,hashlib
from replay import Client,ROOT,ETH,PROBE,CALLER,selector,addr,word,decode_words,utc
from prefix_followup import norm,TX,USER,REPAY
BID=347561592993146169

def main():
 out=ROOT/('bid_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(exist_ok=True);c=Client(out/'raw')
 s={'started_utc':utc(),'transactions_sent':0,'producer_payment_wei':str(BID),'no_balance_overrides':True,'synthetic_gas_price_zero':True,'scope':'single selected historical equal-bid comparison, not independent validation or capture probability'}
 try:
  import solcx
  if '0.8.34' not in {str(v) for v in solcx.get_installed_solc_versions()}:solcx.install_solc('0.8.34')
  source=(ROOT/'BidCashProbe.sol').read_text();inp={'language':'Solidity','sources':{'B.sol':{'content':source}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.deployedBytecode.object','evm.methodIdentifiers']}}}}
  (out/'compiler_input.json').write_text(json.dumps(inp));co=solcx.compile_standard(inp,solc_version='0.8.34');(out/'compiler_output.json').write_text(json.dumps(co));compiled=co['contracts']['B.sol']['BidCashProbe'];rt='0x'+compiled['evm']['deployedBytecode']['object']
  assert compiled['evm']['methodIdentifiers']['execute(address,uint256,uint256)']==selector('execute(address,uint256,uint256)')[2:]
  s['runtime_sha256']=hashlib.sha256(bytes.fromhex(rt[2:])).hexdigest();s['compiled']=True
  if c.val(ETH,'eth_chainId',[])!='0x1':raise ValueError('wrong chain')
  receipt=c.val(ETH,'eth_getTransactionReceipt',[TX]);b=c.val(ETH,'eth_getBlockByNumber',[receipt['blockNumber'],True],6);P=hex(int(b['number'],16)-1)
  if int(b['number'],16)!=25832491 or int(receipt['transactionIndex'],16)!=3:raise ValueError('anchor mismatch')
  if c.val(ETH,'eth_getCode',[PROBE,P])!='0x':raise ValueError('occupied probe')
  calls=[];canonical=[]
  for t in b['transactions'][:3]:
   call={k:t[k] for k in ('from','to','value','gas') if t.get(k) is not None};call['input']=t['input']
   if t.get('maxFeePerGas') is not None:call.update(maxFeePerGas=t['maxFeePerGas'],maxPriorityFeePerGas=t['maxPriorityFeePerGas'])
   else:call['gasPrice']=t['gasPrice']
   calls.append(call);canonical.append(c.val(ETH,'eth_getTransactionReceipt',[t['hash']]))
  calls.append({'from':CALLER,'to':PROBE,'input':selector('environment()'),'gas':hex(200000),'gasPrice':'0x0'})
  data=selector('execute(address,uint256,uint256)')+(addr(USER)+word(REPAY)+word(BID)).hex()
  calls.append({'from':CALLER,'to':PROBE,'input':data,'gas':hex(6000000),'gasPrice':'0x0'})
  bo={'number':b['number'],'time':b['timestamp'],'gasLimit':b['gasLimit'],'baseFeePerGas':b['baseFeePerGas'],'feeRecipient':b['miner'],'prevRandao':b['mixHash']}
  result=c.rpc(ETH,'eth_simulateV1',[{'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{PROBE:{'code':rt}},'calls':calls}],'validation':False,'traceTransfers':False},P]);s['response']=result;s['canonical_prefix']=canonical;s['original_receipt']=receipt;s['block_context']=bo
  if isinstance(result,dict) and isinstance(result.get('result'),list):
   outputs=result['result'][0]['calls'];checks=[]
   for i,r in enumerate(canonical):
    x=outputs[i];checks.append({'tx':r['transactionHash'],'status_equal':int(x['status'],16)==int(r['status'],16),'logs_equal':norm(x.get('logs',[]))==norm(r['logs']),'gas_equal':int(x['gasUsed'],16)==int(r['gasUsed'],16)})
   s['prefix_comparison']=checks;s['prefix_matched']=all(all(v for k,v in ch.items() if k!='tx') for ch in checks)
   env=outputs[3];s['environment_matches']=int(env['status'],16)==1 and decode_words(env['returnData'])==[1,int(b['number'],16),int(b['timestamp'],16),0]
   last=outputs[4];s['execution_status']=last['status']
   if s['prefix_matched'] and s['environment_matches'] and int(last['status'],16)==1:
    w=decode_words(last['returnData']);gas=int(last['gasUsed'],16);price=int(receipt['effectiveGasPrice'],16)
    s.update(gross_weth_wei=str(w[0]),cash_after_bid_weth_wei=str(w[1]),internal_gas=w[2],terminal_native_wei=str(w[3]),full_simulated_call_gas=gas,winner_effective_gas_price_wei=str(price),gas_cost_at_winner_price_wei=str(gas*price),net_at_same_bid_and_gas_price_wei=str(w[1]-gas*price),winner_gas_used=int(receipt['gasUsed'],16),gas_units_saved=int(receipt['gasUsed'],16)-gas)
   else:s['execution_failure']=last
 except Exception as e:s['error']=repr(e)
 s.update(completed_utc=utc(),request_count=c.count,estimated_RU=c.ru)
 (out/'SUMMARY.json').write_text(json.dumps(s,indent=2));print(json.dumps({k:v for k,v in s.items() if k not in ('response','canonical_prefix','original_receipt')},indent=2));print('Evidence',out)
if __name__=='__main__':main()
