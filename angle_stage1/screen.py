"""Stage 1: Angle USDA/USDC Transmuter plus DEX reverse cash quotes.
On-chain READ ONLY. All quoted routes are counterfactual same-state legs,
not full joint execution, captured orders, or guaranteed profit.
"""
import json,time,urllib.request,urllib.error,hashlib,datetime,traceback
from pathlib import Path
from Crypto.Hash import keccak

OUT=Path("angle_evidence");OUT.mkdir(parents=True,exist_ok=True)
ETH="https://rpc-eth.blockmachine.io"
TRANS="0x222222fD79264BBE280b4986F6FEfBC3524d0137".lower()
USDC="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48".lower()
QUOTER="0x61ffe014ba17989e743c5f6cb21bf9697530b21e"
SAMPLES=[{"name":"sep_16","height":25987198},{"name":"sep_18","height":26003414},{"name":"sep_30","height":26090422},{"name":"oct_17","height":26220131}]
SIZES=[100,1000,10000]
FEES=[100,500,3000,10000]
n=0;denied=False;start=time.monotonic()
def dump(name,x):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+"\n")
def sel(x):
 k=keccak.new(digest_bits=256);k.update(x.encode());return '0x'+k.hexdigest()[:8]
def enc_address(x):return x[2:].lower().zfill(64)
def enc_uint(x):return f'{int(x):064x}'
def dec_word(h):
 if not isinstance(h,str) or len(h)<66:raise ValueError("Invalid RPC uint256 result")
 return int(h[2:66],16)
def dec_addr(h):
 x=dec_word(h)
 if x>=2**160 or x==0:raise ValueError("Invalid ERC20 address")
 return "0x"+format(x,'040x')
def dec_list(h):
 if not isinstance(h,str) or not h.startswith("0x"):raise ValueError("Invalid dynamic array")
 chunks=[int(h[i:i+64],16) for i in range(2,len(h),64)]
 if not chunks or chunks[0]!=32 or len(chunks)<2:raise ValueError("Invalid ABI offset")
 count=chunks[1]
 if count>15 or len(chunks)<count+2:raise ValueError("Unexpected collateral count")
 return ["0x"+format(x,'040x') for x in chunks[2:2+count]]
def rpc(name,method,params):
 global n,denied
 if denied:raise RuntimeError("Stopped after provider denial")
 if method not in ('eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call'):raise ValueError("Read-only allowlist")
 if n>=165 or time.monotonic()-start>1200:raise RuntimeError("Bounded request/time cap")
 n+=1;time.sleep(.25);body=b'';record={"name":name,"method":method,"id":n}
 try:
  data=json.dumps({"jsonrpc":"2.0","id":n,"method":method,"params":params}).encode()
  req=urllib.request.Request(ETH,data=data,headers={"Content-Type":"application/json","User-Agent":"QT-stage1-public-RPC"})
  with urllib.request.urlopen(req,timeout=22) as res:body=res.read(180000)
  payload=json.loads(body);record['http_status']=200
  if payload.get("error"):
   record['rpc_error']=payload['error'];msg=str(payload['error']).lower()
   if any(w in msg for w in ('rate limit','access denied','unauthorized','client adjustable limit')):denied=True
   raise RuntimeError("RPC: "+str(payload['error'])[:200])
  if "result" not in payload:raise ValueError("No result")
  record['status']='OK'
  return payload['result']
 except urllib.error.HTTPError as e:
  record.update(status="HTTP_ERROR",http_status=e.code,error=str(e.reason))
  if e.code in (401,403,429):denied=True
  raise
 except Exception as e:record.update(status="ERROR",error=str(e)[:260]);raise
 finally:
  record['sha256']=hashlib.sha256(body).hexdigest()
  record['bytes']=len(body);dump(f"requests/{n:03d}.json",record)
  (OUT/"responses").mkdir(exist_ok=True);(OUT/f"responses/{n:03d}.body").write_bytes(body)
def call(name,to,data,height,basefee):
 tx={"to":to,"data":data,"gas":"0x2dc6c0","gasPrice":hex(basefee)}
 return rpc(name,"eth_call",[tx,hex(height)])
def quoted_transmuter(name,token_in,token_out,quantity,h,basefee):
 return dec_word(call(name,TRANS,sel("quoteIn(uint256,address,address)")+enc_uint(quantity)+enc_address(token_in)+enc_address(token_out),h,basefee))
def paused(asset,action,h,basefee):
 return bool(dec_word(call("paused_"+str(action),TRANS,sel("isPaused(address,uint8)")+enc_address(asset)+enc_uint(action),h,basefee)))
def quoter(name,token_in,token_out,quantity,fee,h,basefee):
 # V3 QuoterV2 quoteExactInputSingle(tuple) output (amountOut,sqrtAfter,ticksCrossed,gasEstimate).
 data=sel("quoteExactInputSingle((address,address,uint256,uint24,uint160))")+enc_address(token_in)+enc_address(token_out)+enc_uint(quantity)+enc_uint(fee)+enc_uint(0)
 return dec_word(call(name,QUOTER,data,h,basefee))
def main():
 report={"name":"Angle USDA against native USDC via Transmuter and actual UniswapV3 pools",
 "cases":[],"completed":False,"no_signature_trade_broadcast":True,"full_cash_execution_performed":False,
 "selection":"Four fixed historical Ethereum block heights, three USDC input sizes, four DEX fees, both route directions",
 "warnings":["Each quote is a separate unchanged historical-state call; second leg executed only as a view","No actual sequential EVM swaps, approvals, oracle bypass or gas-inclusive profit claimed","Uniswap Quoter may hit price limits; actual unspent input not measured","Protocol pause and whitelist checks must be verified for execution","Historical state is development, not prospective capture evidence"]}
 dump("REPORT.json",report)
 try:
  if int(rpc("chainid","eth_chainId",[]),16)!=1:raise RuntimeError("Wrong chain")
  for case in SAMPLES:
   r={**case,"route_quotes":[],"errors":[]};report["cases"].append(r);dump("REPORT.json",report)
   h=case["height"]
   header=rpc("header","eth_getBlockByNumber",[hex(h),False])
   fee0=int(header["baseFeePerGas"],16)
   r.update(canonical_block_hash=header["hash"],base_fee_per_gas=str(fee0),timestamp_utc=datetime.datetime.fromtimestamp(int(header["timestamp"],16),datetime.timezone.utc).isoformat())
   if not rpc("transmuter_code","eth_getCode",[TRANS,hex(h)]) or rpc("usdc_code","eth_getCode",[USDC,hex(h)])=="0x":raise ValueError("Transmuter/USDC not deployed")
   coin=dec_addr(call("get_usda",TRANS,sel("agToken()"),h,fee0))
   c_list=dec_list(call("get_collateral_list",TRANS,sel("getCollateralList()"),h,fee0))
   r.update(usda=coin,collaterals=c_list,usdc_collateral=USDC in c_list)
   if USDC not in c_list:
    r["condition"]="USDC is not accepted collateral at this height";continue
   if not rpc("usda_code","eth_getCode",[coin,hex(h)]):raise ValueError("No agToken runtime")
   r["usda_decimals"]=dec_word(call("usda_decimals",coin,sel("decimals()"),h,fee0))
   if r["usda_decimals"]>24:raise ValueError("Unsupported USDA decimals")
   r["paused_mint"]=paused(USDC,0,h,fee0)
   r["paused_burn"]=paused(USDC,1,h,fee0)
   r["whitelisted_only"]=bool(dec_word(call("whitelist_only",TRANS,sel("isWhitelistedCollateral(address)")+enc_address(USDC),h,fee0)))
   if r["whitelisted_only"] or (r["paused_mint"] and r["paused_burn"]):
    r["condition"]="Paused or whitelist-gated; no permissionless actionable quotes"
    dump("REPORT.json",report);continue
   # Route A: start USDC -> Transmuter mint USDA -> Uniswap sell USDA for USDC.
   # Route B: USDC -> Uniswap buy USDA -> Transmuter burn USDA for USDC.
   for usdc in SIZES:
    if not r["paused_mint"]:
     minted=quoted_transmuter("mint_quote",USDC,coin,usdc*10**6,h,fee0)
     for fee in FEES:
      row={"direction":"mint_then_sell","usdc_in":usdc,"fee_tier":fee,"issued_usda_raw":str(minted)}
      try:
       value=quoter("usda_exit",coin,USDC,minted,fee,h,fee0)
       row.update(usdc_out_raw=str(value),gross_margin_usdc_raw=str(value-usdc*10**6),positive_gross=value>usdc*10**6)
      except Exception as ex:row["error"]=repr(ex)
      r["route_quotes"].append(row);dump("REPORT.json",report)
      if denied:raise RuntimeError("Provider stopped")
    if not r["paused_burn"] and not r["whitelisted_only"]:
     for fee in FEES:
      row={"direction":"buy_then_burn","usdc_in":usdc,"fee_tier":fee}
      try:
       purchased=quoter("usda_buy",USDC,coin,usdc*10**6,fee,h,fee0)
       returned=quoted_transmuter("burn_quote",coin,USDC,purchased,h,fee0)
       row.update(usda_bought_raw=str(purchased),usdc_out_raw=str(returned),gross_margin_usdc_raw=str(returned-usdc*10**6),positive_gross=returned>usdc*10**6)
      except Exception as ex:row["error"]=repr(ex)
      r["route_quotes"].append(row);dump("REPORT.json",report)
      if denied:raise RuntimeError("Provider stopped")
   r["quote_count"]=len(r["route_quotes"])
   # Need recheck block anchor
   header2=rpc("header_recheck","eth_getBlockByNumber",[hex(h),False])
   if header2["hash"]!=header["hash"]:raise ValueError("Historical block reorg")
   dump("REPORT.json",report)
  report["completed"]=True
 except Exception as ex:report["error"]=repr(ex);report["traceback"]=traceback.format_exc()
 report["requests"]=n;report["provider_denied"]=denied;dump("REPORT.json",report)
 print(json.dumps({"completed":report["completed"],"requests":n,"error":report.get("error"),
    "observations":[{"name":x["name"],"collateral_ok":x.get("usdc_collateral"),
       "quotes":len(x.get("route_quotes",[])),"positive":sum(z.get("positive_gross",False) for z in x.get("route_quotes",[]))} for x in report["cases"]]},indent=2),flush=True)
 if not report["completed"]:raise SystemExit("Research incomplete: partial evidence preserved")
if __name__=="__main__":main()
