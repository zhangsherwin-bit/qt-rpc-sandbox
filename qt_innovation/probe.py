"""QT Stage1 independent mechanisms: reproducible read-only finite RPC tests.
Original public data; no signatures, broadcasts, wallets, synthetic states or private APIs.
Only quote/preview and historical third-party events; NO observed executable own profit.
"""
import json,urllib.request,urllib.error,hashlib,datetime,time,traceback
from pathlib import Path
from Crypto.Hash import keccak
ROOT=Path('qt_new_evidence');ROOT.mkdir(exist_ok=True)
RPC={'ETH':'https://rpc-eth.blockmachine.io','RH':'https://rpc.mainnet.chain.robinhood.com'}
USDC='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
FRX='0xcacd6fd266af91b8aed52accc382b4e165586e29'
SFRX='0xcf62f905562626cfcdd2261162a51fd02fc9c5b6'
FXB='0x76237bcfdbe8e06fb774663add96216961df4ff3'
CUST='0x4f95c5ba0c7c69fb2f9340e190ccee890b3bd87c'
QUOTER='0x61ffe014ba17989e743c5f6cb21bf9697530b21e'
KEEP='0x5d9120f45271374c7c8e185cca121d88a250a71a'
COUNTS={'ETH':0,'RH':0};DENIED=set();START=time.monotonic()
OUT={'date_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'arms':['frxUSD discounted redemption','sfrxUSD share discount','FXB2026 maturity claim','Kerf owner-funded keeper bounties'],
 'source':'public Ethereum and Robinhood Chain RPC; official source addresses',
 'execution_cash_profit_proven':False,'capital_deployed':False,'observations':[],'keeper':{},'errors':[]}
def save(): (ROOT/'REPORT.json').write_text(json.dumps(OUT,indent=2,sort_keys=True,default=str))
def sha(v):return hashlib.sha256(v).hexdigest()
def selector(s):
 k=keccak.new(digest_bits=256);k.update(s.encode());return '0x'+k.hexdigest()[:8]
def topic(s):
 k=keccak.new(digest_bits=256);k.update(s.encode());return '0x'+k.hexdigest()
def hx(x):return format(int(x),'064x')
def addr(s):return hx(int(s,16))
def words(r):
 if not r.startswith('0x') or len(r[2:])%64:raise ValueError('bad ABI response')
 return [int(r[i:i+64],16) for i in range(2,len(r),64)]
def rpc(chain,method,params):
 if chain in DENIED:raise RuntimeError('host denied, stopped')
 if COUNTS[chain]>=(85 if chain=='ETH' else 26) or time.monotonic()-START>650:raise RuntimeError('fixed time/request cap')
 COUNTS[chain]+=1;n=COUNTS[chain];req=json.dumps({'jsonrpc':'2.0','id':n,'method':method,'params':params}).encode();raw=b''
 rec={'chain':chain,'number':n,'method':method,'request_sha256':sha(req)}
 try:
  time.sleep(.35)
  with urllib.request.urlopen(urllib.request.Request(RPC[chain],req,{'Content-Type':'application/json','User-Agent':'QT-ReadOnly-Research'}),timeout=23) as response:
   rec['http']=response.status;raw=response.read(1000000)
  obj=json.loads(raw)
  if 'error' in obj:raise RuntimeError('RPC '+str(obj['error'])[:300])
  if 'result' not in obj:raise RuntimeError('result missing')
  rec['status']='OK';return obj['result']
 except urllib.error.HTTPError as e:
  rec['http']=e.code;rec['status']='HTTP_DENIED' if e.code in (401,403,429) else 'HTTP_ERROR';raw=e.read(50000)
  if e.code in (401,403,429):DENIED.add(chain)
  raise
 except Exception as e:rec['status']='ERROR';rec['error']=str(e)[:300];raise
 finally:
  rec['response_sha256']=sha(raw)
  (ROOT/f'{chain}_{n:03d}.json').write_text(json.dumps(rec,indent=2))
  (ROOT/f'{chain}_{n:03d}.response').write_bytes(raw)
  save()
def read_uint(contract,signature,value,block):
 r=words(rpc('ETH','eth_call',[{'to':contract,'data':selector(signature)+hx(value)},hex(block)]))
 if len(r)!=1:raise ValueError('ambiguous ABI')
 return r[0]
def quote(tin,tout,raw,fee,b):
 args=addr(tin)+addr(tout)+hx(raw)+hx(fee)+hx(0)
 data=selector('quoteExactInputSingle((address,address,uint256,uint24,uint160))')+args
 r=words(rpc('ETH','eth_call',[{'to':QUOTER,'data':data},hex(b)]))
 if len(r)!=4:raise ValueError('unexpected V3 quote layout')
 return r[0]
def freeze(b):
 h=rpc('ETH','eth_getBlockByNumber',[hex(b),False]);return {'block':b,'hash':h['hash'],'timestamp':int(h['timestamp'],16)}
def frax():
 assert int(rpc('ETH','eth_chainId',[]),16)==1
 tip=int(rpc('ETH','eth_blockNumber',[]),16)
 for b in sorted(set([26163132,tip-3])):
  state={'anchor':freeze(b),'size_results':[]};OUT['observations'].append(state)
  for name,contract in [('custodian',CUST),('sfrx',SFRX),('FXB',FXB)]:
   try:state[name+'_has_code']=rpc('ETH','eth_getCode',[contract,hex(b)])!='0x'
   except Exception as e:state[name+'_code_error']=str(e)
  for size in [100,1000]:
   row={'usdc_input':size,'routes':[]};state['size_results'].append(row)
   for fee in [500,3000]:
    r={'fee':fee}
    row['routes'].append(r)
    try:
     frx=quote(USDC,FRX,size*10**6,fee,b)
     r['frx_acquired']=frx/1e18
     r['usdc_if_redeemed']=read_uint(CUST,'previewRedeem(uint256)',frx,b)/1e6
     r['indicative_frx_to_usdc_gross']=r['usdc_if_redeemed']-size
     r['no_executed_cash']=True
     sf=quote(FRX,SFRX,frx,fee,b)
     r['sfrx_acquired']=sf/1e18
     frx_out=read_uint(SFRX,'previewRedeem(uint256)',sf,b)
     r['frx_if_sfrx_redeemed']=frx_out/1e18
     cash=read_uint(CUST,'previewRedeem(uint256)',frx_out,b)
     r['indicative_sfrx_to_usdc_gross']=cash/1e6-size
     r['no_atomic_financing_or_approval_proof']=True
    except Exception as e:r['error']=repr(e)
    save()
   r={'mechanism':'FXB2026_TIME_CLAIM','no_immediate_cash':True,'maturity':'2026-12-31'}
   try:r['fxb_acquired_for_1000_frxUSD']=quote(FRX,FXB,1000*10**18,500,b)/1e18
   except Exception as e:r['error']=str(e)
   row['fxb_claim_indication']=r;save()
  state['status']='BOUNDED_QUOTES_ATTEMPTED';save()
def kerf():
 k=OUT['keeper'];k.update(contract=KEEP,chain=4663,events=[],pages=[])
 assert int(rpc('RH','eth_chainId',[]),16)==4663
 tip=int(rpc('RH','eth_blockNumber',[]),16)
 k['has_code']=rpc('RH','eth_getCode',[KEEP,hex(tip)])!='0x'
 lo=max(56938742,tip-49999);k['window']={'from':lo,'to':tip}
 ev_topic=topic('Harvested(uint256,address,uint256,uint256,uint256,uint256,bool)')
 for a in range(lo,tip+1,5000):
  z=min(a+4999,tip);page={'from':a,'to':z};k['pages'].append(page)
  try:
   logs=rpc('RH','eth_getLogs',[{'address':KEEP,'topics':[ev_topic],'fromBlock':hex(a),'toBlock':hex(z)}])
   page['count']=len(logs);page['status']='OK'
   for e in logs:
    item={'tx':e['transactionHash'],'block':int(e['blockNumber'],16),'log_index':int(e['logIndex'],16),'topics':e['topics']}
    if len(e['topics'])==3 and len(words(e['data']))==5:
     w=words(e['data']);item.update(keeper='0x'+e['topics'][2][-40:],bounty0_raw=w[2],bounty1_raw=w[3])
    else:item['decode_error']='signature/topics mismatch'
    k['events'].append(item)
  except Exception as e:page.update(status='UNRESOLVED',error=repr(e))
  save()
  if 'RH' in DENIED:break
 k['count']=len(k['events']);k['complete']=all(p.get('status')=='OK' for p in k['pages']) and len(k['pages'])==10
 k['cash_valuation']='UNRESOLVED: tokens, decimals, gas and own current eligibility not yet checked'
if __name__=='__main__':
 for fn in [frax,kerf]:
  try:fn()
  except Exception as e:OUT['errors'].append({'arm':fn.__name__,'error':repr(e),'trace':traceback.format_exc()})
  save()
 OUT['request_count']=COUNTS;OUT['denied_hosts']=sorted(DENIED);save()
 print(json.dumps({'frax_states':len(OUT['observations']),'keeper_events':OUT['keeper'].get('count'), 'errors':OUT['errors'],'requests':COUNTS},default=str))
