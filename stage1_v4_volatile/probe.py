"""Programme III Stage1: v4 VolatilePair intra-block fees and external ETH/WETH cash closure.

New economics: v4 VolatilePair increases backrun-side fees and changes
directional transaction tolls after price moves. Compare finite actual
historical ETH/USDC v4 Quoter to WETH/USDC v3 QuoterV2, both
directions with exact WETH/ETH 1:1 wrapping, no fictitious USD parity.
Read-only authenticated eth_call; NO orders, wallet, signing, broadcasts.
"""
import json,os,sys
from pathlib import Path
from datetime import datetime,timezone
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC,AuthenticatedBudget,read_key_status,RPCFailure

OUT=Path("volatilepair_evidence")
HOOK="0x000022Ec4eBD6b12294396E852E4C3876b253Cc0"
V4QUOTER="0x52F0E24D1c21C8A0cB1e5a5dD6198556BD9E1203"
V3QUOTER="0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
ETH="0x0000000000000000000000000000000000000000"
WETH="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
POOLID="0x98316e8405502774a5d0a0761276b5d26505a8195c1905169864008d5e7a3eea"
STATES=[0,1,2,3,1000,7000,30000,90000]
CASH_STATES=[0,7000,30000,90000]
SIZES_ETH=[0.05,0.25,1]
FEE_TIERS=[500,3000]
BUDGET_RU=250
R={"timestamp_utc":datetime.now(timezone.utc).isoformat(),
 "family":"New: directional VolatilePair fee-setting creates time-dependent right to backrun",
 "official_source":"https://developers.uniswap.org/docs/protocols/uniswap-labs-hooks/volatile-pair/overview",
 "official_deployment":"https://developers.uniswap.org/docs/protocols/uniswap-labs-hooks/volatile-pair/deployments",
 "official_fee_api":"https://developers.uniswap.org/docs/protocols/uniswap-labs-hooks/volatile-pair/guides/swap",
 "v3_quoter_source":"https://developers.uniswap.org/docs/protocols/v3/deployments/v3-ethereum-deployments",
 "frozen":{"contracts":{"hook":HOOK,"v4_quoter":V4QUOTER,"v3_quoter":V3QUOTER,
                          "ETH":ETH,"WETH":WETH,"USDC":USDC},
           "state_offsets":STATES,"cash_route_offsets":CASH_STATES,
           "sizes_eth":SIZES_ETH,"v3_fee_tiers":FEE_TIERS,
           "max_authenticated_ru":BUDGET_RU,"reserve_floor_ru":1500},
 "pool_id_valid":False,"snapshots":[],"errors":[],
 "actual_cash_income":None,"broadcasts":0,"signatures":0,
 "stage2_ready":False,"complete":False}
def h(a):
 k=keccak.new(digest_bits=256);k.update(a);return k.digest()
def sel(a):return "0x"+h(a.encode()).hex()[:8]
def wd(a):return format(int(a),"064x")
def words():
 return [wd(int(ETH,16)),wd(int(USDC,16)),wd(0x800000),wd(4),wd(int(HOOK,16))]
def pool_id():return "0x"+h(bytes.fromhex("".join(words()))).hex()
def fee_calldata():
 return sel("getFee((address,address,uint24,int24,address))")+"".join(words())
def v4_calldata(direction,amt):
 # ExactSingleParams: (PoolKey,bool,uint128,bytes)
 return (sel("quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))")
 +wd(32)+"".join(words())+wd(int(direction))+wd(amt)+wd(256)+wd(0))
def v3_calldata(inside,outside,amount,fee):
 # Uniswap v3 QuoterV2 QuoteExactInputSingleParams static tuple
 return (sel("quoteExactInputSingle((address,address,uint256,uint24,uint160))")
    +wd(int(inside,16))+wd(int(outside,16))+wd(amount)+wd(fee)+wd(0))
def save():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(R,sort_keys=True,indent=2)+"\n")
def words_result(c,to,data,at,min_words):
 res=c.rpc("eth_call",[{"to":to,"data":data},hex(at)])
 if not isinstance(res,str) or not res.startswith("0x") or len(res)<2+64*min_words:
  raise ValueError("invalid ABI result")
 b=bytes.fromhex(res[2:])
 return [int.from_bytes(b[32*i:32*(i+1)],"big") for i in range(min_words)]
def v4quote(c,direction,amount,at):
 out=words_result(c,V4QUOTER,v4_calldata(direction,amount),at,2)
 return {"out":out[0],"quoter_internal_gas":out[1]}
def v3quote(c,tin,tout,amount,fee,at):
 out=words_result(c,V3QUOTER,v3_calldata(tin,tout,amount,fee),at,4)
 return {"out":out[0],"quoter_internal_gas":out[3]}
def at_block(c,block,anchor):
 row={"block":block,"offset":anchor-block,"routes":[]}
 R["snapshots"].append(row)
 try:
  head=c.rpc("eth_getBlockByNumber",[hex(block),False])
  row["hash"]=head["hash"]
  row["timestamp"]=int(head["timestamp"],16)
  row["base_fee_wei"]=int(head["baseFeePerGas"],16) if head.get("baseFeePerGas") else None
  pair=words_result(c,HOOK,fee_calldata(),block,2)
  if any(x>999998 for x in pair):raise ValueError("invalid feeE6")
  row["directional_fee_ppm"]={"ETH_to_USDC":pair[0],"USDC_to_ETH":pair[1]}
 except RPCFailure as e:
  row["fee_error_kind"]=e.kind
  if e.kind in ("RU_BUDGET_EXHAUSTED","AUTH_OR_ACCESS_DENIED","AUTHENTICATED_RUN_RU_CAP_REACHED","CIRCUIT_OPEN"):
   raise
 except Exception as exc:row["fee_error"]=type(exc).__name__
 save()
 if row["offset"] not in CASH_STATES:return
 # Equal starting WETH budget for every route. ETH unwrap/rewrap is 1:1
 # token conversion in the real WETH contract; additional gas excluded.
 for size in SIZES_ETH:
  start=int(round(size*1e18))
  for category in ["v4_to_v3","v3_to_v4","v3_only_control"]:
   tiers=FEE_TIERS if category!="v3_only_control" else [500]
   for tier in tiers:
    obs={"route":category,"v3_fee":tier,"starting_weth":size,
         "cash_status":"UNRESOLVED","block":block}
    row["routes"].append(obs)
    try:
     if category=="v4_to_v3":
      a=v4quote(c,True,start,block)
      b=v3quote(c,USDC,WETH,a["out"],tier,block)
      final=b["out"]
      obs["intermediate_usdc_raw"]=a["out"]
      obs["v4_quoter_gas_internal"]=a["quoter_internal_gas"]
      obs["v3_quoter_gas_internal"]=b["quoter_internal_gas"]
     elif category=="v3_to_v4":
      a=v3quote(c,WETH,USDC,start,tier,block)
      b=v4quote(c,False,a["out"],block)
      final=b["out"]
      obs["intermediate_usdc_raw"]=a["out"]
      obs["v4_quoter_gas_internal"]=b["quoter_internal_gas"]
      obs["v3_quoter_gas_internal"]=a["quoter_internal_gas"]
     else:
      a=v3quote(c,WETH,USDC,start,500,block)
      b=v3quote(c,USDC,WETH,a["out"],3000,block)
      final=b["out"]
      obs["intermediate_usdc_raw"]=a["out"]
     obs.update({"final_weth_raw":final,"gross_weth":(final-start)/1e18,
                 "gross_positive":final>start,
                 "cash_status":"FINITE_SAME_BLOCK_QUOTES_NOT_EXECUTION",
                 "weth_native_eth_wrap_invariant_assumed":True,
                 "wrap_gas_priority_fee_builder_competition_unmeasured":True,
                 "atomic_flashloan_repayment_unverified":True})
    except RPCFailure as exc:
     obs["cash_status"]="UNRESOLVED_RPC"
     obs["error_kind"]=exc.kind
     if exc.kind in ("RU_BUDGET_EXHAUSTED","AUTH_OR_ACCESS_DENIED","AUTHENTICATED_RUN_RU_CAP_REACHED","CIRCUIT_OPEN"):
      raise
    except Exception as exc:
     obs["cash_status"]="UNRESOLVED"
     obs["error_type"]=type(exc).__name__
    save()
def main():
 save()
 k=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
 if os.environ.get("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES" or os.environ.get("QT_ALLOW_AUTHENTICATED_RPC")!="YES" or not k:
  R["errors"].append({"type":"ACCOUNT_PERMISSION_OR_KEY_MISSING"})
  save();print('BLOCKED, no authenticated RPC sent');return 2
 R["pool_id_derived"]=pool_id()
 R["pool_id_valid"]=pool_id().lower()==POOLID.lower()
 if not R["pool_id_valid"]:
  R["errors"].append({"type":"POOL_ID_MISMATCH_PRE_RPC"})
  save();print('PoolId error before any archive requests');return 2
 try:
  status=read_key_status(k)
  R["account"]={"initial_ru_remaining":status["ru_remaining"],
      "reported_rate_ru_per_min":status["rate_limit_rpm"]}
  budget=AuthenticatedBudget(status,approved=True,reserve_floor=1500,max_run_ru=BUDGET_RU)
  c=ReadOnlyRPC(1,OUT/"rpc_attempts",api_key=k,status=status,budget=budget,
                max_attempts=1,max_requests=200)
  if int(c.rpc("eth_chainId",[]),16)!=1:raise RuntimeError("RPC_WRONG_CHAIN")
  tip=int(c.rpc("eth_blockNumber",[]),16)
  anchor=tip-5;R["anchor"]=anchor
  for offset in STATES:at_block(c,anchor-offset,anchor)
  head=c.rpc("eth_getBlockByNumber",[hex(anchor),False])
  R["anchor_rechecked"]=head.get("hash")==R["snapshots"][0].get("hash")
  R["account"]["conservative_attempted_ru"]=budget.attempted_ru
 except RPCFailure as exc:R["errors"].append({"phase":"RPC","kind":exc.kind})
 except Exception as exc:R["errors"].append({"phase":"RPC","kind":type(exc).__name__})
 rows=[q for s in R["snapshots"] for q in s["routes"]]
 finite=[q for q in rows if q.get("cash_status")=="FINITE_SAME_BLOCK_QUOTES_NOT_EXECUTION"]
 R["summary"]={"states_read":len(R["snapshots"]),"routes_attempted":len(rows),
               "finite_route_quotes":len(finite),
               "gross_positive_quotes":sum(q["gross_positive"] for q in finite),
               "best_gross_weth":max([q["gross_weth"] for q in finite],default=None),
               "unresolved_routes":len(rows)-len(finite)}
 R["complete"]=(len(R["snapshots"])==len(STATES) and R.get("anchor_rechecked") is True
    and len(rows)==len(CASH_STATES)*len(SIZES_ETH)*5
    and len(finite)==len(rows)
    and all("directional_fee_ppm" in row for row in R["snapshots"]))
 save()
 print(json.dumps({"complete":R["complete"],"summary":R["summary"],
   "estimated_ru":R.get("account",{}).get("conservative_attempted_ru"),"errors":R["errors"]},sort_keys=True))
 return 0 if R["complete"] else 1
if __name__=="__main__":sys.exit(main())
