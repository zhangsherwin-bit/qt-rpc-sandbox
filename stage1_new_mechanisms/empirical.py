"""Programme III Stage 1: independent peg-stabilisation and intent-filling probes.

One predeclared bounded empirical tranche. A 2026-10-19 user-authorised account
is required. No wallet, signing, money movement, broadcasts, secret persistence
or backdoor on 401/403/429. Historical evidence is NOT own trading income.
"""
import hashlib, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from Crypto.Hash import keccak
import requests
from qt_rpc.client import ReadOnlyRPC, AuthenticatedBudget, read_key_status, RPCFailure

OUT=Path("stage1_independent_evidence")
ETH=1
BASE=8453
BUDGET_MAX_RU=280
ADDRESS=[
 ("USDC","0x9201da0D97CaAAff53f01B2fB56767C7072dE340"),
 ("USDT","0xFb726F57d251aB5C731E5C64eD4F5F94351eF9F3"),
 ("pyUSD","0x3fA20eAa107DE08B38a8734063D605d5842fe09C"),
 ("frxUSD","0x338Cb2D827112d989A861cDe87CD9FfD913A1f9D")
]
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
SMOKE_ETH_BLOCK=0xe4e1c0
SMOKE_BASE_BLOCK=10000000
CALLER="0x000000000000000000000000000000000000dEaD"
STATE_OFFSETS=[0,50000,180000,500000]
EVENT_OFFSETS=[500,75000,200000,500000,900000]
EVENT_WINDOW=950

R={"date_utc":datetime.now(timezone.utc).isoformat(),
   "question":"Are publicly initiated Curve crvUSD PegKeeperV2 LP-token bonuses a recurring, redeemable, independently capturable cash source?",
   "separate_mechanism":"UniswapX permissionless non-exclusive Dutch auction filler surplus; eligibility and public order-flow screen only",
   "contracts_source":"https://docs.curve.finance/developer/deployments/integration",
   "mechanism_source":"https://docs.curve.finance/developer/crvusd/pegkeepers/peg-keeper-v2/",
   "intent_source":"https://developers.uniswap.org/docs/liquidity/uniswapx/filling/overview",
   "frozen":{"keepers":ADDRESS,"state_offsets":STATE_OFFSETS,
             "event_offsets":EVENT_OFFSETS,"event_window_blocks":EVENT_WINDOW,
             "smoke_eth_block":SMOKE_ETH_BLOCK,"smoke_base_block":SMOKE_BASE_BLOCK,
             "max_authenticated_ru":BUDGET_MAX_RU,
             "caller":"non-funded dummy, used in eth_call simulation only",
             "no_outcome_based_cohort_selection":True},
   "smoke":{},"pegkeeper":{"snapshots":[],"log_windows":[],"unique_transactions":[],
                      "cash_exit_quotations":[]},
   "uniswapx":{"requests":[],"chains":[]},
   "errors":[],"complete":False,"signed_transactions":0,"broadcasts":0,
   "actual_cash_pnl":None,"own_capturability_proven":False,
   "stage2_promoted":False}
def write():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(R,indent=2,sort_keys=True,default=str)+"\n")
def sig(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
def selector(s):return sig(s)[:10]
def word(n):return format(int(n),"064x")
def address_from_hex(x):
 if not isinstance(x,str) or len(x)!=66:return None
 return "0x"+x[-40:]
def safe_hex(h):
 if not isinstance(h,str) or not h.startswith("0x") or len(h)>1000:raise ValueError("invalid ABI hex result")
 return int(h,16)
def contract_call(rpc,to,sigstr,block,args=()):
 data=selector(sigstr)+"".join(word(x) for x in args)
 return rpc.rpc("eth_call",[{"to":to,"data":data},hex(block)])
def get_addr(rpc,to,name,block):
 return address_from_hex(contract_call(rpc,to,name,block))
def get_uint(rpc,to,name,block):
 return safe_hex(contract_call(rpc,to,name,block))
def state(rpc,keeper,at,name):
 row={"name":name,"address":keeper,"block":at,"point_in_time":True}
 try:
  if rpc.rpc("eth_getCode",[keeper,hex(at)])=="0x":
   row["classification"]="NOT_DEPLOYED_AT_BLOCK"
   return row
  for key,function in [("caller_estimate_lp_raw","estimate_caller_profit()"),
                       ("caller_share_ppm_100k","caller_share()"),
                       ("last_change_seconds","last_change()"),
                       ("debt_crvusd_raw","debt()")]:
   try:row[key]=get_uint(rpc,keeper,function,at)
   except Exception as e:row[key+"_error"]=type(e).__name__
  try:
   pool=get_addr(rpc,keeper,"pool()",at)
   if pool:row["pool"]=pool
  except Exception as e:row["pool_error"]=type(e).__name__
  if row.get("caller_estimate_lp_raw",0)>0:
   # eth_call runs state changes only in the sandboxed EVM simulation.
   # It NEVER sends a transaction and can't establish inclusion/competition.
   payload=selector("update(address)")+word(int(CALLER,16))
   try:
    val=rpc.rpc("eth_call",[{"to":keeper,"from":CALLER,
                             "data":payload},hex(at)])
    row["simulated_update_beneficiary_lp_raw"]=safe_hex(val)
    row["simulation_only_not_inclusion"]=True
   except Exception as e:row["update_simulation_error"]=type(e).__name__
  row["classification"]="QUOTE_ONLY_NONCASH"
 except RPCFailure as e:
  row["classification"]="UNRESOLVED_RPC"
  row["error_kind"]=e.kind
  if e.kind in ("AUTH_OR_ACCESS_DENIED","RU_BUDGET_EXHAUSTED","AUTHENTICATED_RUN_RU_CAP_REACHED","CIRCUIT_OPEN"):
   raise
 except Exception as e:
  row["classification"]="UNRESOLVED"
  row["error_kind"]=type(e).__name__
 return row
def quote_usdc(rpc,row,at):
 if row.get("caller_estimate_lp_raw",0)<=0 or not row.get("pool"):return None
 pool=row["pool"]
 obj={"keeper":row["address"],"block":at,"pool":pool,
      "lp_profit_raw":row["caller_estimate_lp_raw"],
      "cash_classification":"UNRESOLVED"}
 try:
  coins=[]
  for j in (0,1):
   coins.append(get_addr(rpc,pool,"coins(uint256)",at,(j,)))
  obj["coins"]=coins
  index=next((i for i,v in enumerate(coins) if v and v.lower()==USDC),None)
  if index is None:
   obj["cash_classification"]="NO_DIRECT_USDC_POOL_COIN"
   return obj
  obj["usdc_coin_index"]=index
  # StableSwap interfaces differ. Try both documented selectors.
  for fn in ("calc_withdraw_one_coin(uint256,int128)",
             "calc_withdraw_one_coin(uint256,uint256)"):
   try:
    raw=contract_call(rpc,pool,fn,at,(row["caller_estimate_lp_raw"],index))
    obj["usdc_quote_raw"]=safe_hex(raw)
    obj["usdc_quote"]=obj["usdc_quote_raw"]/1e6
    obj["quote_function"]=fn
    obj["cash_classification"]="FINITE_SAME_BLOCK_WITHDRAWAL_QUOTE_ONLY"
    obj["gas_executability_and_competition_unproven"]=True
    break
   except Exception as e:
    obj[fn+"_error"]=type(e).__name__
 except Exception as e:
  obj["cash_classification"]="UNRESOLVED_RPC"
  obj["error_type"]=type(e).__name__
 return obj
def onchain(key):
 status=read_key_status(key)
 R["auth"]={"status":status.get("auth"),"ru_before":status.get("ru_remaining"),
            "reported_ru_per_min":status.get("rate_limit_rpm"),
            "ru_budget":status.get("ru_budget"),"is_exhausted":status.get("is_exhausted")}
 if status.get("auth")!="authenticated":raise RuntimeError("No verified account")
 budget=AuthenticatedBudget(status,approved=True,reserve_floor=1500,max_run_ru=BUDGET_MAX_RU)
 eth=ReadOnlyRPC(ETH,OUT/"rpc_attempts"/"ethereum",
                  api_key=key,status=status,budget=budget,
                  max_requests=190,max_attempts=1)
 base=ReadOnlyRPC(BASE,OUT/"rpc_attempts"/"base",
                  api_key=key,status=status,budget=budget,
                  max_requests=3,max_attempts=1)
 for chain,client,historic in [("ethereum",eth,SMOKE_ETH_BLOCK),("base",base,SMOKE_BASE_BLOCK)]:
  cid=int(client.rpc("eth_chainId",[]),16)
  header=client.rpc("eth_getBlockByNumber",[hex(historic),False])
  good=cid==client.chain_id and isinstance(header,dict) and header.get("hash") and int(header["number"],16)==historic
  R["smoke"][chain]={"chain_id":cid,"historical_block":historic,"hash":header.get("hash") if isinstance(header,dict) else None,
                    "pass":bool(good)}
  write()
  if not good:raise RuntimeError("AUTHENTICATED_HISTORICAL_ARCHIVE_PREFLIGHT_FAILED_"+chain)
 R["smoke"]["pass"]=True
 tip=int(eth.rpc("eth_blockNumber",[]),16)
 anchor=tip-5
 R["pegkeeper"]["frozen_anchor"]=anchor
 snapshot_blocks=[anchor-o for o in STATE_OFFSETS]
 for at in snapshot_blocks:
  block=eth.rpc("eth_getBlockByNumber",[hex(at),False])
  if not isinstance(block,dict) or not block.get("hash"):raise RuntimeError("UNAVAILABLE_STATE_BLOCK")
  R["pegkeeper"]["snapshots"].append({"block":at,"header_hash":block["hash"],
                   "timestamp":int(block["timestamp"],16),"keepers":[]})
  slot=R["pegkeeper"]["snapshots"][-1]
  for name,keeper in ADDRESS:
   obs=state(eth,keeper,at,name)
   slot["keepers"].append(obs)
   if obs.get("caller_estimate_lp_raw",0)>0:
    x=quote_usdc(eth,obs,at)
    if x is not None:R["pegkeeper"]["cash_exit_quotations"].append(x)
   write()
 topics=[sig("Provide(uint256)"),sig("Withdraw(uint256)")]
 holders=[a for _,a in ADDRESS]
 txs={}
 for offset in EVENT_OFFSETS:
  hi=anchor-offset;lo=hi-EVENT_WINDOW+1
  w={"from_block":lo,"to_block":hi,"state":"UNRESOLVED","events":None}
  R["pegkeeper"]["log_windows"].append(w)
  try:
   logs=eth.rpc("eth_getLogs",[{"address":holders,
        "topics":[topics],"fromBlock":hex(lo),"toBlock":hex(hi)}])
   w["state"]="OK";w["events"]=len(logs)
   for ev in logs:
    tx=ev["transactionHash"].lower()
    if tx not in txs:
     txs[tx]={"tx":tx,"block":int(ev["blockNumber"],16),
              "pegkeeper":ev["address"],"event_logs":0,"event_topics":[]}
    txs[tx]["event_logs"]+=1
    txs[tx]["event_topics"].append(ev["topics"][0])
  except RPCFailure as e:
   w["error_kind"]=e.kind
   if e.kind in ("AUTH_OR_ACCESS_DENIED","RU_BUDGET_EXHAUSTED","AUTHENTICATED_RUN_RU_CAP_REACHED","CIRCUIT_OPEN"):
    raise
  except Exception as e:w["error_type"]=type(e).__name__
  write()
 # Freeze receipt selection deterministically by lowest ascending block and tx id.
 for tx in sorted(txs.values(),key=lambda x:(x["block"],x["tx"]))[:12]:
  try:
   receipt=eth.rpc("eth_getTransactionReceipt",[tx["tx"]])
   transaction=eth.rpc("eth_getTransactionByHash",[tx["tx"]])
   if not receipt or not transaction:raise RuntimeError("receipt or transaction missing")
   tx["sender"]=transaction.get("from")
   tx["gas_used"]=int(receipt.get("gasUsed","0x0"),16)
   tx["gas_price_wei"]=int(receipt.get("effectiveGasPrice","0x0"),16)
   tx["gas_paid_eth"]=tx["gas_used"]*tx["gas_price_wei"]/1e18
   tx["success"]=receipt.get("status")=="0x1"
   tx["direct_caller_profit_transfer_not_proven"]=True
  except Exception as e:tx["receipt_error"]=type(e).__name__
  write()
 R["pegkeeper"]["unique_transactions"]=sorted(txs.values(),key=lambda x:(x["block"],x["tx"]))
 R["pegkeeper"]["all_log_windows_complete"]=all(x["state"]=="OK" for x in R["pegkeeper"]["log_windows"])
 R["auth"]["ru_attempts_max_conservative"]=budget.attempted_ru
 R["auth"]["ru_remaining_initial_minus_attempts_lower_bound"]=status["ru_remaining"]-budget.attempted_ru
 write()
def public_intents():
 # Public API only; no credential, order placement, route changes or API key.
 urls=[("ethereum","https://api.uniswap.org/v2/orders?orderStatus=open&chainId=1&orderType=Dutch_V2&limit=50"),
       ("base","https://api.uniswap.org/v2/orders?orderStatus=open&chainId=8453&orderType=Dutch_V3&limit=50")]
 for ch,url in urls:
  record={"chain":ch,"http_status":None,"class":"UNRESOLVED"}
  R["uniswapx"]["requests"].append(record)
  try:
   res=requests.get(url,timeout=(8,20),allow_redirects=False,
       headers={"Accept":"application/json","User-Agent":"QT-Stage1-Research/1"})
   raw=res.content[:1500000]
   archive=OUT/"public_order_feeds";archive.mkdir(parents=True,exist_ok=True)
   (archive/(ch+".response")).write_bytes(raw)
   (archive/(ch+".request")).write_text("GET "+url+"\n")
   record["http_status"]=res.status_code
   record["sha256"]=hashlib.sha256(raw).hexdigest()
   record["response_bytes"]=len(raw)
   if res.status_code!=200:
    record["class"]="PROVIDER_UNAVAILABLE_OR_DENIED"
   else:
    data=res.json()
    if isinstance(data,list):orders=data
    elif isinstance(data,dict):
     orders=data.get("orders",data.get("data",[]))
     if isinstance(orders,dict):orders=orders.get("orders",[])
    else:orders=[]
    if not isinstance(orders,list):
     record["class"]="RESPONSE_SCHEMA_UNEXPECTED"
    else:
     record["class"]="PUBLIC_ORDER_FEED_OBSERVED"
     record["returned_orders"]=len(orders)
     record["schema_first_order_keys"]=sorted(list(orders[0].keys()))[:25] if orders and isinstance(orders[0],dict) else []
     record["cash_profit_proven"]=False
   R["uniswapx"]["chains"].append(record)
  except Exception as e:
   record["class"]="UNRESOLVED_TRANSPORT"
   record["error_type"]=type(e).__name__
  write()
def main():
 write()
 key=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
 if os.environ.get("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES" or os.environ.get("QT_ALLOW_AUTHENTICATED_RPC")!="YES" or not key:
  R["errors"].append({"kind":"MISSING_PERMISSIONS_OR_KEY"})
  write();print('BLOCKED: authorisation or key not supplied, 0 on-chain requests');return 2
 try:
  onchain(key)
 except RPCFailure as e:
  R["errors"].append({"phase":"onchain","kind":e.kind})
 except Exception as e:
  R["errors"].append({"phase":"onchain","kind":type(e).__name__})
 write()
 # Still test public intent access if archive RPC fails, entirely separate API.
 public_intents()
 R["complete"]=bool(R["smoke"].get("pass")) and R["pegkeeper"].get("all_log_windows_complete") is True
 write()
 print(json.dumps({"complete":R["complete"],"smoke":R["smoke"].get("pass"),
      "keeper_logs":sum(x.get("events") or 0 for x in R["pegkeeper"]["log_windows"]),
      "keeper_quote_positive_snapshots":sum(o.get("caller_estimate_lp_raw",0)>0 for s in R["pegkeeper"]["snapshots"] for o in s["keepers"]),
      "unique_keeper_event_transactions":len(R["pegkeeper"]["unique_transactions"]),
      "uniswapx_classes":[(x["chain"],x["class"],x.get("returned_orders")) for x in R["uniswapx"]["chains"]],
      "attempted_ru":R["auth"].get("ru_attempts_max_conservative"),
      "errors":R["errors"]},sort_keys=True))
 return 0 if R["complete"] else 1
if __name__=="__main__":sys.exit(main())
