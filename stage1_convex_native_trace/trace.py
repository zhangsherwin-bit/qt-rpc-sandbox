"""Frozen external-value trace of selected Convex reward conversion.

Historical block/tx fixed before any new data. Only 25-RU read-only
debug_traceTransaction plus <=5 ordinary reads. No sending or wallets.
Do not claim profit from ERC20 transfers; reconcile ACTUAL native ETH flows.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,os
from qt_rpc.client import ReadOnlyRPC,AuthenticatedBudget,read_key_status,RPCFailure

TX="0x211f62115ec9c55f349b6fdd100f6e0c7bd6a45baad70f5e9340f8f64150db4f"
BLOCK=25941501
ACCOUNT="0x229965b0ee9ed33450317e6725edec3909dcd340"
EXPECTED_WETH_WITHDRAW=11379084255985277
EXPECTED_GAS=52618514415240
ARCHIVED_END_BLOCK_DELTA=69675416337178
RESERVE_RU=1500
MAX_SPEND_RU=35
OUT=Path("convex_native_trace_evidence")
def parse_value(v):
 if isinstance(v,str) and v.startswith("0x"):return int(v,16)
 if isinstance(v,int) and v>=0:return v
 return 0
def collect_value_transfers(trace,account):
    """Return individual native transfers only; ignore DELEGATECALL shadow values."""
    nodes=[];all_calls=0;stack=[(trace,0)]
    while stack:
        frame,depth=stack.pop()
        if not isinstance(frame,dict):continue
        all_calls+=1
        if all_calls>10000:raise ValueError("too many trace frames")
        kind=str(frame.get("type","")).upper()
        val=parse_value(frame.get("value","0x0"))
        if kind in ("CALL","CALLCODE","CREATE","CREATE2","SELFDESTRUCT") and val>0:
            # CALLCODE changes execution context but does not transfer ETH;
            # exclude, avoiding double accounting.
            if kind!="CALLCODE":
                src=str(frame.get("from","")).lower()
                dst=str(frame.get("to","")).lower()
                if src==account or dst==account:
                    if not (src==dst):
                        nodes.append({"kind":kind,"from":src,"to":dst,
                                      "value_wei":val,"depth":depth,
                                      "error":bool(frame.get("error"))})
        for child in reversed(frame.get("calls") or []):
            stack.append((child,depth+1))
    received=sum(x["value_wei"] for x in nodes if x["to"]==account and not x["error"])
    sent=sum(x["value_wei"] for x in nodes if x["from"]==account and not x["error"])
    return {"native_account_internal_received_wei":received,
            "native_account_internal_sent_wei":sent,
            "net_internal_native_value_wei":received-sent,
            "account_relevant_value_transfers":nodes,
            "trace_total_frames":all_calls}
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 report={"utc":datetime.now(timezone.utc).isoformat(),
         "chain_id":1,"transaction":TX,"block":BLOCK,
         "source":"Previously frozen 2026-10-19 Stage 1 CRV caller payout recipient",
         "frozen_native_balance_delta_wei":ARCHIVED_END_BLOCK_DELTA,
         "frozen_gas_wei":EXPECTED_GAS,
         "historical_token_reward_conversion_wei":EXPECTED_WETH_WITHDRAW,
         "max_research_ru":MAX_SPEND_RU,"protected_account_ru":RESERVE_RU,
         "status":"UNRESOLVED","onchain_writes":0,
         "annual_profit_estimate":None,"stage2_capture_confirmed":False}
 try:
  if os.environ.get("QT_ALLOW_AUTHENTICATED_RPC")!="YES" or os.environ.get("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES":
   raise RPCFailure("AUTHENTICATED_USAGE_NOT_APPROVED")
  key=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
  if not key:raise RPCFailure("KEY_NOT_CONFIGURED")
  status=read_key_status(key)
  if status.get("ru_remaining",0)<RESERVE_RU+MAX_SPEND_RU:raise RPCFailure("RU_BUDGET_RESERVE_PROTECTED")
  b=AuthenticatedBudget(status,reserve_floor=RESERVE_RU,max_run_ru=MAX_SPEND_RU,approved=True)
  rpc=ReadOnlyRPC(1,OUT/"raw",api_key=key,status=status,budget=b,max_requests=8,max_attempts=1)
  report["ru_before_reported"]=status.get("ru_remaining")
  report["provider_rate_per_min"]=status.get("rate_limit_rpm")
  if int(rpc.rpc("eth_chainId",[]),16)!=1:raise RuntimeError("not Ethereum")
  block=rpc.rpc("eth_getBlockByNumber",[hex(BLOCK),False])
  if not isinstance(block,dict) or int(block["number"],16)!=BLOCK:raise RuntimeError("wrong block")
  miner=str(block.get("miner","")).lower()
  report["block_miner_or_fee_recipient"]=miner
  trace=rpc.rpc("debug_traceTransaction",[TX,{"tracer":"callTracer","timeout":"30s"}])
  if not isinstance(trace,dict):raise RuntimeError("no callTracer object")
  report.update(collect_value_transfers(trace,ACCOUNT))
  report["recipient_is_block_fee_recipient"]=any(
      x["from"]==ACCOUNT and x["to"]==miner for x in report["account_relevant_value_transfers"])
  # Repeat existing native balance measurement for independently reconcilable value accounting.
  parent=int(rpc.rpc("eth_getBalance",[ACCOUNT,hex(BLOCK-1)]),16)
  after=int(rpc.rpc("eth_getBalance",[ACCOUNT,hex(BLOCK)]),16)
  report["native_balance_delta_wei"]=after-parent
  report["native_trace_value_minus_gas_wei"]=report["net_internal_native_value_wei"]-EXPECTED_GAS
  report["native_trace_reconciles_target_block_delta"]=(report["native_trace_value_minus_gas_wei"]==after-parent)
  report["matches_prior_balance_audit"]=(after-parent==ARCHIVED_END_BLOCK_DELTA)
  report["historical_native_net_if_no_other_block_effects_wei"]=after-parent
  report["ru_attempted_conservative"]=b.attempted_ru
  report["requests_sent"]=rpc.attempted
  report["status"]="TRACE_RECONCILED" if report["native_trace_reconciles_target_block_delta"] and report["matches_prior_balance_audit"] else "TRACE_UNRECONCILED"
 except Exception as exc:
  report["error_kind"]=exc.kind if isinstance(exc,RPCFailure) else type(exc).__name__
  report["status"]="UNRESOLVED"
 (OUT/"REPORT.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
 print(json.dumps({k:report.get(k) for k in ("status","ru_attempted_conservative",
       "native_balance_delta_wei","native_trace_value_minus_gas_wei",
       "native_trace_reconciles_target_block_delta",
       "native_account_internal_sent_wei","native_account_internal_received_wei",
       "recipient_is_block_fee_recipient","error_kind")},sort_keys=True))
 return 0 if report["status"]=="TRACE_RECONCILED" else 2
if __name__=="__main__":raise SystemExit(main())
