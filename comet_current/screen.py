"""Eleven already verified Compound III deployments: current collateral-sale inventory.
Read-only one-snapshot finite-size quote screen, not completed settlement/profit.
"""
import sys,json,hashlib,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"stage1_followup"))
import study as S
OUT=Path("live_inventory_evidence");OUT.mkdir(exist_ok=True)
SPOKES={
1:{"USDC":"0xc3d688b66703497daa19211eedff47f25384cdc3","USDS":"0x5d409e56d886231adaf00c8775665ad0f9897b56",
 "USDT":"0x3afdc9bca9213a35503b077a6072f3d0d5ab0840","WBTC":"0xe85dc543813b8c2cfeaac371517b925a166a9293",
 "WETH":"0xa17581a9e3356d9a858b789d68b4d866e593ae94","wstETH":"0x3d0bb1ccab520a66e607822fc55bc921738fafe3"},
8453:{"AERO":"0x784efeb622244d2348d4f2522f8860b96fbece89","USDbC":"0x9c4ec768c28520b50860ea7a15bd7213a9ff58bf",
 "USDC":"0xb125e6687d4313864e53df431d5425969c15eb2f","USDS":"0x2c776041ccfe903071af44aa147368a9c8eea518",
 "WETH":"0x46e6b214b524310239732d51387075e0e70970bf"}}
QUOTER={1:"0x61ffe014ba17989e743c5f6cb21bf9697530b21e",8453:"0x3d4e44eb1374240ce5f1b871ab261cd16335b76a"}
def save(x):S.write(OUT,"REPORT.json",x)
def call(c,ch,to,sig,args,block,signed=False):return c.call(ch,to,sig,args,block,signed)
def choose_size(label,scale):
 if label in ("WETH","wstETH"):return [scale//10,scale,scale*10]
 if label=="WBTC":return [max(1,scale//100),max(1,scale//10),scale]
 return [100*scale,1000*scale,10000*scale]
def market(c,ch,label,addr,block):
 row={"chain":ch,"label":label,"comet":addr,"block":block,"complete":False,"assets":[]}
 try:
  contract=c.rpc(ch,"deployed_code","eth_getCode",[addr,hex(block)])
  if not isinstance(contract,str) or len(contract)<20:raise ValueError("Market lacks deployed runtime")
  base=S.address(call(c,ch,addr,"baseToken()",[],block))
  scale=call(c,ch,addr,"baseScale()",[],block)
  reserve=call(c,ch,addr,"getReserves()",[],block,signed=True)
  target=call(c,ch,addr,"targetReserves()",[],block)
  pause=call(c,ch,addr,"isBuyPaused()",[],block)
  count=call(c,ch,addr,"numAssets()",[],block)
  if not 1<=count<=20:raise ValueError("Unexpected collateral count")
  gate=reserve<target and pause==0
  row.update(base_token=base,base_scale=scale,reserves_raw=str(reserve),
    target_reserves_raw=str(target),buy_paused=bool(pause),sale_gate_open=gate,
    assets_count=count)
  for i in range(count):
   a={"index":i,"errors":[]};row["assets"].append(a)
   try:
    dat=S.selector("getAssetInfo(uint8)")+S.enc(i)
    info=S.words(c.rpc(ch,"asset_config","eth_call",[{"to":addr,"data":dat},hex(block)]))
    if len(info)!=8:raise ValueError("Comet asset info ABI mismatch")
    token=S.address(info[1])
    reserve_token=call(c,ch,addr,"getCollateralReserves(address)",[token],block)
    a.update(token=token,inventory_raw=str(reserve_token),scale=str(info[3]),gross_quote_candidates=[])
    if not gate or reserve_token<=0:continue
    for qty in choose_size(label,scale):
     q={"base_spend_raw":str(qty),"quote_only":True,"complete_cash_execution":False,"dex":[]}
     a["gross_quote_candidates"].append(q)
     try:
      units=call(c,ch,addr,"quoteCollateral(address,uint256)",[token,qty],block)
      q["purchased_collateral_raw"]=str(units)
      if units<=0 or units>reserve_token:
       q["inventory_fits"]=False
       continue
      q["inventory_fits"]=True
      for fee in (100,500,3000):
       d={"fee_tier":fee};q["dex"].append(d)
       try:
        data=S.selector("quoteExactInputSingle((address,address,uint256,uint24,uint160))")
        data+="".join(S.enc(v) for v in (token,base,units,fee,0))
        out=S.words(c.rpc(ch,"exit_quote","eth_call",[{"to":QUOTER[ch],"data":data},hex(block)]))
        if len(out)!=4:raise ValueError("QuoterV2 ABI mismatch")
        d.update(output_base_raw=str(out[0]),gross_margin_base_raw=str(out[0]-qty),
          positive_gross=out[0]>qty,
          warning="No flash repayment, producer bid, gas or exact swap execution proved")
       except Exception as e:d["error"]=repr(e)
     except Exception as e:q["error"]=repr(e)
  row["gross_positive_quote_cases"]=sum(bool(z.get("positive_gross")) for a in row["assets"] for q in a.get("gross_quote_candidates",[]) for z in q.get("dex",[]))
  row["complete"]=True
 except Exception as e:row["error"]=repr(e)
 return row
def main():
 r={"scope":"One latest-block pin on 11 deployed Compound III markets Ethereum+Base",
  "not_historical_event_frequency":True,"no_execution_or_income":True,
  "risks":["Free public RPC rate limit on Base","Quoter price-limit partial consumption cannot be treated as a full loss",
   "One block snapshot does not prove continuity or capture","Generic role may lack approvals if used for execution"],
  "chains":{},"markets":[],"complete":False}
 save(r);c=S.Client(OUT)
 try:
  for ch in (1,8453):
   scope={"chain":ch,"complete":False}
   r["chains"][str(ch)]=scope;save(r)
   try:
    if int(c.rpc(ch,"network_id","eth_chainId",[]),16)!=ch:raise ValueError("Wrong network")
    head=c.rpc(ch,"snapshot_header","eth_getBlockByNumber",["latest",False])
    bn=int(head["number"],16);scope.update(block=bn,hash=head["hash"])
    for label,addr in SPOKES[ch].items():
     row=market(c,ch,label,addr,bn)
     r["markets"].append(row);save(r)
     if ch in c.denied:raise RuntimeError("Provider refused; no repeated calls")
    check=c.rpc(ch,"recheck_hash","eth_getBlockByNumber",[hex(bn),False])
    if check["hash"]!=head["hash"]:raise ValueError("Block reorg")
    scope["complete"]=all(z["complete"] for z in r["markets"] if z["chain"]==ch)
   except Exception as e:scope["error"]=repr(e)
   save(r)
  r["complete"]=all(r["chains"].get(str(ch),{}).get("complete") for ch in SPOKES)
 except Exception as e:r["error"]=repr(e);r["traceback"]=traceback.format_exc()
 r["requests"]=c.n;r["provider_denied_chains"]=sorted(c.denied)
 r["gross_positive_observed"]=sum(z.get("gross_positive_quote_cases",0) for z in r["markets"])
 save(r)
 print(json.dumps({"complete":r["complete"],"n_markets":len(r["markets"]),
    "gross_positive_quotes":r["gross_positive_observed"],"requests":r["requests"],
    "denied":r["provider_denied_chains"],"errors":[z.get("error") for z in r["markets"] if z.get("error")]},indent=2),flush=True)
 if not r["complete"]:raise SystemExit("Scope partially unavailable; use saved artifact, never assume no inventory")
if __name__=="__main__":main()
