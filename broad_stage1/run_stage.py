"""Fixed-scope orchestration. Complete calendar census, not exhaustive possible protocols."""
import sys,json,traceback,collections
from pathlib import Path
import collect as C

A,B=25943261,26093737
BARK='0x'+C.H('Bark(bytes32,address,uint256,uint256,uint256,address,uint256)')
KICK='0x'+C.H('Kick(uint256,uint256,uint256,uint256,address,address,uint256)')
REDO='0x'+C.H('Redo(uint256,uint256,uint256,uint256,address,address,uint256)')
FILL='0x'+C.H('Fill(bytes32,address,address,uint256)')
SETTLE='0x'+C.H('Settlement(address)')
def registry(c,key):return C.addr(c.view('registry_'+key,C.CHAINLOG,'getAddress(bytes32)',key.encode().hex().ljust(64,'0'),hex(B)))
def run_api():
 c=C.Client();report={'started_utc':C.utc(),'no_transactions_sent':True,'completed_sections':[]}
 for name,fn in [('across',C.across),('orders',C.orders)]:
  try:report[name]=fn(c);report['completed_sections'].append(name)
  except Exception as e:report[name]={'error':repr(e),'traceback':traceback.format_exc()}
  C.save('API_REPORT.json',report)
 report['requests']=c.n;report['ended_utc']=C.utc();C.save('API_REPORT.json',report)
def run_chain():
 c=C.Client();r={'scope':'Ethereum 2026-09-10 to 2026-10-01 exclusive: Sky Dog all Bark events, nine named Clipper registries Kick/Redo; UniswapX mainnet Dutch V2 Fill and CoW Settlement','blocks':[A,B],'receipt_trace_selection':'Chronological first, middle, last distinct Sky reward transactions; first two distinct UniswapX and CoW fill transactions. Selection fixed before cash accounting.','transactions_sent':0,'errors':[],'complete':False};C.save('CHAIN_REPORT.json',r)
 try:
  h0=c.header(A-1);h1=c.header(A);h2=c.header(B);h3=c.header(B+1)
  assert int(h0['timestamp'],16)<C.START<=int(h1['timestamp'],16)
  assert int(h2['timestamp'],16)<C.END<=int(h3['timestamp'],16)
  C.save('HEADERS.json',[h0,h1,h2,h3]);r['boundaries_verified']=True
  addresses={};clips={}
  for key in ['MCD_DOG','MCD_VAT','MCD_DAI_JOIN','MCD_DAI']:
   addresses[key]=registry(c,key)
  for n in ['ETH_A','ETH_B','ETH_C','WBTC_A','WBTC_B','WBTC_C','WSTETH_A','WSTETH_B','RETH_A']:
   try:
    x=registry(c,'MCD_CLIP_'+n)
    if int(x,16):clips[x]=n
   except Exception as e:r['errors'].append({'registry':n,'error':repr(e)})
  r['addresses']=addresses;r['clippers']=clips;r['clip_parameters']={};C.save('CHAIN_REPORT.json',r)
  for cp in clips:
   p={}
   for sig in ['tip()','chip()','stopped()','count()','dog()','vat()','ilk()']:
    try:p[sig]=c.view('clip_'+sig,cp,sig,block=hex(B))
    except Exception as e:p[sig]={'error':repr(e)}
   r['clip_parameters'][cp]=p;C.save('CHAIN_REPORT.json',r)
  logs=c.logs('full_window',list(dict.fromkeys([addresses['MCD_DOG'],C.REACTOR,C.COW]+list(clips))),[[BARK,KICK,REDO,FILL,SETTLE]],A,B)
  r['complete']=True;r['counts']=dict(collections.Counter(l['topics'][0] for l in logs));r['reward_events']=[];r['barks']=[]
  for l in logs:
   topic=l['topics'][0];words=[l['data'][i:i+64] for i in range(2,len(l['data']),64)]
   if topic==BARK:
    assert len(words)==4 and len(l['topics'])==4
    r['barks'].append({'tx':l['transactionHash'],'block':int(l['blockNumber'],16),'ilk':l['topics'][1],'urn':C.addr(l['topics'][2]),'clip':C.addr(words[3]),'id':int(l['topics'][3],16),'position':int(l['transactionIndex'],16)})
   if topic in (KICK,REDO):
    assert len(words)==4 and len(l['topics'])==4
    r['reward_events'].append({'type':'kick' if topic==KICK else 'redo','clip':l['address'],'tx':l['transactionHash'],'block':int(l['blockNumber'],16),'position':int(l['transactionIndex'],16),'id':int(l['topics'][1],16),'urn':C.addr(l['topics'][2]),'keeper':C.addr(l['topics'][3]),'coin_rad':str(int(words[3],16)),'reward_dai_wei_floor':str(int(words[3],16)//10**27)})
  missing={b['clip'] for b in r['barks'] if b['clip'] not in clips};r['unscanned_new_clippers']=sorted(missing)
  groups={'sky':[l for l in logs if l['topics'][0] in (KICK,REDO)],'uniswapx':[l for l in logs if l['topics'][0]==FILL],'cow':[l for l in logs if l['topics'][0]==SETTLE]};r['selections']={};C.save('CHAIN_REPORT.json',r)
  for group,ls in groups.items():
   seq=sorted({l['transactionHash']:l for l in ls}.values(),key=lambda l:(int(l['blockNumber'],16),int(l['transactionIndex'],16)))
   if group=='sky' and seq:chosen=list({l['transactionHash']:l for l in [seq[0],seq[len(seq)//2],seq[-1]]}.values())
   else:chosen=seq[:2]
   r['selections'][group]=[{'tx':l['transactionHash'],'block':int(l['blockNumber'],16),'position':int(l['transactionIndex'],16)} for l in chosen];C.save('CHAIN_REPORT.json',r)
   for chosen in r['selections'][group]:
    tx=chosen['tx']
    try:
     rec=c.rpc(group+'_receipt','eth_getTransactionReceipt',[tx]);C.save(group+'/'+tx+'_receipt.json',rec)
     tr=c.rpc(group+'_trace','debug_traceTransaction',[tx,{'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True}}]);C.save(group+'/'+tx+'_trace.json',tr)
     chosen['trace_received']=True
    except Exception as e:chosen['error']=repr(e)
    C.save('CHAIN_REPORT.json',r)
 except Exception as e:r['exception']=repr(e);r['traceback']=traceback.format_exc()
 r['requests']=c.n;r['blocked_hosts']=sorted(c.blocked);r['ended_utc']=C.utc();C.save('CHAIN_REPORT.json',r)
 if not r['complete']:raise SystemExit('Calendar scan incomplete; evidence retained, no zero-income conclusion')
if __name__=='__main__':
 if len(sys.argv)!=2 or sys.argv[1] not in ('api','chain'):raise SystemExit('choose api or chain')
 run_api() if sys.argv[1]=='api' else run_chain()
