"""Historical Compound Comet USDC/WETH absorb + buy winner cash accounting.
Read-only original receipt and call trace; no fabricated liquidity or trade.
"""
import collections,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage1_followup'))
import study as S
OUT=Path('comet_winner_evidence');OUT.mkdir(exist_ok=True)
MARKET='0xc3d688b66703497daa19211eedff47f25384cdc3'
USDC='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
WETH='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
TX='0x9a710e9b980957f1418a3578d6601b5e85e4ef0784c42e97cdbf7fe864bd9a4a'
BLOCK=25984761
ABS=S.topic('AbsorbCollateral(address,address,address,uint256,uint256)')
BUY=S.topic('BuyCollateral(address,address,uint256,uint256)')
def save(r):S.write(OUT,'REPORT.json',r)
def asint(x):return int(x,16) if isinstance(x,str) and x.startswith('0x') else int(x)
def decoded(log):
 t=log['topics'];v=S.words(log['data'])
 if log['address'].lower()!=MARKET:return None
 if t[0].lower()==BUY and len(t)==3 and len(v)==2:
  return {'type':'buy','buyer':S.address(t[1]),'asset':S.address(t[2]),'base_raw':v[0],'collateral_raw':v[1]}
 if t[0].lower()==ABS and len(t)==4 and len(v)==2:
  return {'type':'absorb','absorber':S.address(t[1]),'borrower':S.address(t[2]),'asset':S.address(t[3]),
          'collateral_raw':v[0],'usd_value_raw':v[1]}
 return None
def transfers(receipt):
 rows=[]
 for l in receipt['logs']:
  if l['address'].lower() not in (USDC,WETH) or not l.get('topics'):continue
  if l['topics'][0].lower()!=S.TRANSFER or len(l['topics'])!=3:continue
  rows.append({'token':l['address'].lower(),'from':S.address(l['topics'][1]),
               'to':S.address(l['topics'][2]),'value_raw':str(S.scalar(l['data'])),
               'log_index':asint(l['logIndex'])})
 return rows
def balances(rows,participants):
 return {p:{token:sum(int(t['value_raw'])*(int(t['to']==p)-int(t['from']==p))
       for t in rows if t['token']==token) for token in (USDC,WETH)} for p in participants}
def coinbase_transfers(trace,coinbase):
 result=[];stack=[trace]
 while stack:
  n=stack.pop()
  if not isinstance(n,dict):continue
  typ=n.get('type','').upper();to=n.get('to','').lower()
  amount=asint(n.get('value','0x0'))
  if to==coinbase.lower() and typ not in ('DELEGATECALL','STATICCALL') and amount>0:
   result.append({'type':typ,'native_value_wei':str(amount),'from':n.get('from'),'to':to})
  stack.extend(n.get('calls') or [])
 return result
def main():
 report={'scope':'Original 2026-09 historical Comet USDC market absorb+buy, before costs gross quote ~406 USDC',
   'selected_from':'Already completed actual BuyCollateral event census, before this trace',
   'actual_user_profit_unverified':True,'original_winner_no_owner_assumption':True,
   'hypothetical_quote_is_not_terminal_cash':True,'no_trading_signatures_or_state_override':True}
 save(report)
 c=S.Client(OUT)
 try:
  S.ALLOWED.update({'eth_getTransactionByHash','debug_traceTransaction'})
  assert int(c.rpc(1,'chain','eth_chainId',[]),16)==1
  h=c.rpc(1,'block','eth_getBlockByNumber',[hex(BLOCK),False])
  r=c.rpc(1,'receipt','eth_getTransactionReceipt',[TX])
  tx=c.rpc(1,'original_tx','eth_getTransactionByHash',[TX])
  if not r or r.get('status')!='0x1' or int(r['blockNumber'],16)!=BLOCK or tx.get('hash','').lower()!=TX:
   raise ValueError('Canonical winner transaction mismatch')
  ev=[decoded(l) for l in r['logs']];ev=[x for x in ev if x]
  ab=[x for x in ev if x['type']=='absorb'];bu=[x for x in ev if x['type']=='buy']
  if len(ab)!=1 or len(bu)!=1 or ab[0]['asset']!=WETH or bu[0]['asset']!=WETH or ab[0]['absorber']!=bu[0]['buyer']:
   raise ValueError('Not one same-executor absorb/buy')
  if bu[0]['base_raw']!=9346567826 or bu[0]['collateral_raw']!=4138078068736368148:
   raise ValueError('Unexpected original economic event, abort')
  row=transfers(r)
  participants={bu[0]['buyer'],tx['from'].lower(),tx['to'].lower(),MARKET,h.get('miner','').lower()}
  report.update(original_tx=TX,block=BLOCK,block_hash=h['hash'],chain_id=1,
     original_event_pair=ev,original_sender=tx['from'],original_target=tx['to'],
     transaction_gas_used=asint(r['gasUsed']),effective_gas_price_wei=asint(r['effectiveGasPrice']),
     block_base_fee_wei=asint(h['baseFeePerGas']),recorded_receipt_transfers=row,
     participant_deltas_raw=balances(row,participants),
     onchain_usdc_to_market_raw=str(sum(int(t['value_raw']) for t in row if t['token']==USDC and t['to']==MARKET)),
     onchain_weth_from_market_raw=str(sum(int(t['value_raw']) for t in row if t['token']==WETH and t['from']==MARKET)),
     priority_gas_wei=str(asint(r['gasUsed'])*max(0,asint(r['effectiveGasPrice'])-asint(h['baseFeePerGas']))),
     total_transaction_gas_wei=str(asint(r['gasUsed'])*asint(r['effectiveGasPrice'])),
     gross_quote_from_prior_study_usdc_raw='406016571',gross_quote_fee=500)
  save(report)
  # Trace is secondary; receipt/transfer proof remains even when rate-limited.
  time.sleep(4)
  try:
   trace=c.rpc(1,'original_winner_trace','debug_traceTransaction',[TX,
       {'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True}}])
   S.write(OUT,'ORIGINAL_CALL_TRACE.json',trace)
   if asint(trace.get('gasUsed',0))!=asint(r['gasUsed']):
    raise ValueError('Trace gas mismatch')
   coinbase=h.get('miner','').lower()
   native=coinbase_transfers(trace,coinbase)
   report.update(trace_verified=True,producer_direct_native_transfers=native,
      producer_total_visible_wei=str(sum(int(x['native_value_wei']) for x in native)+int(report['priority_gas_wei'])))
  except Exception as exc:report['trace_error']=repr(exc)
  report['receipt_cash_accounting_complete']=True
 except Exception as exc:report['error']=repr(exc);report['traceback']=traceback.format_exc()
 report['requests']=c.n;report['denied']=sorted(c.denied)
 save(report)
 print(json.dumps({'receipt_complete':report.get('receipt_cash_accounting_complete',False),
  'buyer':report.get('original_event_pair',[{},{}])[-1].get('buyer'),
  'trace_verified':report.get('trace_verified',False),
  'producer_total_visible_wei':report.get('producer_total_visible_wei'),
  'error':report.get('error'),'trace_error':report.get('trace_error')},indent=2),flush=True)
 if not report.get('receipt_cash_accounting_complete'):raise SystemExit('Unresolved receipt; raw evidence retained')
if __name__=='__main__':main()
