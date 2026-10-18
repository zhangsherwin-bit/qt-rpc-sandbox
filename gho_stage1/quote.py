"""Read-only historical GHO primary market GSM vs UniV3. Real onchain quotes only.
Gross cash delta is not full EVM execution, net profit, order access or inclusion.
"""
import urllib.request,urllib.error,json,time,hashlib,traceback,datetime
from Crypto.Hash import keccak
from pathlib import Path
OUT=Path("gho_evidence");OUT.mkdir(parents=True,exist_ok=True)
RPC="https://rpc-eth.blockmachine.io"
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
GHO="0x40d16fc0246ad3160ccc09b8d0d3a2cd28ae6c2f"
QUOTER="0x61ffe014ba17989e743c5f6cb21bf9697530b21e"
MODULES=[
 {"name":"current_aave_address_book_USDC","address":"0x3a3868898305f04bec7fea77becff04c13444112"},
 {"name":"prior_seized_control_USDC","address":"0xfeeb6fe430b7523fef2a38327241ee7153779535"}]
BLOCKS=[26090422,26220131]
AMOUNTS=[100,1000,10000,100000]
FEES=[100,500,3000]
count=0;stopped=False;t0=time.monotonic()
def write(name,x):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+"\n")
def sig(t):
 k=keccak.new(digest_bits=256);k.update(t.encode());return "0x"+k.hexdigest()[:8]
def u(i):return f"{int(i):064x}"
def a(z):return z[2:].lower().zfill(64)
def words(h):
 if not isinstance(h,str) or not h.startswith("0x") or len(h[2:])%64:raise ValueError("Invalid ABI output")
 return [int(h[i:i+64],16) for i in range(2,len(h),64)]
def read(name,method,params):
 global count,stopped
 if stopped:raise RuntimeError("Stopped after denial")
 if method not in ("eth_chainId","eth_getBlockByNumber","eth_getCode","eth_call"):raise ValueError("Not readonly")
 if count>=128 or time.monotonic()-t0>1050:raise RuntimeError("Research budget")
 count+=1;time.sleep(1)
 buf=b"";meta={"n":count,"name":name,"method":method}
 try:
  req=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":count,"method":method,"params":params}).encode(),
     headers={"Content-Type":"application/json","User-Agent":"QT-ReadOnly-GHO-GSM"})
  with urllib.request.urlopen(req,timeout=28) as res:
   buf=res.read(900000);meta["http_status"]=res.status
  x=json.loads(buf)
  if x.get("error"):
   meta["rpc_error"]=x["error"];s=str(x["error"]).lower()
   if any(z in s for z in ("rate limit","unauthorized","access denied","client adjustable limit")):stopped=True
   raise RuntimeError(str(x["error"])[:230])
  meta["status"]="OK";return x.get("result")
 except urllib.error.HTTPError as e:
  meta.update(http_status=e.code,error=str(e))
  if e.code in (401,403,429):stopped=True
  raise
 except Exception as e:meta["error"]=repr(e);raise
 finally:
  meta.update(sha256=hashlib.sha256(buf).hexdigest(),bytes=len(buf));write(f"requests/{count:03d}.json",meta)
  (OUT/"responses").mkdir(exist_ok=True);(OUT/f"responses/{count:03d}.body").write_bytes(buf)
def ethcall(contract,method,args,block,basefee):
 data=sig(method)+"".join(u(v) for v in args)
 return words(read(method,"eth_call",[{"to":contract,"data":data,"gasPrice":hex(basefee)},hex(block)]))
def quote_exact_output(amount_gho,fee,block,basefee):
 data=sig("quoteExactOutputSingle((address,address,uint256,uint24,uint160))")+a(USDC)+a(GHO)+u(amount_gho)+u(fee)+u(0)
 r=read("dex_buy_gho","eth_call",[{"to":QUOTER,"data":data,"gasPrice":hex(basefee)},hex(block)])
 return words(r)[0]
def quote_exact_input(amount_gho,fee,block,basefee):
 data=sig("quoteExactInputSingle((address,address,uint256,uint24,uint160))")+a(GHO)+a(USDC)+u(amount_gho)+u(fee)+u(0)
 r=read("dex_sell_gho","eth_call",[{"to":QUOTER,"data":data,"gasPrice":hex(basefee)},hex(block)])
 return words(r)[0]
def main():
 rep={"research_only":True,"full_atomic_cash_execution":False,
      "scope":"Current and explicitly retired Aave mainnet GHO GSM USDC addresses, two fixed historical states, bidirectional cash quotes",
      "uncertainties":["A former GSM can be seized or superseded; deployed code and live gating checked separately",
       "Two quoted legs start from one canonical block but do not run sequentially",
       "No builder bid, failed-attempt costs, upfront gas, or executed reward included",
       "Expired or restricted primary conversion capacity is not counted as available money"],
      "cases":[],"completed":False};write("REPORT.json",rep)
 try:
  if int(read("chain","eth_chainId",[]),16)!=1:raise ValueError("Wrong chain")
  for block in BLOCKS:
   h=read("header","eth_getBlockByNumber",[hex(block),False]);fee0=int(h["baseFeePerGas"],16)
   for m in MODULES:
    row={"block":block,"utc":datetime.datetime.fromtimestamp(int(h["timestamp"],16),datetime.timezone.utc).isoformat(),
      "block_hash":h["hash"],"module":m["name"],"address":m["address"],"quotes":[],"errors":[]}
    rep["cases"].append(row);write("REPORT.json",rep)
    if read("runtime","eth_getCode",[m["address"],hex(block)])=="0x":
     row["unavailable"]="Not deployed at this block";continue
    for fn in ("getAvailableLiquidity()","getAvailableUnderlyingExposure()","canSwap()","getIsSeized()","getIsFrozen()"):
     try:
      val=ethcall(m["address"],fn,[],block,fee0)
      row[fn]=str(val[0]) if val else "UNKNOWN"
     except Exception as e:row["errors"].append({"getter":fn,"reason":repr(e)})
    if row.get("getIsSeized()")=="1" or row.get("canSwap()")=="0":
     row["disabled_by_state"]=True
     continue
    for size in AMOUNTS:
     # USDC -> buy exact GHO on DEX -> sell GHO to GSM for fixed USDC payout.
     # getGhoAmountForBuyAsset returns (assetOut, totalGhoSold, gross, fee).
     try:
      buys=ethcall(m["address"],"getGhoAmountForBuyAsset(uint256)",[size*10**6],block,fee0)
      if len(buys)<2:raise ValueError("Malformed exact-asset GSM quote")
      row.setdefault("primary_quotes",[]).append({"usdc_out_raw":str(buys[0]),"gho_required_raw":str(buys[1]),"usdc_size":size})
      for tier in FEES:
       q={"direction":"buy_gho_on_dex_then_redeem","requested_usdc":size,"dex_fee":tier,"gho_required_raw":str(buys[1])}
       row["quotes"].append(q)
       try:
        dex_cost=quote_exact_output(buys[1],tier,block,fee0)
        q.update(usdc_cost_raw=str(dex_cost),usdc_received_raw=str(buys[0]),gross_margin_raw=str(buys[0]-dex_cost),
          positive_before_execution=buys[0]>dex_cost,correctly_funded=buys[0]>=size*10**6)
       except Exception as e:q["error"]=repr(e)
       write("REPORT.json",rep)
       if stopped:raise RuntimeError("Denied by provider")
     except Exception as e:row["errors"].append({"primary_getGhoAmountForBuyAsset":size,"error":repr(e)})
     if stopped:raise RuntimeError("Denied by provider")
     # USDC -> GSM sell asset for GHO -> DEX sell GHO back to USDC.
     try:
      sells=ethcall(m["address"],"getGhoAmountForSellAsset(uint256)",[size*10**6],block,fee0)
      if len(sells)<2:raise ValueError("Malformed sell quote")
      for tier in FEES:
       q={"direction":"mint_gho_with_usdc_then_sell_dex","usdc_in":size,"fee_tier":tier,"gho_received_raw":str(sells[1])}
       row["quotes"].append(q)
       try:
        amount=quote_exact_input(sells[1],tier,block,fee0)
        q.update(usdc_out_raw=str(amount),margin_raw=str(amount-size*10**6),positive_before_execution=amount>size*10**6)
       except Exception as e:q["error"]=repr(e)
       write("REPORT.json",rep)
       if stopped:raise RuntimeError("Denied by provider")
     except Exception as e:row["errors"].append({"primary_getGhoAmountForSellAsset":size,"error":repr(e)})
     if stopped:raise RuntimeError("Denied by provider")
   if read("header_recheck","eth_getBlockByNumber",[hex(block),False])["hash"]!=h["hash"]:
    raise ValueError("Reorg")
   write("REPORT.json",rep)
  rep["completed"]=True
 except Exception as e:rep["error"]=repr(e);rep["traceback"]=traceback.format_exc()
 rep["requests"]=count;rep["denied"]=stopped;write("REPORT.json",rep)
 print(json.dumps({"completed":rep["completed"],"requests":count,"error":rep.get("error"),
 "modules":[{"block":x["block"],"name":x["module"],"disabled":x.get("disabled_by_state"),
  "n_quotes":len(x["quotes"]),"positive":sum(q.get("positive_before_execution",False) for q in x["quotes"])} for x in rep["cases"]]},indent=2),flush=True)
 if not rep["completed"]:raise SystemExit("Incomplete research; preserve missing data")
if __name__=="__main__":main()
