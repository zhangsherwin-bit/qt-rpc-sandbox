"""Programme III Stage 1 NEW economic sources: intent settlement and ERC-4337 bundling.

Freeze cohorts before reading outcomes. ONLY READ-ONLY BLOCKCHAIN RPC. No key or
wallet in output. Distinguish historical incumbents, fees and true external capture.
Authorised budget: <=400 conservatively estimated RU, reserve 1,500 monthly RU.
"""
import json
import os
import sys
import traceback
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC, AuthenticatedBudget, WeightedLimiter, read_key_status, RPCFailure

OUT=Path("stage1_innovation_evidence")
REQUIRED_CHAINS={
 1:{"label":"ethereum","uniswapx":{
    "dutch_v2":"0x00000011f84b9aa48e5f8aa8b9897600006289be",
    "dutch_v3":"0x0000000015757c461808ea25eb309638b62681cf"},
   "entrypoints":{
    "v0.7":"0x0000000071727de22e5e9d8baf0edac6f37da032",
    "v0.8":"0x4337084d9e255ff0702461cf8895ce9e3b5ff108"}},
 8453:{"label":"base","uniswapx":{
    "dutch_v3":"0x000000008a8330b5d1f43a62bf4c673a49f27ba0",
    "priority":"0x000000001ec5656dcdb24d90dfa42742738de729"},
   "entrypoints":{
    "v0.7":"0x0000000071727de22e5e9d8baf0edac6f37da032",
    "v0.8":"0x4337084d9e255ff0702461cf8895ce9e3b5ff108"}}
}
# Windows selected before inspecting outcomes; non-overlapping and non-contiguous.
# Each window is only a 360-block slice: no extrapolation to annual recurrence.
OFFSETS=[200,20_000,70_000,160_000,360_000]
WINDOW=360
MAX_RECEIPT_TX_PER_FAMILY_CHAIN=8
UNISWAP_FILL_TOPIC="0x"+("0" * 64)  # overwritten and asserted from exact ABI
AA_TOPIC="0x49628fd1471006c1482da88028e9ce4dbb080b815c9b0344d39e5a8e6ec1419f"
TRANSFER_TOPIC="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
REPORT={
 "date_utc":datetime.now(timezone.utc).isoformat(),
 "programme":"QT Programme III Stage 1", "strategy":"innovation-first, cash-profit-first",
 "research_status":"READ_ONLY_EMPIRICAL_SCREEN_NOT_PROFIT",
 "new_families":["UniswapX permissionless intent-auction filler cash",
                 "ERC4337 compensated user-operation bundler"],
 "methodology":{
   "source_selection":"Official published deployed contracts, never chosen after looking at profits",
   "window_length_blocks":WINDOW,"end_offset_from_pinned_head":OFFSETS,
   "receipt_selection":"first eight unique tx per chain+mechanism by block/log index, not by profitability",
   "contract_archive_checks":True,"historical_block_hash_pin":True,
   "cash_priority":"actual token transfer deltas and EIP4337 fee-vs-gas conditional proxy",
   "not_trading_pnl":True,
   "limitations":["UniswapX Fill events do not disclose open-vs-exclusive eligibility",
                  "ERC4337 actualGasCost is a protocol settlement accounting event, not a traced ETH payout",
                  "price conversion, native transfers, gas bidding, exclusivity, adverse selection and offchain costs unmeasured",
                  "samples are disjoint finite windows, no full historical recurrence or capturability inference"]},
 "chain_results":{},"errors":[],"complete":False,
 "live_orders":0,"trades":0,"authenticated_rpc_intended":True,
 "independent_capturability_verified":False,"stage2_promotion":False
}
SESSION={};SHARED_BUDGET=None;SHARED_LIMITER=None;STATUS=None

def sha(sig):
 h=keccak.new(digest_bits=256);h.update(sig.encode());return "0x"+h.hexdigest()
FILL_TOPIC=sha("Fill(bytes32,address,address,uint256)")
assert FILL_TOPIC!="0x"+("0"*64)
assert AA_TOPIC==sha("UserOperationEvent(bytes32,address,address,uint256,bool,uint256,uint256)")
assert TRANSFER_TOPIC==sha("Transfer(address,address,uint256)")
HANDLE_OPS_V7_SELECTOR=sha("handleOps((address,uint256,bytes,bytes,bytes32,uint256,bytes32,bytes,bytes)[],address)")[:10]
def sav():
 OUT.mkdir(exist_ok=True,parents=True)
 (OUT/"REPORT.json").write_text(json.dumps(REPORT,sort_keys=True,indent=2,default=str)+"\n")
def uint(v):
 if not isinstance(v,str) or not v.startswith("0x"):raise ValueError("invalid hex integer")
 return int(v,16)
def addr_topic(v):
 if not isinstance(v,str) or len(v)!=66:raise ValueError("invalid indexed address")
 return "0x"+v[-40:].lower()
def receipt_fee(receipt):
 gas=uint(receipt["gasUsed"])*uint(receipt["effectiveGasPrice"])
 l1=uint(receipt["l1Fee"]) if isinstance(receipt.get("l1Fee"),str) else None
 return {"execution_gas_wei":gas,"reported_l1_fee_wei":l1,
         "chain_total_fee_wei_if_l1_reported":gas+(l1 or 0),
         "l1_fee_completeness":"RECORDED" if l1 is not None else "UNVERIFIED_MAY_BE_INCLUDED_OR_MISSING"}
def get_rpc(ch):
 global SHARED_BUDGET,SHARED_LIMITER,STATUS
 if ch in SESSION:return SESSION[ch]
 if STATUS is None:
  if os.environ.get("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES":
   raise RPCFailure("PROVIDER_ACCOUNT_PERMISSION_NOT_CONFIRMED")
  if os.environ.get("QT_ALLOW_AUTHENTICATED_RPC")!="YES":
   raise RPCFailure("USER_AUTHENTICATED_RU_CONSENT_NOT_ENABLED")
  key=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
  if not key:raise RPCFailure("API_SECRET_NOT_CONFIGURED")
  STATUS=read_key_status(key)
  if STATUS["auth"]!="authenticated":raise RPCFailure("KEY_STATUS_NOT_AUTHENTICATED")
  if STATUS["ru_remaining"] < 2200:raise RPCFailure("INSUFFICIENT_SAFE_RU_RESERVE")
  SHARED_BUDGET=AuthenticatedBudget(STATUS,reserve_floor=1500,max_run_ru=400,approved=True)
  SHARED_LIMITER=WeightedLimiter(cap_ru=max(5,int(STATUS["rate_limit_rpm"]*.55)))
  REPORT["status_snapshot"]={k:STATUS[k] for k in ["auth","ru_remaining","ru_budget","rate_limit_rpm"]}
  REPORT["auth_ru_ceiling"]=SHARED_BUDGET.cap_ru
  sav()
 key=os.environ["BLOCKMACHINE_API_KEY"].strip()
 obj=ReadOnlyRPC(ch,OUT/REQUIRED_CHAINS[ch]["label"]/ "rpc_raw",
                 api_key=key,status=STATUS,budget=SHARED_BUDGET,
                 limiter=SHARED_LIMITER,max_requests=100,max_attempts=2)
 SESSION[ch]=obj
 return obj
def query(ch,m,p):
 return get_rpc(ch).rpc(m,p)
def sample_windows(head):
 return [{"start":head-off-WINDOW+1,"end":head-off,"offset":off}
         for off in OFFSETS]
def unwrap_name(ch,family,address):
 for name,a in REQUIRED_CHAINS[ch][family].items():
  if a.lower()==address.lower():return name
 return None
def parse_fill(l,ch):
 ts=l.get("topics",[])
 if len(ts)!=4 or ts[0].lower()!=FILL_TOPIC.lower():raise ValueError("Fill topic/arity mismatch")
 if len(l.get("data",""))!=66:raise ValueError("Fill nonce invalid")
 return {"type":"fill","tx":l["transactionHash"],"block":uint(l["blockNumber"]),
         "idx":uint(l["logIndex"]),"reactor":l["address"].lower(),
         "reactor_type":unwrap_name(ch,"uniswapx",l["address"]),
         "order_hash":ts[1],"filler":addr_topic(ts[2]),
         "swapper":addr_topic(ts[3]),"nonce":uint(l["data"])}
def parse_aa(l,ch):
 ts=l.get("topics",[])
 if len(ts)!=4 or ts[0].lower()!=AA_TOPIC.lower():raise ValueError("UserOperationEvent topic mismatch")
 data=l.get("data","")
 if len(data)!=2+64*4:raise ValueError("UserOperationEvent data length invalid")
 vals=[int(data[2+i*64:2+(i+1)*64],16) for i in range(4)]
 if vals[1] not in [0,1]:raise ValueError("invalid UserOp success boolean")
 return {"type":"userop","tx":l["transactionHash"],"block":uint(l["blockNumber"]),
         "idx":uint(l["logIndex"]),"entrypoint":l["address"].lower(),
         "entrypoint_version":unwrap_name(ch,"entrypoints",l["address"]),
         "userop_hash":ts[1],"account":addr_topic(ts[2]),"paymaster":addr_topic(ts[3]),
         "nonce":vals[0],"userop_success":bool(vals[1]),
         "actual_gas_cost_wei":vals[2],"actual_gas_used":vals[3]}
def token_deltas(receipt,account):
 account=account.lower()
 table=defaultdict(int)
 for l in receipt.get("logs",[]):
  t=l.get("topics",[])
  if len(t)!=3 or t[0].lower()!=TRANSFER_TOPIC:continue
  raw=l.get("data","")
  if not isinstance(raw,str) or len(raw)!=66:continue
  a=addr_topic(t[1]);b=addr_topic(t[2]);v=uint(raw)
  if a==account:table[l["address"].lower()]-=v
  if b==account:table[l["address"].lower()]+=v
 return {k:str(v) for k,v in sorted(table.items()) if v!=0}
def beneficiary_from_tx(tx):
 raw=tx.get("input","")
 if not isinstance(raw,str) or not raw.lower().startswith(HANDLE_OPS_V7_SELECTOR):
  return None
 # handleOps(PackedUserOperation[],address) uses 2-word ABI head.
 if len(raw)<10+128:return None
 return "0x"+raw[10+64+24:10+64+64].lower()
def inspect_receipts(ch,family,events):
 chosen=[]
 seen=set()
 for e in sorted(events,key=lambda x:(x["block"],x["idx"])):
  h=e["tx"].lower()
  if h not in seen:
   seen.add(h);chosen.append(h)
  if len(chosen)>=MAX_RECEIPT_TX_PER_FAMILY_CHAIN:break
 results=[]
 for h in chosen:
  item={"tx":h,"classification":"UNRESOLVED"}
  results.append(item)
  try:
   tx=query(ch,"eth_getTransactionByHash",[h])
   receipt=query(ch,"eth_getTransactionReceipt",[h])
   if not isinstance(tx,dict) or not isinstance(receipt,dict):raise ValueError("missing tx/receipt")
   if uint(receipt["status"])!=1:raise ValueError("unsuccessful transaction despite success log")
   all_events=[e for e in events if e["tx"].lower()==h]
   if not all_events:raise ValueError("no sample event")
   item.update({"block":uint(tx["blockNumber"]),"tx_sender":tx["from"].lower(),
                "tx_to":str(tx.get("to","")).lower(),
                "observed_event_count_in_scanned_log_batch":len(all_events),
                "fees":receipt_fee(receipt)})
   if family=="uniswapx":
    fillers=sorted(set(e["filler"] for e in all_events))
    item["fillers"]=fillers
    item["filler_token_deltas_from_transfer_logs"]={f:token_deltas(receipt,f) for f in fillers}
    item["receipt_selector"]=str(tx.get("input",""))[:10]
    item["classification"]="HISTORIC_FILL_CONFIRMED_UNPRICED_TOKENS_NO_OPEN_AUCTION_PROOF"
   else:
    beneficiary=beneficiary_from_tx(tx)
    actual=sum(e["actual_gas_cost_wei"] for e in all_events)
    expected_receipt_events=[
      l for l in receipt["logs"]
      if (l["address"].lower() in [v.lower() for v in REQUIRED_CHAINS[ch]["entrypoints"].values()]
          and l.get("topics",[]) and l["topics"][0].lower()==AA_TOPIC)]
    total_reconciled=0
    for l in expected_receipt_events:
     if l["address"].lower() not in [e["entrypoint"] for e in all_events]:continue
     total_reconciled+=int(l["data"][2+64*2:2+64*3],16)
    item.update({"beneficiary":beneficiary,
        "sum_userop_actualGasCost_wei":actual,
        "receipt_all_entrypoint_events_gas_cost_wei":total_reconciled,
        "receipt_event_set_complete":total_reconciled==actual,
        "payer_is_beneficiary":beneficiary is not None and beneficiary==tx["from"].lower()})
    if beneficiary and beneficiary==tx["from"].lower() and total_reconciled==actual:
     paid=item["fees"]["chain_total_fee_wei_if_l1_reported"]
     item["conditional_Eth_revenue_less_tx_fee_wei"]=actual-paid
     item["classification"]="THIRD_PARTY_4337_FEE_PROXY_UNTRACED_BENEFICIARY_SETTLEMENT"
    else:
     item["classification"]="BENEFICIARY_OR_RECEIPT_NOT_ATTRIBUTABLE"
  except Exception as exc:
   item["error_type"]=type(exc).__name__
   item["error_summary"]=str(exc)[:180].replace(os.environ.get("BLOCKMACHINE_API_KEY",""),"[redacted]") if os.environ.get("BLOCKMACHINE_API_KEY") else str(exc)[:180]
  sav()
 return results
def do_chain(ch):
 label=REQUIRED_CHAINS[ch]["label"]
 res={"chain_id":ch,"chain":label,"windows":[],"by_family":{},"errors":[],"complete":False}
 REPORT["chain_results"][label]=res
 if uint(query(ch,"eth_chainId",[]))!=ch:raise ValueError("chain identity mismatch")
 head=uint(query(ch,"eth_blockNumber",[]))-6
 header=query(ch,"eth_getBlockByNumber",[hex(head),False])
 if header is None or uint(header["number"])!=head:raise ValueError("non-canonical head")
 res["pin"]={"block":head,"hash":header["hash"],"timestamp":uint(header["timestamp"])}
 windows=sample_windows(head)
 if any(w["start"]<0 for w in windows):raise ValueError("sample predates genesis")
 res["windows"]=windows
 # Before querying event outcomes, verify targets exist at sample tip.
 for family in ["uniswapx","entrypoints"]:
  fam={"deployed":[],"log_batches":[],"events":[],"selected_receipts":[],
       "activity_count":0,"distinct_txs":0,"dominant_actor_share":None,"state":"UNRESOLVED"}
  res["by_family"][family]=fam
  addresses=list(REQUIRED_CHAINS[ch][family].values())
  for a in addresses:
   code=query(ch,"eth_getCode",[a,hex(head)])
   fam["deployed"].append({"address":a,"code_present":bool(code and code!="0x")})
  for w in windows:
   win={"start":w["start"],"end":w["end"],"offset":w["offset"]}
   fam["log_batches"].append(win)
   try:
    # source selection frozen, no adaptive re-scanning after outcome checks
    logs=query(ch,"eth_getLogs",[{"address":addresses,
         "fromBlock":hex(w["start"]),"toBlock":hex(w["end"]),
         "topics":[FILL_TOPIC if family=="uniswapx" else AA_TOPIC]}])
    win["status"]="OK";win["count"]=len(logs)
    for l in logs:
     a=l["address"].lower()
     if a not in [x.lower() for x in addresses]:raise ValueError("unexpected emitting address")
     e=parse_fill(l,ch) if family=="uniswapx" else parse_aa(l,ch)
     fam["events"].append(e)
   except Exception as exc:
    win["status"]="UNRESOLVED";win["exception"]=type(exc).__name__
    if isinstance(exc,RPCFailure):
     win["failure_kind"]=exc.kind
     if get_rpc(ch).aborted:break
   sav()
  ev=fam["events"]
  fam["activity_count"]=len(ev)
  fam["distinct_txs"]=len(set(e["tx"] for e in ev))
  actors=Counter(e["filler"] if family=="uniswapx" else e["account"] for e in ev)
  fam["unique_actors"]=len(actors)
  fam["top_actor_share"]=max(actors.values())/len(ev) if ev else None
  fam["distinct_emitting_contracts"]=sorted(set(e["reactor"] if family=="uniswapx" else e["entrypoint"] for e in ev))
  fam["complete_log_windows"]=sum(w.get("status")=="OK" for w in fam["log_batches"])
  if not get_rpc(ch).aborted:
   fam["selected_receipts"]=inspect_receipts(ch,family,ev)
  fam["state"]="WINDOWS_COMPLETE" if fam["complete_log_windows"]==len(OFFSETS) else "SAMPLE_INCOMPLETE"
  sav()
 again=query(ch,"eth_getBlockByNumber",[hex(head),False])
 res["anchor_recheck"]=again["hash"]==res["pin"]["hash"]
 res["complete"]=res["anchor_recheck"] and all(f["state"]=="WINDOWS_COMPLETE" for f in res["by_family"].values())
 sav()
def main():
 sav()
 for ch in REQUIRED_CHAINS:
  try:do_chain(ch)
  except Exception as exc:
   REPORT["errors"].append({"chain":ch,"kind":exc.kind if isinstance(exc,RPCFailure) else type(exc).__name__})
   sav()
   if isinstance(exc,RPCFailure) and exc.kind in ("AUTHENTICATED_RUN_RU_CAP_REACHED","RU_BUDGET_EXHAUSTED","AUTH_OR_ACCESS_DENIED"):break
 REPORT["spent_ru_conservative_attempts"]=SHARED_BUDGET.attempted_ru if SHARED_BUDGET else 0
 REPORT["rpc_attempts_by_chain"]={REQUIRED_CHAINS[k]["label"]:v.attempted for k,v in SESSION.items()}
 REPORT["complete"]=all(r["complete"] for r in REPORT["chain_results"].values()) and len(REPORT["chain_results"])==2
 REPORT["stage2_promotion"]=False
 sav()
 print(json.dumps({"complete":REPORT["complete"],"estimated_ru_attempts":REPORT["spent_ru_conservative_attempts"],
  "requests":REPORT["rpc_attempts_by_chain"],
  "sample_counts":{k:{fam:{"events":v["activity_count"],"tx":v["distinct_txs"],"windows":v["complete_log_windows"]}
        for fam,v in result["by_family"].items()} for k,result in REPORT["chain_results"].items()},
  "error_kinds":REPORT["errors"],"no_trades":True},sort_keys=True))
if __name__=="__main__":main()
