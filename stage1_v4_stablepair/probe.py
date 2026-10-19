"""Programme III Stage1: Uniswap v4 StablePair fee-decay real closed cash route test.

NEW economic mechanism: directional block-dependent dynamic fees can change
whether an otherwise identical stablecoin conversion is profitable. Authenticated
read-only historical RPC only. No swap, send, signature, wallet, state mutation,
hidden capital or hypothetical 1 USD = 1 USD input accounting.
"""
import hashlib, json, os, sys
from pathlib import Path
from datetime import datetime, timezone
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC, AuthenticatedBudget, read_key_status, RPCFailure

OUT=Path("stablepair_evidence")
HOOK="0x0000113dCf4ADd69999Fad8F20F2b63F979bfcC0"
QUOTER="0x52F0E24D1c21C8A0cB1e5a5dD6198556BD9E1203"
USDC="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
USDT="0xdAC17F958D2ee523a2206206994597C13D831ec7"
USDG="0xe343167631d89B6Ffc58B88d6b7fB0228795491D"
THREEPOOL="0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"
OFFSETS=[0,1,2,3,1000,7000,30000,90000]
ROUTE_OFFSETS=[0,7000,30000,90000]
SIZES=[100,1000,10000]
# Derived Pool IDs must equal the official published values, not used for ABI.
PUBLISHED_IDS={
 "USDT":"0x2b21c65d9a7dc6926ee330a1c6e5a8037fd81774f3dc066536f800128e39f634",
 "USDG":"0xeda62d2906d0edf26d40c793d581609552a44a87f618a98ff76ebe8dde4b7edb"}
FROZEN_CONTRACTS={"hook":HOOK,"quoter":QUOTER,"curve_3pool":THREEPOOL,
                  "usdc":USDC,"usdt":USDT,"usdg":USDG}
R={"utc":datetime.now(timezone.utc).isoformat(),
   "title":"Uniswap v4 StablePair directional fee-decay window versus finite Curve 3pool cash",
   "source_deployments":"https://developers.uniswap.org/docs/protocols/uniswap-labs-hooks/stable-pair/deployments",
   "source_exact_fee":"https://developers.uniswap.org/docs/protocols/uniswap-labs-hooks/stable-pair/guides/swap",
   "source_v4_quoter":"https://github.com/Uniswap/v4-periphery/blob/main/src/interfaces/IV4Quoter.sol",
   "source_threepool":"https://github.com/curvefi/curve-js/blob/master/src/constants/pools/ethereum.ts",
   "frozen_design":{"contracts":FROZEN_CONTRACTS,"offsets":OFFSETS,
     "cash_route_offsets":ROUTE_OFFSETS,"usdc_sizes":SIZES,
     "chain_id":1,"no_outcome_based_selection":True,
     "max_authenticated_ru":230,"reserve_floor_ru":1500},
   "pool_id_validation":{},"snapshots":[],
   "summary":{},"errors":[],"complete":False,
   "signatures":0,"broadcasts":0,"actual_profit":None,
   "claim_of_repeatable_own_capture":False}
def sha3(data):
 h=keccak.new(digest_bits=256);h.update(data);return h.digest()
def select(s):return "0x"+sha3(s.encode()).hex()[:8]
def wd(x):return f"{int(x):064x}"
def address_word(a):return wd(int(a,16))
def pool_words(other):
 return [address_word(USDC),address_word(other),wd(0x800000),wd(1),address_word(HOOK)]
def pool_id(other):
 return "0x"+sha3(bytes.fromhex("".join(pool_words(other)))).hex()
def calldata_getfee(other):
 return select("getFee((address,address,uint24,int24,address))")+"".join(pool_words(other))
def calldata_v4_quote(other,zero_for_one,amount):
 # V4 QuoteExactSingleParams = (PoolKey,bool,uint128,bytes)
 # root dynamic struct offset 0x20; static tuple header 8 words;
 # empty hookData encoded as offset 0x100 plus zero length.
 return (select("quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))")
  +wd(32)+"".join(pool_words(other))+wd(1 if zero_for_one else 0)
  +wd(amount)+wd(256)+wd(0))
def calldata_curve_quote(i,j,amount):
 return select("get_dy(int128,int128,uint256)")+wd(i)+wd(j)+wd(amount)
def save():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(R,indent=2,sort_keys=True)+"\n")
def rpc_call(c,to,data,at):
 result=c.rpc("eth_call",[{"to":to,"data":data},hex(at)])
 if not isinstance(result,str) or not result.startswith("0x") or len(result)<66:
  raise ValueError("empty or short ABI return")
 return bytes.fromhex(result[2:])
def uint256_output(raw,position=0):
 if len(raw)<32*(position+1):raise ValueError("invalid ABI return length")
 return int.from_bytes(raw[32*position:32*(position+1)],"big")
def fee_pair(c,other,at):
 ret=rpc_call(c,HOOK,calldata_getfee(other),at)
 if len(ret)<64:raise ValueError("fee return incomplete")
 a,b=uint256_output(ret,0),uint256_output(ret,1)
 if not (0<=a<=1000000 and 0<=b<=1000000):raise ValueError("invalid fee rate")
 return {"zero_for_one_ppm":a,"one_for_zero_ppm":b}
def v4quote(c,other,direction,amount,at):
 result=rpc_call(c,QUOTER,calldata_v4_quote(other,direction,amount),at)
 if len(result)<64:raise ValueError("v4 quoter ABI return invalid")
 return {"amount_out":uint256_output(result),"quoter_gas_internal":uint256_output(result,1)}
def curvequote(c,i,j,amount,at):
 return uint256_output(rpc_call(c,THREEPOOL,calldata_curve_quote(i,j,amount),at))
def state(c,at,anchor):
 row={"block":at,"offset":anchor-at,"fee":{},"routes":[]}
 R["snapshots"].append(row)
 try:
  blk=c.rpc("eth_getBlockByNumber",[hex(at),False])
  row["hash"]=blk["hash"];row["timestamp"]=int(blk["timestamp"],16)
  row["base_fee_per_gas_wei"]=int(blk["baseFeePerGas"],16) if "baseFeePerGas" in blk else None
 except Exception as exc:row["block_error"]=type(exc).__name__
 for name,other in [("USDT",USDT),("USDG",USDG)]:
  try:row["fee"][name]=fee_pair(c,other,at)
  except RPCFailure as exc:
   row["fee"][name]={"status":"UNRESOLVED_RPC","error_kind":exc.kind}
   if exc.kind in ("RU_BUDGET_EXHAUSTED","AUTH_OR_ACCESS_DENIED","AUTHENTICATED_RUN_RU_CAP_REACHED","CIRCUIT_OPEN"):
    raise
  except Exception as exc:
   row["fee"][name]={"status":"UNRESOLVED","error_type":type(exc).__name__}
  save()
 if anchor-at not in ROUTE_OFFSETS:return
 # All routes use the exact same USDC input budget, no USD parity assumption.
 for size in SIZES:
  unit=size*10**6
  for label in ["v4_then_curve","curve_then_v4","curve_then_curve_control"]:
   q={"route":label,"usdc_start":size,"block":at,"cash_state":"UNRESOLVED"}
   row["routes"].append(q)
   try:
    if label=="v4_then_curve":
     a=v4quote(c,USDT,True,unit,at)
     terminal=curvequote(c,2,1,a["amount_out"],at)
     q["intermediate_usdt_raw"]=a["amount_out"]
     q["v4_internal_gas_estimate"]=a["quoter_gas_internal"]
    elif label=="curve_then_v4":
     usdt=curvequote(c,1,2,unit,at)
     a=v4quote(c,USDT,False,usdt,at)
     terminal=a["amount_out"]
     q["intermediate_usdt_raw"]=usdt
     q["v4_internal_gas_estimate"]=a["quoter_gas_internal"]
    else:
     usdt=curvequote(c,1,2,unit,at)
     terminal=curvequote(c,2,1,usdt,at)
     q["intermediate_usdt_raw"]=usdt
    gross_raw=terminal-unit
    q.update({"terminal_usdc_raw":terminal,"gross_usdc":gross_raw/1e6,
              "gross_positive":gross_raw>0,
              "cash_state":"FINITE_SAME_BLOCK_QUOTES_ONLY",
              "gas_builder_funding_and_competition_unmeasured":True,
              "atomic_execution_unverified":True})
   except RPCFailure as exc:
    q["cash_state"]="UNRESOLVED_RPC";q["error_kind"]=exc.kind
    if exc.kind in ("RU_BUDGET_EXHAUSTED","AUTH_OR_ACCESS_DENIED","AUTHENTICATED_RUN_RU_CAP_REACHED","CIRCUIT_OPEN"):
     raise
   except Exception as exc:
    q["cash_state"]="UNRESOLVED";q["error_type"]=type(exc).__name__
   save()
def main():
 save()
 key=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
 if os.environ.get("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES" or os.environ.get("QT_ALLOW_AUTHENTICATED_RPC")!="YES" or not key:
  R["errors"].append({"gate":"AUTH_OR_APPROVAL_MISSING"});save()
  print('BLOCKED: approval absent; no archive RPC');return 2
 for name,other in [("USDT",USDT),("USDG",USDG)]:
  derived=pool_id(other)
  R["pool_id_validation"][name]={"derived":derived,
       "matches_published":derived.lower()==PUBLISHED_IDS[name].lower()}
 if not all(v["matches_published"] for v in R["pool_id_validation"].values()):
  R["errors"].append({"phase":"ABI_PRECHECK","kind":"POOL_ID_MISMATCH"})
  save();print("POOL ID invariant failed before any RPC");return 2
 try:
  status=read_key_status(key)
  R["account"]={"ru_before":status.get("ru_remaining"),
      "rate_limit_rpm":status.get("rate_limit_rpm"),"budget":status.get("ru_budget")}
  budget=AuthenticatedBudget(status,approved=True,reserve_floor=1500,max_run_ru=230)
  c=ReadOnlyRPC(1,OUT/"rpc_attempts",api_key=key,status=status,budget=budget,
                max_attempts=1,max_requests=205)
  if int(c.rpc("eth_chainId",[]),16)!=1:raise RuntimeError("WRONG_CHAIN")
  tip=int(c.rpc("eth_blockNumber",[]),16)
  anchor=tip-5
  R["anchor"]=anchor
  for x in OFFSETS:
   state(c,anchor-x,anchor)
  # Recheck canonical anchor, and persist the spent worst-case RU.
  again=c.rpc("eth_getBlockByNumber",[hex(anchor),False])
  R["anchor_rechecked"]=again["hash"]==R["snapshots"][0].get("hash")
  R["account"]["conservative_attempt_ru"]=budget.attempted_ru
 except RPCFailure as exc:
  R["errors"].append({"phase":"RPC","kind":exc.kind})
 except Exception as exc:
  R["errors"].append({"phase":"RPC","kind":type(exc).__name__})
 records=[q for s in R["snapshots"] for q in s["routes"]]
 matched=[q for q in records if q["cash_state"]=="FINITE_SAME_BLOCK_QUOTES_ONLY"]
 R["summary"]={"blocks_observed":len(R["snapshots"]),"routes_attempted":len(records),
   "finite_cash_quotes":len(matched),
   "gross_positive_quote_count":sum(q["gross_positive"] for q in matched),
   "max_positive_gross_usdc":max((q["gross_usdc"] for q in matched),default=None),
   "unresolved_quotes":len(records)-len(matched)}
 R["complete"]=(len(R["snapshots"])==len(OFFSETS) and
                len(matched)==len(ROUTE_OFFSETS)*len(SIZES)*3 and
                all(all(v.get("zero_for_one_ppm") is not None for v in s["fee"].values()) for s in R["snapshots"])
                and R.get("anchor_rechecked") is True)
 save()
 print(json.dumps({"complete":R["complete"],"summary":R["summary"],
                   "ru":R.get("account",{}).get("conservative_attempt_ru"),
                   "errors":R["errors"]},sort_keys=True))
 return 0 if R["complete"] else 1
if __name__=="__main__":sys.exit(main())
