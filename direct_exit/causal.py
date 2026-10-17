"""Exact historical prefix follow-up selected from the first run's pool logs.
No new submission, signatures or impersonation on chain: read-only state replay.
"""
import json,traceback
from pathlib import Path
TX='0x16b00a1ef23a7f028fbb0f4366ea0282ed82e186cd30ba171272209ccd51afcf'
TARGET=25643400

def normlogs(logs):return [(x['address'].lower(),[t.lower() for t in x['topics']],x['data'].lower()) for x in logs]
def ascall(tx):
 c={k:tx[k] for k in ('from','to','value','gas','accessList','authorizationList') if tx.get(k) is not None};c['input']=tx['input']
 if tx.get('maxFeePerGas') is not None:c.update(maxFeePerGas=tx['maxFeePerGas'],maxPriorityFeePerGas=tx.get('maxPriorityFeePerGas','0x0'))
 elif tx.get('gasPrice') is not None:c['gasPrice']=tx['gasPrice']
 return c

def follow(m,runtime):
 m.ALLOWED.add('eth_getTransactionByHash')
 plan={'selected_transaction':TX,'target_block':TARGET,'selection':'first/only transaction touching the original TRI pool in the prior run next-block logs; identified after initial study, not a prospective test','principal_USDC':20000,'route':'unchanged original frxUSD redemption route','comparison':'same canonical state/header; before-prefix positive result is in first run, now replay the canonical first transaction and retry'}
 m.save('CAUSAL_PLAN.json',plan);d={'plan':plan}
 rec=m.val('causal_receipt','eth_getTransactionReceipt',[TX]);tx=m.val('causal_transaction','eth_getTransactionByHash',[TX]);h=m.val('causal_header','eth_getBlockByNumber',[hex(TARGET),False]);p=m.val('causal_parent','eth_getBlockByNumber',[hex(TARGET-1),False])
 assert h['parentHash']==p['hash'] and rec['blockHash']==h['hash'] and int(rec['transactionIndex'],16)==0 and tx['hash']==TX and tx['blockHash']==h['hash']
 d.update(receipt=rec,transaction=tx,header=h,parent=p)
 d['trace']=m.rpc('causal_trace','debug_traceTransaction',[TX,{'tracer':'callTracer','timeout':'25s','tracerConfig':{'onlyTopCall':False}}])
 env={'from':m.CALLER,'to':m.PROBE,'input':'0x74e2b63c','gas':hex(200000),'gasPrice':'0x0'}
 trade={'from':m.CALLER,'to':m.PROBE,'input':m.encode_uints('2d29a47b',20_000*10**6,m.RESERVE,m.MINIMUM),'gas':hex(10000000),'gasPrice':'0x0'}
 bo={'number':h['number'],'time':h['timestamp'],'gasLimit':h['gasLimit'],'baseFeePerGas':h['baseFeePerGas'],'feeRecipient':h['miner'],'prevRandao':h['mixHash']}
 payload={'blockStateCalls':[{'blockOverrides':bo,'stateOverrides':{m.PROBE:{'code':runtime}},'calls':[ascall(tx),env,trade,env]}],'validation':False,'traceTransfers':False}
 r=m.rpc('after_exact_first_transaction','eth_simulateV1',[payload,p['number']]);d['response']=r
 if isinstance(r,dict) and r.get('result'):
  calls=r['result'][0]['calls'];assert len(calls)==4
  a=calls[0];d['prefix_status_matches']=a.get('status')==rec['status'];d['prefix_gas_matches']=int(a['gasUsed'],16)==int(rec['gasUsed'],16);d['prefix_logs_match']=normlogs(a.get('logs',[]))==normlogs(rec['logs'])
  if not all(d[k] for k in ('prefix_status_matches','prefix_gas_matches','prefix_logs_match')):raise ValueError('canonical prefix replay did not match')
  d['cash_test']=m.evaluate(calls[-3:],h,20_000*10**6)
 return d

def main():
 import run as old
 old.main();m=old.m;s=json.loads((old.OUT/'SUMMARY.json').read_text())
 if not m.STOP and not s.get('exception'):
  try:s['causal_followup']=follow(m,(old.OUT/'runtime.hex').read_text().strip())
  except Exception as e:s['causal_exception']=repr(e);s['causal_traceback']=traceback.format_exc()
 s.update(completed_utc=m.utc(),rpc_requests=m.COUNT);m.save('SUMMARY.json',s)
 print(json.dumps({'causal_exception':s.get('causal_exception'),'causal_test':s.get('causal_followup',{}).get('cash_test'),'requests':m.COUNT},indent=2),flush=True)
if __name__=='__main__':main()
