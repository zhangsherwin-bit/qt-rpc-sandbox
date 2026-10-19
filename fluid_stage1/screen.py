"""Fluid vault historic liquidation discount and cash exit, independent of Morpho/Comet.
Read-only eth_call simulation via Fluid's deployed VaultResolver: token balances
and permissionless liquidation are untouched, actual execution not presumed.
"""
import json,urllib.request,urllib.error,time,traceback,datetime,hashlib
from pathlib import Path
from Crypto.Hash import keccak

OUT=Path("fluid_evidence");OUT.mkdir(exist_ok=True)
RESOLVER="0xa5c3e16523eeeddcc34706b0e6be88b4c6ea95cc"
QUOTER={1:"0x61ffe014ba17989e743c5f6cb21bf9697530b21e",8453:"0x3d4e44eb1374240ce5f1b871ab261cd16335b76a"}
RPC={1:"https://rpc-eth.blockmachine.io",8453:"https://mainnet.base.org"}
ANCHORS=[{"chain":1,"block":26090422,"label":"eth_sep30"},
         {"chain":1,"block":26220131,"label":"eth_oct17"},
         {"chain":8453,"block":None,"label":"base_recent_500"}]
FEE_TIERS=[500,3000]
LIMIT=115
COUNT=0
DENIED=set()
START=time.monotonic()
def save(n,obj):
 p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+"\n")
def sig(s):
 k=keccak.new(digest_bits=256);k.update(s.encode());return "0x"+k.hexdigest()[:8]
def u(x):return format(int(x),"064x")
def a(addr):return addr[2:].lower().zfill(64)
def decode_words(payload):
 if not isinstance(payload,str) or not payload.startswith("0x") or (len(payload)-2)%64:raise ValueError("Malformed ABI bytes")
 return [int(payload[i:i+64],16) for i in range(2,len(payload),64)]
def address(x):
 if int(x)>=2**160:raise ValueError("Unexpected high bits in address")
 return "0x"+format(x,"040x")
def request(chain,method,params,label):
 global COUNT
 if chain in DENIED:raise RuntimeError("Stop after access denial")
 if COUNT>=LIMIT or time.monotonic()-START>1200:raise RuntimeError("Fixed request/time budget")
 if method not in ("eth_chainId","eth_blockNumber","eth_getBlockByNumber","eth_getCode","eth_call"):raise ValueError("Read methods only")
 COUNT+=1;time.sleep(1.25);raw=b"";entry={"name":label,"chain":chain,"method":method,"id":COUNT}
 try:
  body=json.dumps({"jsonrpc":"2.0","id":COUNT,"method":method,"params":params}).encode()
  req=urllib.request.Request(RPC[chain],data=body,headers={"Content-Type":"application/json","User-Agent":"QT-Fluid-Stage1-Research"})
  with urllib.request.urlopen(req,timeout=25) as resp:
   raw=resp.read(2_000_001);entry["http"]=resp.status
  if len(raw)>2_000_000:raise ValueError("RPC oversized; partial observations not zero")
  data=json.loads(raw)
  if data.get("error"):
   msg=str(data["error"]);entry["rpc_error"]=data["error"]
   if any(x in msg.lower() for x in ("rate limit","access denied","unauthorized","missing trie node","client adjustable limit")):DENIED.add(chain)
   raise RuntimeError(msg[:300])
  if "result" not in data:raise ValueError("Missing RPC result")
  entry["status"]="OK"
  return data["result"]
 except urllib.error.HTTPError as err:
  entry.update(http=err.code,error=str(err));raw=err.read(100000)
  if err.code in (401,403,429):DENIED.add(chain)
  raise
 except Exception as err:entry.update(error=repr(err));raise
 finally:
  entry.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
  save(f"requests/{COUNT:03d}.json",entry)
  (OUT/"raw").mkdir(exist_ok=True)
  (OUT/f"raw/{COUNT:03d}.body").write_bytes(raw)
def ethcall(chain,addr,data,block,basefee,label):
 return request(chain,"eth_call",[{"to":addr,"data":data,"gas":"0x1312d00","gasPrice":hex(basefee)},hex(block)],label)
def get_vaults(chain,block,basefee):
 w=decode_words(ethcall(chain,RESOLVER,sig("getAllVaultsAddresses()"),block,basefee,"vault_registry"))
 if len(w)<2 or w[0]!=32 or len(w)<w[1]+2 or w[1]>2000:raise ValueError("Vault array invalid or out of bounds")
 return [address(x) for x in w[2:2+w[1]]]
def selection(vaults):
 N=len(vaults)
 if not N:return []
 # 24 deterministic ID-spread entries, frozen from the full onchain roster.
 ids=set(range(min(7,N)))
 ids.update(range(max(0,N//2-4),min(N,N//2+4)))
 ids.update(range(max(0,N-7),N))
 ids.update(int((N-1)*i/7) for i in range(8))
 return [{"index":i,"address":vaults[i]} for i in sorted(ids)]
def decode_liquidation(raw,vault):
 w=decode_words(raw)
 if len(w)!=10:raise ValueError("Unsupported resolver liquidation ABI")
 if address(w[0])!=vault:raise ValueError("Returned vault mismatch")
 if w[9] not in (0,1):raise ValueError("Unexpected bool")
 return {"vault":vault,"token0_in":address(w[1]),"token0_out":address(w[2]),
  "token1_in":address(w[3]),"token1_out":address(w[4]),
  "max_debt_in_raw":str(w[5]),"max_collateral_out_raw":str(w[6]),
  "with_absorb_debt_in_raw":str(w[7]),"with_absorb_collateral_out_raw":str(w[8]),
  "absorb_available":bool(w[9]),"liquidatable_now":bool(w[5]>0 and w[6]>0)}
def liquidate_view(chain,vault,amount,block,basefee):
 data=sig("getVaultLiquidation(address,uint256)")+a(vault)+u(amount)
 raw=ethcall(chain,RESOLVER,data,block,basefee,"liquidation_view")
 return decode_liquidation(raw,vault)
def decimals(chain,token,block,basefee):
 return decode_words(ethcall(chain,token,sig("decimals()"),block,basefee,"repayment_decimals"))[0]
def quote(chain,token0,token1,qty,fee,block,basefee):
 data=sig("quoteExactInputSingle((address,address,uint256,uint24,uint160))")
 data+=a(token0)+a(token1)+u(qty)+u(fee)+u(0)
 out=decode_words(ethcall(chain,QUOTER[chain],data,block,basefee,"exact_input_cash_exit"))
 if len(out)!=4:raise ValueError("QuoterV2 invalid output")
 return out[0]
def run():
 report={"scope":"Fluid VaultResolver permissionless liquidation inventory and finite debt-to-cash quotes",
  "market_selection":"Official all-vaults ABI; deterministic 7 early, 8 middle, 7 latest, 8 uniformly spaced IDs, deduplicated",
  "test_method":"historical eth_call of getVaultLiquidation; only read-only and no real funds",
  "cases":[],"finished":False,"no_transaction_or_profit_claim":True,
  "warnings":["An eth_call-liquidatable amount is not a captured auction or standalone profitable execution",
     "Token1/smart vault legs cannot be treated as equivalent ordinary ERC20 cash",
     "Uniswap V3 quotations reset state, exclude gas and builder compensation",
     "Finite liquidation quotes may differ nonlinearly from maximum due to dynamic discount",
     "A positive quote cannot be promoted until full stateful financing/settlement closes"]}
 save("REPORT.json",report)
 try:
  for config in ANCHORS:
   chain=config["chain"]
   if int(request(chain,"eth_chainId",[],"chainid"),16)!=chain:raise ValueError("Wrong chain")
   block=config["block"]
   if block is None:
    latest=int(request(chain,"eth_blockNumber",[],"tip"),16)
    block=latest-500
   header=request(chain,"eth_getBlockByNumber",[hex(block),False],"head")
   if not header:raise ValueError("Missing pinned header")
   basefee=int(header["baseFeePerGas"],16)
   state={"name":config["label"],"chain":chain,"block":block,"hash":header["hash"],
    "utc":datetime.datetime.fromtimestamp(int(header["timestamp"],16),datetime.timezone.utc).isoformat(),
    "vaults":[],"errors":[]}
   report["cases"].append(state);save("REPORT.json",report)
   if request(chain,"eth_getCode",[RESOLVER,hex(block)],"resolver_runtime")=="0x":raise ValueError("Resolver not deployed")
   vaults=get_vaults(chain,block,basefee)
   state["vaults_in_registry"]=len(vaults)
   selections=selection(vaults)
   state["selected_count"]=len(selections)
   for candidate in selections:
    x={**candidate}
    state["vaults"].append(x)
    try:
     case=liquidate_view(chain,x["address"],0,block,basefee)
     x.update(case)
     if x["liquidatable_now"]:
      # More conservative than treating DEX smart shares as ERC-20.
      if int(x["token1_in"],16) or int(x["token1_out"],16):
       x["cash_status"]="MULTI_ASSET_UNRESOLVED";continue
      debt_scale=decimals(chain,x["token0_in"],block,basefee)
      if debt_scale>24:raise ValueError("Unreasonable decimals")
      max_amt=int(x["max_debt_in_raw"]);target=min(max_amt,1000*10**debt_scale)
      limited=liquidate_view(chain,x["address"],target,block,basefee)
      x["finite"]={"limit_in_raw":str(target),"quoted_in_raw":limited["max_debt_in_raw"],
        "quoted_out_raw":limited["max_collateral_out_raw"],"cash_exits":[]}
      if int(limited["max_debt_in_raw"])<=0 or int(limited["max_collateral_out_raw"])<=0:
       x["cash_status"]="NO_FINITE_AVAILABLE";continue
      for fee in FEE_TIERS:
       q={"fee":fee}
       x["finite"]["cash_exits"].append(q)
       try:
        amount=quote(chain,x["token0_out"],x["token0_in"],int(limited["max_collateral_out_raw"]),fee,block,basefee)
        q["USDC_or_debt_out_raw"]=str(amount)
        q["gross_spread_debt_raw"]=str(amount-int(limited["max_debt_in_raw"]))
        q["positive_quote_only"]=amount>int(limited["max_debt_in_raw"])
       except Exception as err:q["error"]=repr(err)
       save("REPORT.json",report)
       if chain in DENIED:raise RuntimeError("Stop after provider denial")
    except Exception as err:x["error"]=repr(err)
    save("REPORT.json",report)
    if chain in DENIED:raise RuntimeError("Provider denial")
   stat=request(chain,"eth_getBlockByNumber",[hex(block),False],"canonical_hash_recheck")
   if stat["hash"]!=header["hash"]:raise ValueError("Historical block reorg")
   state["complete"]=True
  report["finished"]=True
 except Exception as err:report["exception"]=repr(err);report["traceback"]=traceback.format_exc()
 report["requests"]=COUNT;report["denied_chains"]=sorted(DENIED)
 save("REPORT.json",report)
 print(json.dumps({"finished":report["finished"],"requests":COUNT,"error":report.get("exception"),
    "states":[{"name":x["name"],"vaults_total":x.get("vaults_in_registry"),
     "inspected":len(x["vaults"]),"liquidatable":sum(bool(v.get("liquidatable_now")) for v in x["vaults"]),
     "positive_cash_quotes":sum(sum(int(z.get("positive_quote_only",False)) for z in v.get("finite",{}).get("cash_exits",[])) for v in x["vaults"])} for x in report["cases"]]},indent=2),flush=True)
 if not report["finished"]:raise SystemExit("Partial evidence only: no zero-income conclusion")
if __name__=="__main__":run()
