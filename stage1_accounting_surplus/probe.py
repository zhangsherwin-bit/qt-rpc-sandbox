"""QT Programme III Stage 1: accounting-reserve surplus across unrelated systems.

Two independent accounting implementations:
 A) UniV2/SushiV2 pools: actual ERC20 balance - getReserves before skim.
 B) Sushi BentoBoxV1: ERC20 actual + accounted strategy.balance - totals.elastic,
    with read-only simulated deposit(from=BentoBox) for independent external rights.

First-order observations only; no trades/signatures/funds/recoveries. Predeclared
chains, contracts, tokens, pair lists, blocks and bounded original provider RU.
"""
import json, os, sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC, WeightedLimiter, AuthenticatedBudget, read_key_status, RPCFailure

OUT=Path("stage1_accounting_surplus_evidence")
OUT.mkdir(exist_ok=True)
ETH=1;BASE=8453
FACTORIES={
 ETH:{"UniswapV2":"0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
      "SushiV2":"0xc0aee478e3658e2610c5f7a4a2e1777ce9e4f2ac"},
 BASE:{"UniswapV2":"0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6"},
}
TOK={
 ETH: {
  "WETH":("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",18),
  "USDC":("0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",6),
  "USDT":("0xdAC17F958D2ee523a2206206994597C13D831ec7",6),
  "DAI": ("0x6B175474E89094C44Da98b954EedeAC495271d0F",18),
  "stETH":("0xae7ab96520de3a18e5e111b5eaab095312d7fe84",18),
  "WBTC":("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",8),
  "AMPL":("0xD46bA6D942050d489DBd938a2C909A5d5039A161",9)
 },
 BASE:{
  "WETH":("0x4200000000000000000000000000000000000006",18),
  "USDC":("0x833589fCD6EDB6E08f4c7c32D4f71b54bdA02913",6),
  "DAI":("0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",18),
 }
}
PAIRS={
 ETH:{
  "UniswapV2":[("WETH","USDC"),("WETH","USDT"),("WETH","DAI"),
               ("WETH","stETH"),("WETH","WBTC"),("WETH","AMPL")],
  "SushiV2":[("WETH","USDC"),("WETH","USDT"),("WETH","stETH"),("WETH","AMPL")]
 },
 BASE:{"UniswapV2":[("WETH","USDC"),("WETH","DAI"),("USDC","DAI")]}
}
BENTO="0xf5bce5077908a1b7370b9ae04adc565ebd643966"
BENTO_TOKENS=["USDC","USDT","WETH","DAI"]  # no rebase, no strategies presumed
SNAPSHOT_OFFSETS=[8,20008,70008,150008,360008]
BENTO_SNAPSHOTS=3 # first three offsets, fixed before fetching data
ZERO="0x"+"0"*40
EXTERNAL="0x000000000000000000000000000000000000dEaD"
MAX_SKIM_SIMULATIONS=6
RUN_CAP_RU=430
REPORT={
 "campaign":"QT Programme III Stage 1 -- new accounting-discrepancy families",
 "utc":datetime.now(timezone.utc).isoformat(),
 "frozen_design":{
  "chains":[1,8453],"factories":FACTORIES,"token_metadata":TOK,
  "pairs":PAIRS,"bentobox_contract":BENTO,"bentobox_tokens":BENTO_TOKENS,
  "snapshot_offsets":SNAPSHOT_OFFSETS,"bento_snapshot_count":BENTO_SNAPSHOTS,
  "balance_reserve_cash_claim":"max(0, token.balanceOf(pool)-reserves[k])",
  "bento_cash_claim":"max(0, ERC20.balanceOf(bento)+strategyData.balance-totals.elastic)",
  "stage1_assumptions":"no quote=profit; token units not fungible; gross amount excludes gas",
  "historical_sample_not_full_census":True,"read_only":True,
  "max_rU_this_process":RUN_CAP_RU,"reserve_rU_floor":1500,
  "predeclared_max_simulations":MAX_SKIM_SIMULATIONS},
 "raw_archive_sha256_index":"qt_rpc.ReadOnlyRPC",
 "results":{},"negative_controls":[],"errors":[],"complete":False,
 "stage2_eligible":False,"trades_signed_or_submitted":0
}
SHARED=None; STATUS=None; LIMITER=None;CLIENT={}
def persist():
 (OUT/"REPORT.json").write_text(json.dumps(REPORT,indent=2,sort_keys=True,default=str)+"\n")
def selector(sig):
 h=keccak.new(digest_bits=256);h.update(sig.encode());return "0x"+h.hexdigest()[:8]
SEL={s:selector(s) for s in [
 "getPair(address,address)","token0()","token1()","getReserves()",
 "balanceOf(address)","decimals()","skim(address)",
 "totals(address)","strategyData(address)",
 "deposit(address,address,address,uint256,uint256)"]}
def word(v):return format(int(v),"064x")
def hex_addr(a):return int(a,16)
def encode(sig,*args):
 out=SEL[sig]
 for a in args:out+=word(hex_addr(a) if isinstance(a,str) and a[:2]=="0x" and len(a)==42 else a)
 return out
def unpack(raw,count=1):
 if not isinstance(raw,str) or not raw.startswith("0x"):raise ValueError("invalid or empty ABI output")
 hexv=raw[2:]
 if len(hexv)<64*count:raise ValueError("short ABI output")
 return tuple(int(hexv[i*64:(i+1)*64],16) for i in range(count))
def toaddr(n):return "0x"+format(n,"040x")
def ident(ch):return "ethereum" if ch==1 else "base"
def rpc(ch,method,params):
 return CLIENT[ch].rpc(method,params)
def read(ch,to,sig,*args,block):
 return rpc(ch,"eth_call",[{"to":to,"data":encode(sig,*args)},hex(block)])
def init_rpc():
 global SHARED,STATUS,LIMITER
 if os.environ.get("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES":
  raise RPCFailure("ACCOUNT_USE_CONFIRMATION_REQUIRED")
 if os.environ.get("QT_ALLOW_AUTHENTICATED_RPC")!="YES":
  raise RPCFailure("AUTHENTICATED_RU_CONSENT_REQUIRED")
 key=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
 if not key:raise RPCFailure("GITHUB_SECRET_NOT_FOUND")
 STATUS=read_key_status(key)
 if STATUS.get("auth")!="authenticated" or STATUS.get("ru_remaining",0)<2200:
  raise RPCFailure("KEY_NOT_READY_OR_BALANCE_TOO_LOW")
 SHARED=AuthenticatedBudget(STATUS,reserve_floor=1500,max_run_ru=RUN_CAP_RU,approved=True)
 LIMITER=WeightedLimiter(cap_ru=max(5,int(STATUS["rate_limit_rpm"]*.55)))
 REPORT["starting_status"]={k:STATUS.get(k) for k in ["ru_budget","ru_remaining","rate_limit_rpm"]}
 REPORT["authorised_run_ru_cap"]=SHARED.cap_ru
 for ch in [ETH,BASE]:
  CLIENT[ch]=ReadOnlyRPC(ch,OUT/ident(ch)/"rpc_raw",api_key=key,status=STATUS,
      budget=SHARED,limiter=LIMITER,max_requests=280,max_attempts=2)
 persist()
def getpair(ch,factory,t0,t1,block):
 raw=read(ch,FACTORIES[ch][factory],"getPair(address,address)",
          TOK[ch][t0][0],TOK[ch][t1][0],block=block)
 return toaddr(unpack(raw)[0])
def balance(ch,token,account,block):
 return unpack(read(ch,token,"balanceOf(address)",account,block=block))[0]
def check_head(ch):
 n=int(rpc(ch,"eth_chainId",[]),16)
 if n!=ch:raise RPCFailure("CHAIN_ID_MISMATCH")
 tip=int(rpc(ch,"eth_blockNumber",[]),16)-5
 anchors=[]
 for off in SNAPSHOT_OFFSETS:
  b=tip-off
  if b<0:raise ValueError("predates chain genesis")
  h=rpc(ch,"eth_getBlockByNumber",[hex(b),False])
  if not isinstance(h,dict) or int(h["number"],16)!=b:raise ValueError("missing archive header")
  anchors.append({"offset":off,"block":b,"hash":h["hash"],
      "timestamp":int(h["timestamp"],16),
      "base_fee_wei":int(h.get("baseFeePerGas","0x0"),16)})
 return anchors
def get_pool(ch,venue,token_a,token_b,headblock):
 pool=getpair(ch,venue,token_a,token_b,headblock)
 if pool==ZERO:return {"pair":None,"reason":"NO_PAIR_DEPLOYED","venue":venue,
                        "tokens":[token_a,token_b],"states":[]}
 expected={TOK[ch][token_a][0].lower(),TOK[ch][token_b][0].lower()}
 try:
  a=toaddr(unpack(read(ch,pool,"token0()",block=headblock))[0])
  b=toaddr(unpack(read(ch,pool,"token1()",block=headblock))[0])
  if {a.lower(),b.lower()}!=expected:raise ValueError("pair token identifiers mismatch")
  dec={v[0].lower():{"symbol":k,"decimals":v[1]} for k,v in TOK[ch].items()}
  return {"pair":pool,"venue":venue,"tokens":[token_a,token_b],
   "token0":a.lower(),"token1":b.lower(),"metadata":dec,"states":[]}
 except Exception as ex:
  return {"pair":pool,"venue":venue,"tokens":[token_a,token_b],"states":[],
          "error_kind":type(ex).__name__}
def calc_state(ch,pool,anchor):
 b=anchor["block"]
 st={"block":b,"block_hash":anchor["hash"],"status":"UNRESOLVED"}
 try:
  reserve=unpack(read(ch,pool["pair"],"getReserves()",block=b),3)
  bal0=balance(ch,pool["token0"],pool["pair"],b)
  bal1=balance(ch,pool["token1"],pool["pair"],b)
  balances=[bal0,bal1]
  st.update({"reserve_raw":list(reserve[:2]),
   "balance_raw":balances,
   "surplus_raw":[bal0-reserve[0],bal1-reserve[1]],
   "claimable_if_uncontested_raw":[max(0,bal0-reserve[0]),max(0,bal1-reserve[1])],
   "shortfall_negative_control_raw":[max(0,reserve[0]-bal0),max(0,reserve[1]-bal1)],
   "status":"READ"})
  st["surplus_display"]={
   pool["metadata"][token]["symbol"]:
     float(amount)/10**pool["metadata"][token]["decimals"]
   for token,amount in zip([pool["token0"],pool["token1"]],
                            st["claimable_if_uncontested_raw"])}
  st["valuation_status"]="UNPRICED_GROSS_TOKEN_NOT_NET_CASH"
 except Exception as ex:
  st["exception_kind"]=type(ex).__name__
 return st
def audit_pool_ch(ch,anchors):
 label=ident(ch)
 res=REPORT["results"].setdefault(label,{"chain":ch,"anchors":anchors,"v2":[]})
 for venue,combos in PAIRS[ch].items():
  for a,b in combos:
   item=get_pool(ch,venue,a,b,anchors[0]["block"])
   res["v2"].append(item)
   persist()
   if not item.get("pair") or "token0" not in item:continue
   for anchor in anchors:
    item["states"].append(calc_state(ch,item,anchor))
    persist()
 # Pin recheck at the tail so no reorg changes the evidence cohort.
 later=rpc(ch,"eth_getBlockByNumber",[hex(anchors[0]["block"]),False])
 res["head_rechecked"]=later["hash"]==anchors[0]["hash"]
 persist()
def bento_at(ch,token_key,anchor):
 assert ch==ETH
 token= TOK[ch][token_key][0]
 block=anchor["block"]
 entry={"token":token_key,"block":block,"status":"UNRESOLVED"}
 try:
  direct=balance(ch,token,BENTO,block)
  elastic,base=unpack(read(ch,BENTO,"totals(address)",token,block=block),2)
  strategy=unpack(read(ch,BENTO,"strategyData(address)",token,block=block),3)
  strategy_balance=strategy[2]
  surplus=direct+strategy_balance-elastic
  entry.update({"direct_balance_raw":direct,"strategy_accounted_balance_raw":strategy_balance,
   "total_elastic_raw":elastic,"total_base_shares":base,
   "surplus_claim_raw":max(0,surplus),
   "shortfall_raw":max(0,-surplus),
   "token_decimals":TOK[ch][token_key][1],
   "claim_token_amount":float(max(0,surplus))/10**TOK[ch][token_key][1],
   "status":"READ",
   "rights":"UNVERIFIED_UNTIL_ETH_CALL_DEPOSIT_AND_ATOMIC_WITHDRAW"})
 except Exception as exc:entry["failure_kind"]=type(exc).__name__
 return entry
def bento(ch,anchors):
 r=REPORT["results"][ident(ch)]
 r["bentobox"]={"address":BENTO,"observations":[],"validation":[]}
 for token in BENTO_TOKENS:
  for anchor in anchors[:BENTO_SNAPSHOTS]:
   entry=bento_at(ch,token,anchor)
   r["bentobox"]["observations"].append(entry)
   persist()
 # Deterministic earliest-six positive snapshots by token then descending block.
 positive=[x for x in r["bentobox"]["observations"]
           if x.get("status")=="READ" and x["surplus_claim_raw"]>0]
 for e in positive[:MAX_SKIM_SIMULATIONS]:
  observation={"token":e["token"],"block":e["block"],"status":"UNRESOLVED"}
  r["bentobox"]["validation"].append(observation)
  try:
   token=TOK[ch][e["token"]][0]
   amount=e["surplus_claim_raw"]
   data=encode("deposit(address,address,address,uint256,uint256)",
         token,BENTO,EXTERNAL,amount,0)
   raw=rpc(ch,"eth_call",[{"to":BENTO,"from":EXTERNAL,"data":data},hex(e["block"])])
   amt,shares=unpack(raw,2)
   observation.update({"status":"STATIC_DEPOSIT_SUCCEEDED",
       "credited_amount_raw":amt,"credited_shares_raw":shares,
       "NOTE":"eth_call reverted state after simulation; not an actual deposit and does not demonstrate atomic cash withdrawal or entitlement"})
   if amt>0 and shares>0:
    try:
     gas=rpc(ch,"eth_estimateGas",[{"to":BENTO,"from":EXTERNAL,"data":data},hex(e["block"])])
     observation["deposit_gas_estimate"]=int(gas,16)
    except Exception as exc:observation["gas_error"]=type(exc).__name__
  except Exception as exc:observation["error_kind"]=type(exc).__name__
  persist()
def simulate_v2_positive():
 # Selected earliest six positive claims in each chain (predeclared) for
 # read-only execution validity and estimation, not for profit forecasting.
 for ch in [ETH,BASE]:
  result=REPORT["results"].get(ident(ch),{})
  selected=[]
  for p in result.get("v2",[]):
   for st in p.get("states",[]):
    if st.get("status")=="READ" and any(q>0 for q in st["claimable_if_uncontested_raw"]):
     selected.append((p,st))
  result["positive_observations_count"]=len(selected)
  result["skim_validation"]=[]
  for pool,st in selected[:MAX_SKIM_SIMULATIONS]:
   v={"pool":pool["pair"],"block":st["block"],"status":"UNRESOLVED"}
   result["skim_validation"].append(v)
   calldata=encode("skim(address)",EXTERNAL)
   tx={"to":pool["pair"],"from":EXTERNAL,"data":calldata}
   try:
    raw=rpc(ch,"eth_call",[tx,hex(st["block"])])
    v["simulation_status"]="ETH_CALL_RETURNED_"+("EMPTY_SUCCESS" if raw=="0x" else "OTHER")
    if raw=="0x":
     try:
      gas=rpc(ch,"eth_estimateGas",[tx,hex(st["block"])])
      v["gas_estimated"]=int(gas,16)
      v["gas_at_observed_basefee_wei"]=int(gas,16)*next(a["base_fee_wei"] for a in result["anchors"] if a["block"]==st["block"])
      v["gas_limitations"]="excludes priority fee and L2 L1 data fee"
     except Exception as exc:v["gas_exception"]=type(exc).__name__
    v["status"]="READ_ONLY_SIMULATION"
   except Exception as exc:v["error_kind"]=type(exc).__name__
   persist()
def main():
 persist()
 try:
  init_rpc()
  for ch in [ETH,BASE]:
   anchors=check_head(ch)
   audit_pool_ch(ch,anchors)
   if ch==ETH:bento(ch,anchors)
  simulate_v2_positive()
  REPORT["complete"]=all(REPORT["results"][ident(ch)].get("head_rechecked") for ch in [ETH,BASE])
 except Exception as exc:
  REPORT["errors"].append({"kind":exc.kind if isinstance(exc,RPCFailure) else type(exc).__name__})
 finally:
  REPORT["conservative_ru_charged_attempts"]=SHARED.attempted_ru if SHARED else 0
  REPORT["rpc_request_count"]={ident(ch):x.attempted for ch,x in CLIENT.items()}
  REPORT["no_trades_made"]=True
  REPORT["stage2_eligible"]=False
  persist()
  print(json.dumps({"complete":REPORT["complete"],
    "spent_conservative_ru":REPORT["conservative_ru_charged_attempts"],
    "errors":REPORT["errors"],
    "chains":{k:{"pairs":len(v.get("v2",[])),
      "nonzero_surplus_snapshots":sum(1 for p in v.get("v2",[]) for s in p.get("states",[])
          if any(q>0 for q in s.get("claimable_if_uncontested_raw",[]))),
      "bento_positive_snapshots":sum(s.get("surplus_claim_raw",0)>0 for s in v.get("bentobox",{}).get("observations",[]))}
      for k,v in REPORT["results"].items()}},sort_keys=True))
 return 0 if REPORT["complete"] else 2
if __name__=="__main__":sys.exit(main())
