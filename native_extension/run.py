"""Read-only contract quote screening; no executor or state-changing transaction."""
import sys,pathlib,json,time,datetime,traceback
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'stage1'))
import public_screen as S
from eth_abi import encode,decode
from Crypto.Hash import keccak
S.OUT=pathlib.Path('native_evidence');S.OUT.mkdir(exist_ok=True)
PLAN=json.loads((pathlib.Path(__file__).parent/'PLAN.json').read_text())
USDC='0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
FEES=(100,500,3000)
def data(sig,types,args):return '0x'+(keccak.new(digest_bits=256,data=sig.encode()).digest()[:4]+encode(types,args)).hex()
def main():
 c=S.Client();report={'plan':PLAN,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'headers':[],'pools':[],'rows':[],'lido_pool_diagnostics':[],'error':None,'new_cash_execution':False};cache={}
 def call(name,to,sig,types,args,h):
  key=(to.lower(),sig,json.dumps(args),h['hash'])
  if key in cache:return cache[key]
  if c.n>=300 or time.monotonic()-c.start>1100:raise RuntimeError('Bounded quote budget reached')
  raw=c.rpc(name,'eth_call',[{'to':to,'data':data(sig,types,args),'gas':hex(1500000),'gasPrice':h['baseFeePerGas']},h['number']]);cache[key]=raw;return raw
 def quote(a,b,fee,n,h):
  v=call('bridge_quote',S.QUOTER,'quoteExactInputSingle((address,address,uint256,uint24,uint160))',['(address,address,uint256,uint24,uint160)'],[(a,b,n,fee,0)],h)
  out=decode(['uint256','uint160','uint32','uint256'],bytes.fromhex(v[2:]))
  return int(out[0])
 def pool(a,b,fee,h):
  v=call('pool_discovery',S.FACTORY,'getPool(address,address,uint24)',['address','address','uint24'],[a,b,fee],h)
  address='0x'+v[-40:];report['pools'].append({'block':int(h['number'],16),'a':a,'b':b,'fee':fee,'address':address});return address
 try:
  assert c.rpc('chain','eth_chainId',[])=='0x1'
  for number,date in zip(PLAN['calendar_blocks'],PLAN['calendar_dates']):
   h=c.rpc('header','eth_getBlockByNumber',[hex(number),False]);p=c.rpc('preceding_header','eth_getBlockByNumber',[hex(number-1),False]);target=int(datetime.datetime.fromisoformat(date).timestamp())
   assert int(p['timestamp'],16)<target<=int(h['timestamp'],16) and h['parentHash']==p['hash'];report['headers'].append(h)
   assert int(call('usdc_decimals',USDC,'decimals()',[],[],h),16)==6
   assert call('converter_dai',S.CONVERTER,'dai()',[],[],h)[-40:].lower()==S.DAI[2:].lower()
   assert call('converter_usds',S.CONVERTER,'usds()',[],[],h)[-40:].lower()==S.USDS[2:].lower()
   for token in (S.DAI,S.USDS):assert int(call('token_decimals',token,'decimals()',[],[],h),16)==18
   available={t:[f for f in FEES if int(pool(t,USDC,f,h),16)>0] for t in (S.DAI,S.USDS)}
   for index,(enter,leave) in enumerate(((S.DAI,S.USDS),(S.USDS,S.DAI))):
    for amount in PLAN['USDC_sizes']:
     n=amount*10**6
     for f1 in available[enter]:
      try:intermediate=quote(USDC,enter,f1,n,h)
      except Exception as e:
       report['rows'].append({'block':number,'direction':index,'input_USDC':amount,'entry_fee':f1,'status':'ENTRY_QUOTE_UNAVAILABLE','error':repr(e)});continue
      for f2 in available[leave]:
       row={'block':number,'timestamp':int(h['timestamp'],16),'hash':h['hash'],'direction':index,'input_USDC':amount,'entry_fee':f1,'exit_fee':f2,'intermediate_raw':str(intermediate),'cash_execution':False}
       try:
        out=quote(leave,USDC,f2,intermediate,h);row.update(status='QUOTE_ONLY',output_raw=str(out),gross_USDC_raw=str(out-n))
       except Exception as e:row.update(status='EXIT_QUOTE_UNAVAILABLE',error=repr(e))
       report['rows'].append(row);S.save('REPORT.json',report)
       if c.blocked:raise RuntimeError('Provider refusal; stopped')
   direct=pool(S.DAI,S.USDS,3000,h)
   if int(direct,16)>0:
    for amount in PLAN['USDC_sizes']:
     for d,(a,b) in enumerate(((S.DAI,S.USDS),(S.USDS,S.DAI))):
      row={'block':number,'family':'DAI_USDS_direct_3000','input_DAI':amount,'direction':d,'cash_execution':False}
      try:out=quote(a,b,3000,amount*10**18,h);row.update(status='QUOTE_ONLY',gross_DAI_raw=str(out-amount*10**18))
      except Exception as e:row.update(status='QUOTE_UNAVAILABLE',error=repr(e))
      report['rows'].append(row)
   lido='0xd340b57aacdd10f96fc1cf10e15921936f41e29c';diag={'block':number,'pool':lido}
   for sig,types,args in [('liquidity()',[],[]),('token0()',[],[]),('token1()',[],[])]:
    try:diag[sig]=call('lido_pool_diagnostic',lido,sig,types,args,h)
    except Exception as e:diag[sig]={'error':repr(e)}
   report['lido_pool_diagnostics'].append(diag);S.save('REPORT.json',report)
 except Exception as e:report.update(error=repr(e),traceback=traceback.format_exc())
 report.update(requests=c.n,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),provider_stopped=bool(c.blocked))
 S.save('REPORT.json',report)
 print(json.dumps({'requests':c.n,'rows':len(report['rows']),'positive_quote_rows':sum(int(x.get('gross_USDC_raw',x.get('gross_DAI_raw','0')))>0 for x in report['rows']),'error':report['error'],'no_cash_execution':True},indent=2))
 if report['error']:raise SystemExit('Incomplete quote research; evidence retained')
if __name__=='__main__':main()
