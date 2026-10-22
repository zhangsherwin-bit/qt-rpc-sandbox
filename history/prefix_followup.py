"""Follow-up to run 38771437945. The first eth_simulateV1 was rejected because
its final synthetic zero-balance caller was charged gas. We explicitly set only
synthetic probe calls to gasPrice=0 with validation=false. No balance overrides.
This is a simulation execution convention, not evidence a real transaction needs
no gas. Actual preceding calls retain their original fee fields. Compare all
prefix status/logs/gas before accepting the liquidation result.
"""
import json,pathlib,datetime,hashlib,sys
from replay import Client,ROOT,ETH,POOL,WETH,PROBE,CALLER,compile_probe,selector,word,addr,decode_words,utc,keccak256
TX='0xc9a55cc994a45ee75562bc7f316e1a81414b4db888437e577829b131257ee711'
USER='0xc950fe241c50f93d872edb5a97066474c84c2394'
REPAY=7834307681356720885

def norm(logs):return [(l['address'].lower(),[t.lower() for t in l['topics']],l['data'].lower()) for l in logs]
def main():
 out=ROOT/('prefix_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(exist_ok=True)
 c=Client(out/'raw');s={'started_utc':utc(),'original_run':38771437945,'zero_balance_overrides':True,'synthetic_calls_gasPrice':0,'real_transaction_gas_still_required':True,'transactions_sent':0}
 try:
  rt,status=compile_probe();s['compile']=status
  if not rt:raise ValueError('compiler failed')
  if c.val(ETH,'eth_chainId',[])!='0x1':raise ValueError('wrong chain')
  receipt=c.val(ETH,'eth_getTransactionReceipt',[TX]);b=c.val(ETH,'eth_getBlockByNumber',[receipt['blockNumber'],True],6);P=hex(int(b['number'],16)-1)
  if int(b['number'],16)!=25832491 or int(receipt['transactionIndex'],16)!=3:raise ValueError('anchor mismatch')
  if c.val(ETH,'eth_getCode',[PROBE,P])!='0x':raise ValueError('probe occupied')
  code=c.val(ETH,'eth_getCode',[POOL,P]);s['pool_runtime_sha256']=hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()
  prefix=b['transactions'][:3];s['prefix_tx_hashes']=[t['hash'] for t in prefix];calls=[];canonical=[]
  for t in prefix:
   call={k:t[k] for k in ('from','to','value','gas') if t.get(k) is not None};call['input']=t['input']
   if t.get('maxFeePerGas') is not None:
    call['maxFeePerGas']=t['maxFeePerGas'];call['maxPriorityFeePerGas']=t['maxPriorityFeePerGas']
   elif t.get('gasPrice') is not None:call['gasPrice']=t['gasPrice']
   calls.append(call);canonical.append(c.val(ETH,'eth_getTransactionReceipt',[t['hash']]))
  # Read-only post-prefix controls; native balances remain untouched.
  calls.append({'from':CALLER,'to':PROBE,'input':selector('environment()'),'gas':hex(200000),'gasPrice':'0x0'})
  calls.append({'from':CALLER,'to':POOL,'input':selector('getUserAccountData(address)')+addr(USER).hex(),'gas':hex(1000000),'gasPrice':'0x0'})
  calls.append({'from':CALLER,'to':PROBE,'input':selector('aave(address,uint256)')+(addr(USER)+word(REPAY)).hex(),'gas':hex(6000000),'gasPrice':'0x0'})
  bo={'number':b['number'],'time':b['timestamp'],'gasLimit':b['gasLimit'],'baseFeePerGas':b['baseFeePerGas'],'feeRecipient':b['miner'],'prevRandao':b['mixHash']}
  request={'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{PROBE:{'code':rt}},'calls':calls}],'validation':False,'traceTransfers':False}
  result=c.rpc(ETH,'eth_simulateV1',[request,P]);s['response']=result;s['canonical_prefix_receipts']=canonical;s['block_header']={k:b.get(k) for k in bo if k in b}
  if isinstance(result,dict) and isinstance(result.get('result'),list) and len(result['result'])==1:
   sim=result['result'][0];s['simulated_block']=sim;outputs=sim['calls']
   checks=[]
   for i,r in enumerate(canonical):
    x=outputs[i]
    checks.append({'tx':r['transactionHash'],'status_equal':int(x['status'],16)==int(r['status'],16),'logs_equal':norm(x.get('logs',[]))==norm(r.get('logs',[])),'gas_equal':int(x['gasUsed'],16)==int(r['gasUsed'],16),'simulated_gas':int(x['gasUsed'],16),'canonical_gas':int(r['gasUsed'],16)})
   s['prefix_comparison']=checks
   s['prefix_logs_status_match']=all(x['status_equal'] and x['logs_equal'] for x in checks)
   s['prefix_gas_match']=all(x['gas_equal'] for x in checks)
   s['environment']=decode_words(outputs[3].get('returnData','0x')) if int(outputs[3]['status'],16)==1 else None
   s['environment_matches']=s['environment']==[1,int(b['number'],16),int(b['timestamp'],16),0]
   s['post_prefix_borrower_account']= [str(x) for x in decode_words(outputs[4].get('returnData','0x'))] if int(outputs[4]['status'],16)==1 else None
   s['liquidation_call']=outputs[5]
   s['cash_words']= [str(x) for x in decode_words(outputs[5].get('returnData','0x'))] if int(outputs[5]['status'],16)==1 else None
   s['retrospective_cash_execution_verified']=bool(s['prefix_logs_status_match'] and s['prefix_gas_match'] and s['environment_matches'] and s['cash_words'] and int(s['cash_words'][0])>0)
  else:s['retrospective_cash_execution_verified']=False
 except Exception as e:s['error']=repr(e)
 s.update(completed_utc=utc(),request_count=c.count,estimated_RU=c.ru)
 (out/'SUMMARY.json').write_text(json.dumps(s,indent=2))
 print(json.dumps({k:v for k,v in s.items() if k not in ('response','simulated_block','canonical_prefix_receipts','liquidation_call')},indent=2));print('Evidence',out)
if __name__=='__main__':main()
