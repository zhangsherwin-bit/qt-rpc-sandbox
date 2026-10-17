"""Exact transaction-index cash execution; no funding/storage/oracle overrides.
The original call must reproduce canonical status, gas and complete log multiset
before the research call is accepted. This avoids replaying hundreds of calls in
one eth_simulateV1 request. All provider limits and failures remain recorded.
"""
import sys,pathlib,json,time,collections,traceback
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import execute as D
C=D.C;OUT=D.OUT
REG='0xf949982b91c8c61e952b3ba942cbbfaef5386684'

def prepare():
 p=pathlib.Path('angles_probe/CashProbe.sol');s=p.read_text()
 marker='interface Liquidator {function batchLiquidateTroves(uint[] calldata) external;function collToken() external view returns(address);}'
 assert s.count(marker)==1
 s=s.replace(marker,marker+'\ninterface Registry {function totalCollaterals() external view returns(uint);function getToken(uint) external view returns(address);function getTroveManager(uint) external view returns(address);}')
 old='address c=Liquidator(j.target).collToken();';assert s.count(old)==1;s=s.replace(old,'address c=collateralOf(j.target);')
 pos=' bool busy;';assert s.count(pos)==1;s=s.replace(pos,' uint producerPayment;\n'+pos)
 old='busy=true;';assert s.count(old)==1;s=s.replace(old,'busy=true;producerPayment=(j.kind==1||j.kind==2)?j.amount:0;')
 old='token=c;paid=payout(c);';assert s.count(old)==1
 new='if(j.mode==1){uint n=balance(c);approve(c,ROUTER,n);Router(ROUTER).exactInputSingle(Router.ExactInputSingleParams(c,WETH,500,address(this),block.timestamp,n,0,0));require(balance(c)==0,"stable residue");token=WETH;paid=payout(WETH);}else{require(producerPayment==0,"native payment needs native cash");token=c;paid=payout(c);}'
 s=s.replace(old,new)
 old='Wrapped(WETH).withdraw(n);(bool ok,)=BENEFICIARY.call{value:n}("");';assert s.count(old)==1
 new='Wrapped(WETH).withdraw(n);uint bid=producerPayment;if(n<=bid)revert CashShortfall(n,bid);if(bid>0){(bool sent,)=block.coinbase.call{value:bid}("");require(sent,"producer payment");n-=bid;}producerPayment=0;(bool ok,)=BENEFICIARY.call{value:n}("");'
 s=s.replace(old,new)
 extra='''
 function collateralOf(address tm) internal view returns(address){Registry r=Registry(address(bytes20(hex"f949982b91c8c61e952b3ba942cbbfaef5386684")));uint count=r.totalCollaterals();require(count<=16,"registry cap");for(uint i;i<count;i++)if(r.getTroveManager(i)==tm)return r.getToken(i);revert("unknown manager");}
 function checkedExecute(Job calldata j,uint number,uint stamp,uint base) external returns(address,uint){require(msg.sender==BENEFICIARY,"checked caller");require(block.chainid==1&&block.number==number&&block.timestamp==stamp&&block.basefee==base,"header mismatch");require(BENEFICIARY.balance==0&&address(this).balance==0&&balance(WETH)==0&&balance(STETH)==0&&balance(USDC)==0&&balance(USDT)==0,"initial balance");return this.execute(j);}
'''
 s=s.rstrip();assert s.endswith('}');s=s[:-1]+extra+'}\n';p.write_text(s)
 return D.compile_probe()

class R(D.Runner):
 def rpc(self,name,method,params):
  if method=='debug_traceCall':time.sleep(max(0,70-(time.monotonic()-self.last)));self.heavy+=1
  return super().rpc(name,method,params)

def logbag(c):
 if c.get('error'):return []
 out=[(x.get('address',c.get('to','')).lower(),tuple(t.lower() for t in x['topics']),x['data'].lower()) for x in c.get('logs',[])]
 for child in c.get('calls',[]):out+=logbag(child)
 return out

def native_to(c,recipient):
 if c.get('error'):return 0
 frm=c.get('from','').lower();to=c.get('to','').lower();n=int(c.get('value','0x0'),16)
 v=(n if to==recipient and frm!=recipient else 0)-(n if frm==recipient and to!=recipient else 0)
 return v+sum(native_to(x,recipient) for x in c.get('calls',[]))

def run():
 OUT.mkdir(exist_ok=True);s={'stage':'calibrated_native_cash_services','new_remote_run':True,'signed_or_sent':0,'cases':[],'counting':'retrospective first/middle/last events; alternatives not additive income'}
 try:
  r=R();C.ALLOWED.update({'debug_traceCall','debug_traceTransaction','eth_getTransactionByHash'});runtime=prepare()
  events=D.load('keeper_events.json');rows=sorted({x['transactionHash']:x for x in events if x['address'].lower()==C.KEEPERS[1]}.values(),key=lambda x:(int(x['blockNumber'],16),int(x['transactionIndex'],16)))
  selected=[rows[i] for i in sorted(set([0,len(rows)//2,len(rows)-1]))] if rows else []
  C.save('TRACE_PLAN.json',{'selection':selected,'quote_or_model_only':False,'comparison':'real native payout; separately matching incumbent full visible direct+priority compensation','calibration':'original transaction must match canonical gas/status and log multiset; no inferred txIndex convention','block_context':'canonical block; explicitly verified inside checkedExecute; code-only research override'})
  for k,e in enumerate(selected):
   d={'tx':e['transactionHash'],'index':int(e['transactionIndex'],16)}
   try:
    rec=r.getreceipt(e['transactionHash']);tx=r.rpc('original_transaction','eth_getTransactionByHash',[e['transactionHash']]);n=int(rec['blockNumber'],16);h=r.head(n)
    assert rec['blockHash']==h['hash']==tx['blockHash'];d['header']=h;d['receipt']=rec
    # Fixed effective price reproduces GASPRICE and native fees without sending mixed fee fields.
    orig={x:tx[x] for x in ['from','to','value','gas','accessList','authorizationList'] if tx.get(x) is not None};orig.update(input=tx['input'],gasPrice=rec['effectiveGasPrice'])
    config={'tracer':'callTracer','timeout':'30s','tracerConfig':{'withLog':True},'txIndex':d['index']}
    tr=r.rpc('original_index_calibration','debug_traceCall',[orig,hex(n),config]);C.save('traces/original_%s.json'%k,tr)
    expect=collections.Counter((x['address'].lower(),tuple(t.lower() for t in x['topics']),x['data'].lower()) for x in rec['logs'])
    d['calibration']={'success':not tr.get('error') and rec['status']=='0x1','gas_matches':int(tr.get('gasUsed','0x0'),16)==int(rec['gasUsed'],16),'log_multiset_matches':collections.Counter(logbag(tr))==expect}
    if not all(d['calibration'].values()):raise ValueError('transaction-index calibration failed; not a profitability observation')
    pay=native_to(tr,h['miner'].lower());tip=int(rec['gasUsed'],16)*(int(rec['effectiveGasPrice'],16)-int(h['baseFeePerGas'],16));bid=pay+tip
    d.update(original_direct_producer_wei=str(pay),original_priority_fee_wei=str(tip),equal_visible_compensation_wei=str(bid),results=[])
    for label,amount,index in [('no_bid',0,d['index']),('equal_visible_compensation',bid,d['index']),('after_original_control',0,d['index']+1)]:
     j=(1,C.KEEPERS[1],[],amount,1,b'');data=C.calldata('checkedExecute('+D.JOB+',uint256,uint256,uint256)',[D.JOB,'uint256','uint256','uint256'],[j,n,int(h['timestamp'],16),int(h['baseFeePerGas'],16)])
     call={'from':D.BENEF,'to':D.PROBE,'input':data,'gas':hex(3000000),'gasPrice':'0x0'}
     cfg=dict(config,txIndex=index,stateOverrides={D.PROBE:{'code':runtime}},blockOverrides={'number':h['number'],'time':h['timestamp'],'baseFeePerGas':h['baseFeePerGas'],'feeRecipient':h['miner'],'prevRandao':h['mixHash']})
     rr=r.rpc(label,'debug_traceCall',[call,hex(n),cfg]);C.save('traces/%s_%s.json'%(k,label),rr)
     q={'label':label,'status':'reverted' if rr.get('error') else 'completed','gas_used':int(rr.get('gasUsed','0x0'),16),'error':rr.get('error'),'output':rr.get('output')}
     if not rr.get('error'):
      token,cash=D.decode(['address','uint256'],bytes.fromhex(rr['output'][2:]));assert token==C.WETH and native_to(rr,D.BENEF)==cash and native_to(rr,h['miner'].lower())==amount
      q.update(native_payout_wei=str(cash),actual_producer_payment_wei=str(amount),base_fee_cost_wei=str(q['gas_used']*int(h['baseFeePerGas'],16)),net_after_base_fee_wei=str(cash-q['gas_used']*int(h['baseFeePerGas'],16)),initial_and_terminal_checks_passed=True)
     d['results'].append(q);C.save('SUMMARY.json',s|{'cases':s['cases']+[d]})
   except Exception as exc:d['exception']=repr(exc)
   s['cases'].append(d);C.save('SUMMARY.json',s)
   if r.stopped:raise RuntimeError('provider stopped')
 except Exception as exc:s['exception']=repr(exc);s['traceback']=traceback.format_exc()
 s.update(requests=r.n if 'r' in locals() else 0,heavy_calls=r.heavy if 'r' in locals() else 0);C.save('SUMMARY.json',s);print(json.dumps(s,indent=2),flush=True)
if __name__=='__main__':run()
