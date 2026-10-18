"""Read-only evidence completion. No new trading executor or transaction simulation.
Retains the first acquisition failure; same frozen historical scope.
"""
import sys,json,re,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'broad_stage1'))
import collect as C
import run_stage as R
# Official sky-ecosystem/dss-chain-log README and chainlog-ui/examples/python.py.
CHAINLOG='0xda0ab1e0017debcd72be8599041a2aa3ba7e740f'
PERMIT2='0x000000000022d473030f116ddee9f6b43ac78ba3'
ORDERS=[
 {'hash':'0x4c23a896626cea2566b6a1d2499f2e0b3a6daeb03558aceaf807ae9e5c3c8472','tx':'0x224c94d52947b7af20cae64ace5be721085c3ca1d15bd64a4f492017ef4af34b','block':26217505,'swapper':'0xe0a69f35567364f2e4034fda77712a7a980c7563','nonce':'1993352109482785658904775818785758527923428726878360778474020427139721948421'},
 {'hash':'0x09ff621f8d553b38aa054038cb28505d28adbf968f1b4bbf0491c035b030ba4a','tx':'0xa50e21f4d714c616f3302b1953ce4a47fc98f8f7433b01b69da21220524417dc','block':26217510,'swapper':'0x8e35f6caee5a3a59f1f8280ae81aeaaa6a1c7c2f','nonce':'1993351474211842483272066417889308843071196701099046641334132156145588948225'}
]
def strict_addr(h):
 if not isinstance(h,str):raise ValueError('address result is not text')
 x=h[2:] if h.startswith('0x') else h
 if len(x)!=64 or not re.fullmatch('[0-9a-fA-F]{64}',x) or int(x[:24],16)!=0:raise ValueError('missing or invalid ABI address word')
 return '0x'+x[-40:].lower()
def validate_addresses(addresses):
 seq=addresses if isinstance(addresses,list) else [addresses]
 if not seq or any(not isinstance(a,str) or not re.fullmatch('0x[0-9a-fA-F]{40}',a) or int(a,16)==0 for a in seq):raise ValueError('invalid log address filter')
 return seq
class VerifiedClient(C.Client):
 def logs(self,name,addresses,topics,a,b):return super().logs(name,validate_addresses(addresses),topics,a,b)
 def view(self,name,to,sig,args='',block='latest',chain=1):
  validate_addresses(to)
  return super().view(name,to,sig,args,block,chain)

def order_evidence():
 c=VerifiedClient();report={'source':'Two unique captured API-open orders also reported filled; no order submission or counterfactual fill','cases':[],'no_transactions_sent':True}
 for o in ORDERS:
  item=dict(o);report['cases'].append(item)
  try:
   h=c.header(o['block']);rc=c.rpc('order_receipt','eth_getTransactionReceipt',[o['tx']]);tx=c.rpc('order_transaction','eth_getTransactionByHash',[o['tx']])
   assert rc['status']=='0x1' and int(rc['blockNumber'],16)==o['block'] and rc['blockHash']==h['hash'] and tx['blockHash']==h['hash']
   item.update(canonical_header=h,canonical_receipt=rc,canonical_transaction=tx)
   matches=[l for l in rc['logs'] if l['address'].lower()==C.REACTOR and len(l['topics'])>1 and l['topics'][0]==R.FILL and l['topics'][1].lower()==o['hash']]
   item['fill_event_count']=len(matches);assert len(matches)==1
   nonce=int(o['nonce']);word=nonce>>8;bit=nonce&255
   args=o['swapper'][2:].rjust(64,'0')+C.wi(word)
   pre=c.view('nonce_before_fill',PERMIT2,'nonceBitmap(address,uint256)',args,hex(o['block']-1))
   post=c.view('nonce_after_fill',PERMIT2,'nonceBitmap(address,uint256)',args,hex(o['block']))
   assert len(pre)==66 and len(post)==66
   item['nonce_before_spent']=bool((int(pre,16)>>bit)&1);item['nonce_after_spent']=bool((int(post,16)>>bit)&1)
   item['canonical_fill_timestamp']=int(h['timestamp'],16)
   tr=c.rpc('order_trace','debug_traceTransaction',[o['tx'],{'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True}}]);C.save('orders/'+o['hash']+'_trace.json',tr)
   item['trace_received']=True
  except Exception as e:item['error']=repr(e);item['traceback']=traceback.format_exc()
  C.save('ORDER_CANONICAL.json',report)
 report['requests']=c.n;C.save('ORDER_CANONICAL.json',report)
 if any(x.get('error') for x in report['cases']):raise SystemExit('Order verification incomplete; not empty inventory proof')
def chain():
 C.CHAINLOG=CHAINLOG;C.addr=strict_addr;C.Client=VerifiedClient
 # Contract code is a necessary precondition for decoding a historical registry view.
 c=VerifiedClient();code=c.rpc('verified_chainlog_code','eth_getCode',[CHAINLOG,hex(R.B)])
 if not isinstance(code,str) or len(code)<=2:raise SystemExit('Verified registry not deployed at target state')
 # Use that same client for all requests so numbering/budget remains global.
 C.Client=lambda:c
 R.run_chain()
if __name__=='__main__':
 if len(sys.argv)!=2 or sys.argv[1] not in ('orders','chain'):raise SystemExit('orders or chain')
 order_evidence() if sys.argv[1]=='orders' else chain()
