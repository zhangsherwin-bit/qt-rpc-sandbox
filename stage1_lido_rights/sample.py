"""QT Programme III Stage1: test market activity of transferable Lido unstETH rights.

Owner of the exact ERC721 is allowed to claim finalized ETH. Buying the NFT
at an attractive price is a DIFFERENT right from requesting one's own stETH
withdrawal. Only externally accessible signed offers support purchasability.
This test merely counts transfer activity and verifies ownership semantics.
Read-only Ethereum RPC: no wallets, trading, bidding, signing or purchases.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from Crypto.Hash import keccak
import json, os, sys
from qt_rpc.client import ReadOnlyRPC, AuthenticatedBudget, read_key_status, RPCFailure

QUEUE="0x889edc2edab5f40e902b864ad4d7ade8e412f9b1"
ZERO="0x"+"0"*40
WINDOW_BLOCKS=160
END_OFFSETS=(200,19000,96000,300000,550000,900000)
MAX_NONMINT_RECEIPTS=6
MAX_RU=135
PROTECTED_RU=1500
OUT=Path("lido_unsteth_evidence")
def sel(text):
 h=keccak.new(digest_bits=256);h.update(text.encode());return "0x"+h.hexdigest()
TRANSFER=sel("Transfer(address,address,uint256)")
GET_STATUS=sel("getWithdrawalStatus(uint256[])")[:10]
LAST_REQUEST=sel("getLastRequestId()")[:10]
LAST_FINALIZED=sel("getLastFinalizedRequestId()")[:10]
def uint(x):
 if isinstance(x,str) and x.startswith("0x"):return int(x,16)
 raise ValueError("invalid uint")
def wd(n):
 return format(n,"064x")
def addr(t):
 if not isinstance(t,str) or len(t)!=66:raise ValueError("invalid indexed address")
 return "0x"+t[-40:].lower()
def decode_transfer(log):
 ts=log.get("topics",[])
 if not (len(ts)==4 and ts[0].lower()==TRANSFER and log["address"].lower()==QUEUE):
  raise ValueError("not this ERC721 transfer event")
 a,b=addr(ts[1]),addr(ts[2])
 return {"block":uint(log["blockNumber"]),"tx":log["transactionHash"].lower(),
   "log_index":uint(log["logIndex"]),"token_id":uint(ts[3]),
   "from":a,"to":b,"kind":("MINT" if a==ZERO else "BURN" if b==ZERO
                          else "SELF" if a==b else "TRANSFER_NONZERO")}
def status_arg(token_id):
 # ABI: one dynamic array offset=0x20, length=1, token ID.
 return GET_STATUS+wd(32)+wd(1)+wd(token_id)
def decode_one_status(raw):
 if not isinstance(raw,str) or not raw.startswith("0x"):
  raise ValueError("bad ABI status")
 data=raw[2:]
 if len(data)<64*8 or len(data)%64:raise ValueError("too few returned words")
 words=[int(data[x:x+64],16) for x in range(0,len(data),64)]
 p=words[0]//32
 if words[p]!=1 or len(words)<p+1+6:raise ValueError("wrong status array count")
 vals=words[p+1:p+7]
 if any(x not in (0,1) for x in vals[4:]):raise ValueError("malformed booleans")
 return {"amount_steth_wei":str(vals[0]),"steth_shares":str(vals[1]),
         "owner":"0x"+format(vals[2],"040x"),"request_timestamp":vals[3],
         "finalized":bool(vals[4]),"claimed":bool(vals[5])}
def receipt_simple(transfer,tx,rc,st):
 if tx.get("hash","").lower()!=transfer["tx"] or rc.get("transactionHash","").lower()!=transfer["tx"]:
  raise ValueError("receipt not matched to selected event")
 if uint(rc.get("status","0x0"))!=1:raise ValueError("transfer receipt failed")
 matched_status=st["owner"].lower()==transfer["to"]
 return {"eth_value_on_outer_tx_wei":str(uint(tx.get("value","0x0"))),
         "gas_paid_wei":str(uint(rc["gasUsed"])*uint(rc["effectiveGasPrice"])),
         "tx_destination":str(tx.get("to","")).lower(),
         "tx_sender":tx["from"].lower(),
         "receipt_log_count":len(rc["logs"]),
         "status_owner_matches_nonzero_transferee_at_block_end":matched_status,
         "status":st,
         "interpretation":"ownership-transfer-only, NOT proof of priced secondary-market sale"}
def save(report):
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
def main():
 report={"utc":datetime.now(timezone.utc).isoformat(),"chain":"ethereum",
   "source":"Lido WithdrawalQueueERC721 user docs & verified mainnet proxy",
   "queue":QUEUE,"hypothesis":"Transferable pending ETH withdrawal claim can be legitimately acquired at a discount from a willing seller",
   "fixed_sample":{"end_offsets":END_OFFSETS,"window_blocks":WINDOW_BLOCKS,
      "first_nonmint_receipts":MAX_NONMINT_RECEIPTS,"max_ru":MAX_RU,
      "reserve_floor":PROTECTED_RU,
      "sample_not_independent_holdout":False},
   "separation":{"contract_transferability":"CONFIRMED_BY_OFFICIAL_PROTOCOL",
    "past_ownership_transfers":"UNVERIFIED","past_sales_at_price":"UNVERIFIED",
    "current_signed_discounted_offer":"UNVERIFIED","liquid_risk_adjusted_profit":"UNVERIFIED",
    "rights_owned_by_QT":False},
   "outcome":"UNRESOLVED","sampled_windows":[],
   "sampled_nonmint_receipts":[],"errors":[],"no_spend_or_trade":True}
 rpc=None;budget=None
 try:
  if os.getenv("QT_ALLOW_AUTHENTICATED_RPC")!="YES" or os.getenv("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES":
   raise RPCFailure("AUTHENTICATED_USE_NOT_APPROVED")
  key=os.getenv("BLOCKMACHINE_API_KEY","").strip()
  if not key:raise RPCFailure("MISSING_BEARER_SECRET")
  status=read_key_status(key)
  if status.get("ru_remaining",0)<PROTECTED_RU+MAX_RU:raise RPCFailure("RU_RESERVE_INSUFFICIENT")
  budget=AuthenticatedBudget(status,reserve_floor=PROTECTED_RU,max_run_ru=MAX_RU,approved=True)
  rpc=ReadOnlyRPC(1,OUT/"rpc_raw",api_key=key,status=status,budget=budget,
                 max_attempts=1,max_requests=38)
  report["provider_ru_before"]=status["ru_remaining"]
  report["provider_limit_ru_per_min"]=status["rate_limit_rpm"]
  if uint(rpc.rpc("eth_chainId",[]))!=1:raise ValueError("wrong chain")
  head=uint(rpc.rpc("eth_blockNumber",[]))-12
  anchor=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  if uint(anchor["number"])!=head:raise ValueError("wrong anchor")
  report["anchor"]={"number":head,"hash":anchor["hash"],"timestamp":uint(anchor["timestamp"])}
  if rpc.rpc("eth_getCode",[QUEUE,hex(head)])=="0x":raise ValueError("withdrawal NFT proxy code not deployed")
  report["last_request_at_anchor"]=uint(rpc.rpc("eth_call",[{"to":QUEUE,"data":LAST_REQUEST},hex(head)]))
  report["last_finalized_at_anchor"]=uint(rpc.rpc("eth_call",[{"to":QUEUE,"data":LAST_FINALIZED},hex(head)]))
  all_events=[]
  for d in END_OFFSETS:
   end=head-d;start=end-WINDOW_BLOCKS+1
   w={"start":start,"end":end,"offset":d,"state":"UNRESOLVED"}
   report["sampled_windows"].append(w)
   try:
    logs=rpc.rpc("eth_getLogs",[{"address":QUEUE,"topics":[TRANSFER],
            "fromBlock":hex(start),"toBlock":hex(end)}])
    events=[decode_transfer(x) for x in logs]
    w["state"]="OK";w["total_transfers"]=len(events)
    w["types"]=dict(Counter(x["kind"] for x in events))
    w["nonzero_transfer_examples"]= [x for x in events if x["kind"]=="TRANSFER_NONZERO"][:6]
    all_events.extend(events)
   except Exception as exc:
    w["error_kind"]=exc.kind if isinstance(exc,RPCFailure) else type(exc).__name__
   save(report)
  report["complete_windows"]=sum(w["state"]=="OK" for w in report["sampled_windows"])
  report["count_by_type"]=dict(Counter(x["kind"] for x in all_events))
  report["unique_nonzero_transfer_tokens"]=len({x["token_id"] for x in all_events if x["kind"]=="TRANSFER_NONZERO"})
  selected=[];seen=set()
  for event in sorted(all_events,key=lambda x:(x["block"],x["log_index"])):
   if event["kind"]!="TRANSFER_NONZERO" or event["tx"] in seen:continue
   seen.add(event["tx"]);selected.append(event)
   if len(selected)>=MAX_NONMINT_RECEIPTS:break
  for transfer in selected:
   item={**transfer,"state":"UNRESOLVED"}
   report["sampled_nonmint_receipts"].append(item)
   try:
    tx=rpc.rpc("eth_getTransactionByHash",[transfer["tx"]])
    rc=rpc.rpc("eth_getTransactionReceipt",[transfer["tx"]])
    raw=rpc.rpc("eth_call",[{"to":QUEUE,"data":status_arg(transfer["token_id"])},
                           hex(transfer["block"])])
    st=decode_one_status(raw)
    item.update(receipt_simple(transfer,tx,rc,st));item["state"]="READ_ONLY_CONFIRMED"
   except Exception as exc:
    item["error_kind"]=exc.kind if isinstance(exc,RPCFailure) else type(exc).__name__
   save(report)
  confirm=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  report["same_anchor_hash"]=confirm["hash"]==anchor["hash"]
  complete=report["complete_windows"]==len(END_OFFSETS) and report["same_anchor_hash"] and all(
   x["state"]=="READ_ONLY_CONFIRMED" for x in report["sampled_nonmint_receipts"])
  report["separation"]["past_ownership_transfers"]=("OBSERVED" if report["unique_nonzero_transfer_tokens"]>0 else
          "ZERO_IN_BOUNDED_SAMPLE" if complete else "UNRESOLVED")
  report["outcome"]="BOUNDED_TRANSFER_TEST_COMPLETE" if complete else "PARTIAL_DATA_UNRESOLVED"
 except Exception as exc:
  report["errors"].append({"kind":exc.kind if isinstance(exc,RPCFailure) else type(exc).__name__})
 report["conservative_ru_used"]=budget.attempted_ru if budget else 0
 report["rpc_requests_sent"]=rpc.attempted if rpc else 0
 save(report)
 print(json.dumps({"outcome":report["outcome"],"windows":report.get("complete_windows",0),
  "types":report.get("count_by_type",{}),"unique_nonzero_token_ids":report.get("unique_nonzero_transfer_tokens",None),
  "sample_receipts":len(report["sampled_nonmint_receipts"]),"ru":report["conservative_ru_used"],
  "errors":report["errors"]},sort_keys=True))
 return 0 if report["outcome"]=="BOUNDED_TRANSFER_TEST_COMPLETE" else 2
if __name__=="__main__":sys.exit(main())