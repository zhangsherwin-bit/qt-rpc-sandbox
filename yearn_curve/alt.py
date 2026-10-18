"""Alternate genuine DOLA Curve and RSUP UniswapV2->Curve cash-exit quotations.
Shares the same SIX preselected real-auction settlement receipts from PR56.
This is read-only historical cash-path SCREENING, not executing an auction buy.
"""
import json,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'yearn_new_exit'))
import screen as S
S.OUT=Path('curve_exit_evidence');S.OUT.mkdir(exist_ok=True)
OUT=S.OUT
REG="0xf98b45fa17de75fb1aD0e7aFD971b0ca00e379fC".lower()
V2FACTORY="0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f"
POOL_USDC_CRVUSD="0x4dece678ceceb27446b35c672dc7d61f30bad69e"
def one_call(addr,method,args,block,label):
    sel=S.h(method)[2:10]
    data="0x"+sel+''.join(S.pad_addr(x) if isinstance(x,str) and x.startswith("0x") else S.enc(x) for x in args)
    ret=S.rpc("eth_call",[{"to":addr,"data":data},hex(block)],label)
    if not isinstance(ret,str) or not ret.startswith("0x") or len(ret)<66:raise ValueError("Invalid ABI response")
    return int(ret[2:66],16)
def pointer(value):
    return "0x"+format(value & (2**160-1),"040x")
def stable_pool(asset,block):
    try:
        raw=one_call(REG,"find_pool_for_coins(address,address,uint256)",[asset,S.CRVUSD,0],block,"Curve registry actual-pair view")
        return pointer(raw) if raw else None
    except Exception:return None
def stable_quote(pool,from_token,to_token,amount,block):
    if amount<=0 or pool=="0x"+"0"*40:raise ValueError("Missing amount/pool")
    if len(S.rpc("eth_getCode",[pool,hex(block)],"verify Curve runtime"))<=4:raise ValueError("Missing historical pool code")
    pair=[]
    for i in (0,1):
        ptr=one_call(pool,"coins(uint256)",[i],block,"Pool coin order")
        pair.append(pointer(ptr))
    if set(pair)!={from_token.lower(),to_token.lower()}:
        raise ValueError("Pool token identities do not match quote")
    i,j=pair.index(from_token.lower()),pair.index(to_token.lower())
    attempts=[]
    for sig in ("get_dy(int128,int128,uint256)","get_dy(uint256,uint256,uint256)"):
        try:
            res=one_call(pool,sig,[i,j,amount],block,"Canonical finite Curve cash view")
            return dict(output=res,signature=sig,pair=pair)
        except Exception as exc:attempts.append(str(exc)[:180])
    raise ValueError("Curve pool get_dy failed: "+str(attempts))
def univ2_rsup_to_weth(block,amount):
    factory=V2FACTORY.lower()
    pair=pointer(one_call(factory,"getPair(address,address)",[S.RSUP,S.WETH],block,"UniV2 RSUP-WETH pool search"))
    if pair=="0x"+"0"*40:raise ValueError("No UniV2 RSUP-WETH pool at this date")
    if len(S.rpc("eth_getCode",[pair,hex(block)],"Verify V2 deployed"))<=4:raise ValueError("V2 pool no code")
    token0=pointer(one_call(pair,"token0()",[],block,"V2 token0"))
    token1=pointer(one_call(pair,"token1()",[],block,"V2 token1"))
    if {token0,token1}!={S.RSUP,S.WETH}:raise ValueError("Pair mismatch")
    res=S.rpc("eth_call",[{"to":pair,"data":S.h("getReserves()")[:10]},hex(block)],"V2 exact historic reserves")
    w=[int(res[2+i:2+i+64],16) for i in range(0,192,64)]
    a,b=(w[0],w[1]) if token0==S.RSUP else (w[1],w[0])
    if a<=0 or b<=0:raise ValueError("zero reserve")
    out=(amount*997*b)//(a*1000+amount*997)
    if out==0:raise ValueError("less than one wei")
    return dict(pair=pair,token0=token0,reserve_input=a,reserve_output=b,
        weth_quoted=out,formula="UniswapV2 x*y fee 0.30%, NOT a complete execution; token transfer fees untested")
def do():
  rep={"scope":"Existing six RSUP/DOLA settled Yearn auctions; historical Curve and UniswapV2 alternative liquidity only",
      "research_only":True,"actual_trade_settled":False,
      "source":"Already complete PR56 receipt and payment ledger, unchanged six selected transactions",
      "warnings":["Historical Curve get_dy quotes and V2 reserve arithmetic are not cash-execution results.",
         "Registry does not guarantee full/in-time quote availability; missing is not zero.",
         "V2 quote assumes exact-input balance; fee-on-transfer and router overhead are not tested.",
         "No winning producer payment, gas or capital costs in indicative cash margin."],
      "cases":[],"complete":False}
  S.save('REPORT.json',rep)
  try:
    saved=json.loads(Path('input_quotes/yearn_exit_evidence/REPORT.json').read_text())
    cases=saved['cases']
    if len(cases)!=6 or not saved['complete'] or not all(x.get('receipt_checked') for x in cases):
        raise ValueError("Frozen baseline receipts missing")
    if S.rpc("eth_chainId",[],"Ethereum chain check")!="0x1":raise ValueError("wrong chain")
    for x in cases:
        o=dict(asset=x['asset'],tx=x['tx'],block=x['block'],sold_raw=x['sold_raw'],paid_raw=x['payment_raw'],outcomes=[])
        rep['cases'].append(o);S.save('REPORT.json',rep)
        blk=x['block']-1;sold=int(x['sold_raw']);paid=int(x['payment_raw'])
        def record(route,f):
            try:
                val=f()
                if isinstance(val,dict):
                    qty=int(val['output']);more={k:v for k,v in val.items() if k!='output'}
                else:qty=int(val);more={}
                o['outcomes'].append({"route":route,"quoted_out_crvusd_raw":str(qty),
                    "gross_crvusd_margin_raw":str(qty-paid),"positive_before_cost":qty>paid,"details":more})
            except Exception as e:o['outcomes'].append({"route":route,"error":repr(e)})
            S.save('REPORT.json',rep)
        pool=stable_pool(x['token'],blk)
        if pool:
            record("CURVE_DIRECT",lambda pool=pool:stable_quote(pool,x['token'],S.CRVUSD,sold,blk))
        else:o['outcomes'].append({"route":"CURVE_DIRECT","error":"No historical registered pool"})
        if x['asset']=="DOLA":
            # alternate shallow DOLA/uniswapV3 USDC leg followed by stable deep crvUSD/USDC pool
            for fee in (500,3000):
                def dola_bridge(fee=fee):
                    q=S.quote(S.DOLA,S.USDC,sold,fee,blk)
                    got=stable_quote(POOL_USDC_CRVUSD,S.USDC,S.CRVUSD,q,blk)
                    return {"output":got['output'],"first_leg_usdc_raw":q,"pool":POOL_USDC_CRVUSD}
                record(f"DOLA_UNIV3_USDC_FEE_{fee}_CURVE_CRVUSD",dola_bridge)
        if x['asset']=="RSUP":
            try:
                v=univ2_rsup_to_weth(blk,sold);o['univ2']=v
                for fee in (500,3000):
                    def rsup_path(fee=fee):
                        usdc=S.quote(S.WETH,S.USDC,v['weth_quoted'],fee,blk)
                        out=stable_quote(POOL_USDC_CRVUSD,S.USDC,S.CRVUSD,usdc,blk)
                        return {"output":out['output'],"weth_raw":v['weth_quoted'],"usdc_raw":usdc}
                    record(f"RSUP_UNIV2_WETH_UNIV3_{fee}_CURVE_CRVUSD",rsup_path)
            except Exception as exc:o['univ2_error']=repr(exc)
        vals=[int(v['gross_crvusd_margin_raw']) for v in o['outcomes'] if "gross_crvusd_margin_raw" in v]
        o['best_margin_raw']=str(max(vals)) if vals else None
        S.save('REPORT.json',rep)
        if S.STOP:raise RuntimeError("Provider denial: stop")
    rep['complete']=True
  except Exception as e:
    rep['exception']=repr(e);rep['traceback']=traceback.format_exc()
  rep['requests']=S.REQUESTS;rep['provider_stopped']=S.STOP
  S.save('REPORT.json',rep)
  print(json.dumps({"complete":rep['complete'],"requests":S.REQUESTS,
      "cases":[{"asset":c['asset'],"best_margin_raw":c.get('best_margin_raw'),
      "nonmissing":sum('gross_crvusd_margin_raw' in v for v in c['outcomes'])} for c in rep['cases']],
      "exception":rep.get('exception')},indent=2),flush=True)
  if not rep['complete']:raise SystemExit("Partial alternate-venue study, preserve errors")
if __name__=="__main__":do()
