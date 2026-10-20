"""QT Stage1 rights/retention: two PRE-SELECTED historic gross reward tails.
Read-only, bounded <=115 estimated RU; no live transactions or new purchases.
Selections POST HOC from archived original Convex 805 reward operations,
two different beneficiary addresses. Historical incumbent != QT opportunity.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import os,json
from qt_rpc.client import ReadOnlyRPC,AuthenticatedBudget,read_key_status,RPCFailure

TARGETS=[
 {"tx":"0x80040416b1d01c1349eb5fcbade8351bfbfdb1709f208dba46f096ef1207499d",
  "block":26133003,"recipient":"0x96e0b3b687f71b7de00dd4641c35f6f1b50fb1d1",
  "crv_wei":385298381897244354451},
 {"tx":"0x51a17bdcc45b22f058fea4a6a34b70219c429243182a2a1f1039be9b06c92795",
  "block":25945376,"recipient":"0x229965b0ee9ed33450317e6725edec3909dcd340",
  "crv_wei":164154511351069237764}]
TOKEN="0xd533a949740bb3306d119cc777fa900ba034cd52"
BOOSTER="0xf403c135812408bfbe8713b5a23a04b3d48aae31"
WETH="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
TRANSFER="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
OUT=Path("stage1_rights_tail_evidence")
MAX_RU=115
FLOOR=1500
def adr(topic):
 if not isinstance(topic,str) or len(topic)!=66:raise ValueError("invalid address topic")
 return "0x"+topic[-40:].lower()
def n(v):
 if isinstance(v,str) and v.startswith("0x"):return int(v,16)
 if isinstance(v,int) and v>=0:return v
 return 0
def token_flows(rec,parties):
 out=defaultdict(lambda:defaultdict(int))
 for log in rec.get("logs",[]):
  topics=log.get("topics",[])
  if len(topics)!=3 or str(topics[0]).lower()!=TRANSFER:continue
  token=log.get("address","").lower()
  if token not in (TOKEN,WETH):continue
  a=adr(topics[1]);b=adr(topics[2]);q=n(log["data"])
  if a in parties:out[a][token]-=q
  if b in parties:out[b][token]+=q
 return {addr:{asset:str(v) for asset,v in data.items() if v}
         for addr,data in out.items()}
def count_frozen_reward(rec,recipient):
 return sum(n(l["data"]) for l in rec.get("logs",[])
  if l.get("address","").lower()==TOKEN and len(l.get("topics",[]))==3
  and l["topics"][0].lower()==TRANSFER and adr(l["topics"][1])==BOOSTER
  and adr(l["topics"][2])==recipient)
def native_transfers(frame,accounts,miner):
 out=[];stack=[(frame,False,0)];frames=0
 while stack:
  o,parent_failed,depth=stack.pop()
  if not isinstance(o,dict):continue
  frames+=1
  if frames>15000:raise ValueError("trace too large")
  failed=parent_failed or bool(o.get("error"))
  kind=str(o.get("type","")).upper()
  frm=str(o.get("from","")).lower();to=str(o.get("to","")).lower()
  value=n(o.get("value","0x0"))
  if (not failed and kind in ("CALL","CREATE","CREATE2","SELFDESTRUCT")
    and value and frm!=to and (frm in accounts or to in accounts or to==miner)):
   out.append({"from":frm,"to":to,"value_wei":str(value),
               "to_block_fee_recipient":to==miner,"depth":depth})
  for child in reversed(o.get("calls") or []):stack.append((child,failed,depth+1))
 delta={}
 for a in accounts:
  received=sum(int(e["value_wei"]) for e in out if e["to"]==a)
  spent=sum(int(e["value_wei"]) for e in out if e["from"]==a)
  delta[a]={"native_received_wei":str(received),
            "native_sent_wei":str(spent),"native_net_wei":str(received-spent),
            "native_sent_to_block_fee_recipient_wei":str(sum(int(e["value_wei"])for e in out if e["from"]==a and e["to_block_fee_recipient"]))}
 return {"relevant_native_value_transfers":out,
         "net_native_flow_by_address":delta,"trace_frame_count":frames}
def run():
 OUT.mkdir(exist_ok=True,parents=True)
 report={"timestamp":datetime.now(timezone.utc).isoformat(),
    "baseline_archive_sha256":"3d5dd9777ab1636b7d95a0a56546ff7ebee2bab118377539045193acd0d9e794",
    "selection":"retrospective largest gross CRV caller bounty from each of two different recipient addresses",
    "limitations":"No prewinner access/inclusion, not an independent replication, token residue unpriced",
    "reported_status":"UNRESOLVED","no_wallet_or_live_trade":True,
    "max_estimated_ru":MAX_RU,"monthly_reserve_ru":FLOOR,"cases":[]}
 budget=None;rpc=None
 try:
  if os.getenv("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES" or os.getenv("QT_ALLOW_AUTHENTICATED_RPC")!="YES":
   raise RPCFailure("EXPLICIT_APPROVAL_REQUIRED")
  key=os.getenv("BLOCKMACHINE_API_KEY","").strip()
  if not key:raise RPCFailure("MISSING_SECRET")
  status=read_key_status(key)
  if status.get("ru_remaining",0)<FLOOR+MAX_RU:raise RPCFailure("INSUFFICIENT_RU_WITH_RESERVE")
  budget=AuthenticatedBudget(status,reserve_floor=FLOOR,max_run_ru=MAX_RU,approved=True)
  rpc=ReadOnlyRPC(1,OUT/"rpc_raw",api_key=key,status=status,budget=budget,
       max_requests=24,max_attempts=1)
  report["provider_reported_ru_before"]=status["ru_remaining"]
  if int(rpc.rpc("eth_chainId",[]),16)!=1:raise ValueError("wrong chain")
  for t in TARGETS:
   result={**t,"status":"UNRESOLVED"}
   report["cases"].append(result)
   try:
    tx=rpc.rpc("eth_getTransactionByHash",[t["tx"]])
    rec=rpc.rpc("eth_getTransactionReceipt",[t["tx"]])
    head=rpc.rpc("eth_getBlockByNumber",[hex(t["block"]),False])
    if not isinstance(tx,dict) or not isinstance(rec,dict) or not isinstance(head,dict):
     raise ValueError("missing historical response")
    if tx["hash"].lower()!=t["tx"] or rec["transactionHash"].lower()!=t["tx"] or n(rec["blockNumber"])!=t["block"] or n(rec["status"])!=1:
     raise ValueError("wrong event, block or unsuccessful transaction")
    beneficiary=t["recipient"];sender=tx["from"].lower()
    reward=count_frozen_reward(rec,beneficiary)
    if reward!=t["crv_wei"]:raise ValueError("original archive reward disagreement")
    miner=head["miner"].lower();actors={beneficiary,sender}
    gas=n(rec["gasUsed"])*n(rec["effectiveGasPrice"])
    result.update({"block_hash":head["hash"],"tx_sender":sender,
     "tx_destination":str(tx.get("to","")).lower(),
     "tx_index":n(tx["transactionIndex"]),"block_fee_recipient":miner,
     "observed_CRV_to_caller_raw":str(reward),
     "incumbent_tx_gas_wei":str(gas),"token_net_deltas_raw":token_flows(rec,actors)})
    trace=rpc.rpc("debug_traceTransaction",[t["tx"],{"tracer":"callTracer","timeout":"30s"}])
    if not isinstance(trace,dict):raise ValueError("no successful trace")
    result["native_trace"]=native_transfers(trace,actors,miner)
    balance={}
    for a in actors:
     before=n(rpc.rpc("eth_getBalance",[a,hex(t["block"]-1)]))
     after=n(rpc.rpc("eth_getBalance",[a,hex(t["block"])]))
     trace_net=int(result["native_trace"]["net_native_flow_by_address"][a]["native_net_wei"])
     expected=trace_net-(gas if a==sender else 0)
     balance[a]={"block_native_delta_wei":str(after-before),
      "trace_net_after_sender_gas_wei":str(expected),
      "exact_match":after-before==expected,
      "same_block_other_tx_may_influence_delta":n(tx["transactionIndex"])!=0}
    result["native_account_check"]=balance
    result["status"]="HISTORIC_CALLER_TOKEN_PAYOUT_AND_TRACE_CONFIRMED"
   except Exception as ex:
    result["error_kind"]=ex.kind if isinstance(ex,RPCFailure) else type(ex).__name__
   (OUT/"REPORT.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
  report["reported_status"]="COMPLETE_FORENSIC_WITH_UNPRICED_RESIDUALS" if all(x["status"]=="HISTORIC_CALLER_TOKEN_PAYOUT_AND_TRACE_CONFIRMED" for x in report["cases"])else "PARTIAL_MISSING_EVIDENCE"
 except Exception as ex:
  report["error_kind"]=ex.kind if isinstance(ex,RPCFailure) else type(ex).__name__
 report["estimated_RU_attempts"]=budget.attempted_ru if budget else 0
 report["RPC_requests"]=rpc.attempted if rpc else 0
 (OUT/"REPORT.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"status":report["reported_status"],"estimated_ru":report["estimated_RU_attempts"],
   "cases":[{"tx":x["tx"],"status":x["status"],"error_kind":x.get("error_kind")}for x in report["cases"]]},sort_keys=True))
 return 0 if report["reported_status"]=="COMPLETE_FORENSIC_WITH_UNPRICED_RESIDUALS" else 2
if __name__=="__main__":raise SystemExit(run())