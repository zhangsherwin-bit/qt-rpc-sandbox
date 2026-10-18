"""Read-only Morpho Blue USD3 and yoETH health/funding truth test.
Uses actual onchain MarketParams, storage and an *unfunded eth_call* to
liquidate one share. A revert before the repayment pull is an eligibility
diagnostic, NOT an executed liquidation, payout or potential right to profit.
No signatures, keys, blockchain writes, wallets, state overrides or trades.
"""
import json,hashlib,datetime,time,re,traceback,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from Crypto.Hash import keccak
OUT=Path('onchain_health_evidence');OUT.mkdir(exist_ok=True)
CORE='0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb'
RPC={1:'https://ethereum-rpc.publicnode.com',8453:'https://base-rpc.publicnode.com'}
MARKETS=[
 dict(name='USD3_USDC_Ethereum',chain=1,id='0xe3df58f9d3011b7481ff36b939fa5f8da642f34ea5792d25d3958dbf1efa26d7',
 loan='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',collateral='0x056b269eb1f75477a8666ae8c7fe01b64dd55ecc',
 borrowers=['0x0a907c7ce498b6a1d1dc42dad1acbd97d96392e8','0x2385233abb910357e2b97a16d40e0443e53d0769','0xaa34d20be3f9623ccf5bff53ef4dfa765c3f5dd5']),
 dict(name='yoETH_WETH_Base',chain=8453,id='0x94f344f8db8c950faa45206c269dd0c2787a86ae3a7b988423e1e6e8173ae269',
 loan='0x4200000000000000000000000000000000000006',collateral='0x3a43aec53490cb9fa922847385d82fe25d0e9de7',
 borrowers=['0x081ea40e753cd6c8cb2b03d52798999691b85299','0xd03e53428041c22195a29bdc5413ad10f728d94e','0xecf1df76136fc42d512400027538f1c233ace8a1'])]
SENDER='0x000000000000000000000000000000000000dead'
MAX=85;CNT=0;BLOCKED=set();START=time.monotonic()
def save(name,v):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,sort_keys=True,default=str)+'\n')
def w(n):return format(int(n),'064x')
def aw(addr):
 if not re.fullmatch('0x[0-9a-f]{40}',addr):raise ValueError('Bad address')
 return addr[2:].zfill(64)
def selector(name):
 k=keccak.new(digest_bits=256);k.update(name.encode())
 return '0x'+k.hexdigest()[:8]
def rpc(chain,name,method,params):
 global CNT
 if method not in ('eth_chainId','eth_getBlockByNumber','eth_call'):raise ValueError('Read only')
 host=urllib.parse.urlsplit(RPC[chain]).netloc
 if host in BLOCKED:raise RuntimeError('Provider denied; do not retry host')
 if CNT>=MAX or time.monotonic()-START>800:raise RuntimeError('Read budget exhausted')
 if CNT:time.sleep(0.8)
 CNT+=1;body=b'';meta={'name':name,'chain':chain,'url':RPC[chain],'method':method,'id':CNT}
 try:
  payload={'jsonrpc':'2.0','id':CNT,'method':method,'params':params}
  req=urllib.request.Request(RPC[chain],data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','User-Agent':'QT-Stage1-Unfunded-ViewOnly'})
  with urllib.request.urlopen(req,timeout=25) as r:body=r.read(1_200_001);meta['http_status']=r.status
  if len(body)>1_200_000:raise ValueError('Body cap')
  res=json.loads(body)
  if 'error' in res:
   e=res['error'];meta['rpc_error']=e
   if any(q in str(e).lower() for q in ('rate limit','too many','client adjustable limit','unauthorized','access denied')):BLOCKED.add(host)
   return {'_rpc_error':e}
  if 'result' not in res:raise ValueError('No RPC result')
  meta['status']='OK';return res['result']
 except urllib.error.HTTPError as e:
  body=e.read(100000);meta.update(http_status=e.code,error=str(e))
  if e.code in (401,403,429):BLOCKED.add(host)
  raise
 except Exception as e:meta['error']=repr(e);raise
 finally:
  meta.update(sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
  save('requests/'+str(CNT).zfill(3)+'.json',meta)
  (OUT/'raw').mkdir(parents=True,exist_ok=True)
  (OUT/f'raw/{CNT:03d}.body').write_bytes(body)
def read_call(chain,to,data,block,name):
 ret=rpc(chain,name,'eth_call',[{'to':to,'data':data},hex(block)])
 if isinstance(ret,dict) and '_rpc_error' in ret:raise RuntimeError('view RPC error '+str(ret['_rpc_error']))
 if not isinstance(ret,str) or not ret.startswith('0x'):raise ValueError('Invalid eth_call return')
 return ret
def decode(ret,count):
 if len(ret)!=2+64*count:raise ValueError('Unexpected onchain ABI layout')
 return [int(ret[2+64*i:2+64*(i+1)],16) for i in range(count)]
def liquidate_probe(chain,market,params,user,block):
 # Morpho liquidate((address,address,address,address,uint256),address,uint256,uint256,bytes)
 # static head 9 * 32-byte values, followed by empty dynamic bytes.
 data=selector('liquidate((address,address,address,address,uint256),address,uint256,uint256,bytes)')
 data+=''.join(w(x) for x in params)+aw(user)+w(0)+w(1)+w(288)+w(0)
 tx={'from':SENDER,'to':CORE,'data':data,'gas':'0x989680','gasPrice':'0x0'}
 ret=rpc(chain,'unfunded_liquidate_one_share','eth_call',[tx,hex(block)])
 if isinstance(ret,dict) and '_rpc_error' in ret:
  err=ret['_rpc_error'];msg=str(err.get('message',''))
  payload=str(err.get('data') or '')
  if 'position is healthy' in msg.lower() or '706f736974696f6e206973206865616c746879' in payload.lower():
   return {'status':'HEALTHY_REVERT_EXACT','message':msg[:350],'no_write_or_payment':True}
  return {'status':'REVERT_OTHER_UNCLASSIFIED','message':msg[:350],'error_data':payload[:420],'no_write_or_payment':True}
 return {'status':'UNFUNDED_CALL_RETURNED','result':str(ret)[:200],
         'note':'Unexpected call return; never infer actual funds paid','no_write_or_payment':True}
def main():
 report={'scope':'Exact USD3 and yoETH borrower positions and read-only liquidation eligibility at pinned state',
 'historical_payout_executed':False,'signed_or_sent_transactions':False,'any_real_cash_profit':False,
 'no_sender_funding':True,'markets':[],'errors':[],'complete':False}
 save('REPORT.json',report)
 try:
  for m in MARKETS:
   chain=m['chain']
   if int(rpc(chain,'network','eth_chainId',[]),16)!=chain:raise ValueError('Unexpected chain ID')
   h=rpc(chain,'block_pin','eth_getBlockByNumber',['latest',False]);bn=int(h['number'],16)
   x={**m,'block':bn,'block_hash':h['hash'],'borrower_results':[]}
   report['markets'].append(x);save('REPORT.json',report)
   params=decode(read_call(chain,CORE,selector('idToMarketParams(bytes32)')+m['id'][2:],bn,'verify_market_params'),5)
   p_addrs=['0x'+format(z,'040x') for z in params[:4]]
   assert p_addrs[0]==m['loan'] and p_addrs[1]==m['collateral']
   x['verified_market_params']={'loan':p_addrs[0],'collateral':p_addrs[1],'oracle':p_addrs[2],'irm':p_addrs[3],'lltv_wad':str(params[4])}
   market=decode(read_call(chain,CORE,selector('market(bytes32)')+m['id'][2:],bn,'market_balance_snapshot'),6)
   x['market_snapshot']={'total_borrow_assets_raw':str(market[2]),'total_borrow_shares_raw':str(market[3]),
      'last_update':market[4]}
   if market[3]==0:raise ValueError('No actual borrow shares')
   for user in m['borrowers']:
    row={'user':user}
    x['borrower_results'].append(row);save('REPORT.json',report)
    try:
     pos=decode(read_call(chain,CORE,selector('position(bytes32,address)')+m['id'][2:]+aw(user),bn,'borrower_position'),3)
     row['borrow_shares_raw']=str(pos[1]);row['collateral_raw']=str(pos[2])
     row['simple_unaccrued_borrow_assets_raw']=str((pos[1]*market[2]+market[3]-1)//market[3])
     if not pos[1] or not pos[2]:row['eligibility']='ZERO_BALANCE_NOT_ELIGIBLE';continue
     row['read_only_liquidate_probe']=liquidate_probe(chain,m,params,user,bn)
     row['eligibility']=row['read_only_liquidate_probe']['status']
    except Exception as exc:row['eligibility']='UNAVAILABLE';row['error']=repr(exc)
    save('REPORT.json',report)
    if urllib.parse.urlsplit(RPC[chain]).netloc in BLOCKED:raise RuntimeError('Provider refused further calls')
   check=rpc(chain,'canonical_hash_recheck','eth_getBlockByNumber',[h['number'],False])
   if check.get('hash')!=h['hash']:raise ValueError('Reorg / changed pinned state')
   x['verified_canonical_block']=True
  report['complete']=True
 except Exception as exc:report['errors'].append(repr(exc));report['traceback']=traceback.format_exc()
 report['requests']=CNT;report['denied_hosts']=sorted(BLOCKED)
 save('REPORT.json',report)
 print(json.dumps({'complete':report['complete'],'requests':CNT,
  'market_summary':[{'name':m['name'],'borrowers':[(r['user'],r.get('eligibility')) for r in m['borrower_results']]} for m in report['markets']],
  'errors':report['errors']},indent=2),flush=True)
 if not report['complete']:raise SystemExit('Onchain eligibility incomplete; preserve partial evidence')
if __name__=='__main__':main()
