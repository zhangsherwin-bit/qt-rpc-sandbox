"""QT Programme III Stage1: permissionlessly transferable Lido unstETH rights.

Read-only historical existence/eligibility *screen*, NOT a claim-market bid.
Four preselected 250-block samples. 90-RU cap and 1500 reserve.
No wallet, orders, signatures, claims, transfers or trades.
"""
import os,json
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC,AuthenticatedBudget,read_key_status,RPCFailure
QUEUE="0x889edc2edab5f40e902b864ad4d7ade8e412f9b1"
ZERO="0x"+"0"*40
OFFSETS=[200,15000,90000,450000]
WIDTH=250
MAX_RECEIPTS=8
MAX_RU=90;FLOOR=1500
OUT=Path("stage1_lido_claim_evidence")
def sig(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
TRANSFER=sig("Transfer(address,address,uint256)")
REQUEST=sig("WithdrawalRequested(uint256,address,address,uint256,uint256)")
CLAIM=sig("WithdrawalClaimed(uint256,address,address,uint256)")
STATUS_SELECTOR=sig("getWithdrawalStatus(uint256[])")[:10]
def hx(x):return int(x,16)
def w(x):return format(int(x),"064x")
def ad(x):
 if not isinstance(x,str) or len(x)!=66:raise ValueError("Invalid topic")
 return "0x"+x[-40:].lower()
def parse(log):
 t=log["topics"]; data=log["data"];event=t[0].lower()
 common={"tx":log["transactionHash"],"block":hx(log["blockNumber"]),"index":hx(log["logIndex"])}
 if event==TRANSFER:
  if len(t)!=4 or data not in ("0x","0x0"):raise ValueError("Invalid ERC721 Transfer")
  a,b=ad(t[1]),ad(t[2])
  if a==ZERO and b==ZERO:raise ValueError("Both zero")
  typ=("mint" if a==ZERO else "burn" if b==ZERO else "secondary_owner_transfer")
  return {**common,"kind":typ,"id":hx(t[3]),"from":a,"to":b}
 if event==REQUEST:
  if len(t)!=4 or len(data)!=130:raise ValueError("WithdrawalRequested ABI mismatch")
  return {**common,"kind":"request","id":hx(t[1]),"requestor":ad(t[2]),
          "owner":ad(t[3]),"amount_steth_raw":int(data[2:66],16),
          "amount_shares_raw":int(data[66:130],16)}
 if event==CLAIM:
  if len(t)!=4 or len(data)!=66:raise ValueError("WithdrawalClaimed ABI mismatch")
  return {**common,"kind":"claim","id":hx(t[1]),"owner":ad(t[2]),
          "receiver":ad(t[3]),"eth_claimed_raw":hx(data)}
 raise ValueError("Unknown event")
def classify_payment(receipt,seller,buyer):
 """No external market event implies sale; direct ERC20 payment is only a hint."""
 direct=[]
 for l in receipt.get("logs",[]):
  t=l.get("topics",[])
  if len(t)==3 and t[0].lower()==TRANSFER:
   try:a,b=ad(t[1]),ad(t[2])
   except ValueError:continue
   if a==buyer and b==seller and len(l.get("data",""))==66:
    direct.append({"token":l["address"].lower(),"amount_raw":str(hx(l["data"]))})
 return direct
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 report={"research":"Lido unstETH transferable delayed claim screening",
  "timestamp":datetime.now(timezone.utc).isoformat(),"contract":QUEUE,
  "source":"lidofinance/core v4.0.0 contracts/0.8.9/WithdrawalQueueBase.sol and WithdrawalQueueERC721.sol",
  "frozen_offsets":OFFSETS,"width":WIDTH,
  "status":"UNRESOLVED","permission":"Lido NFT is an ERC721; owner controls claim, no rights without NFT ownership",
  "evidence_limitations":["nonmint transfer not proof of sale or price",
    "recipient's claim rights require current ownership and finalisation",
    "stETH AMM immediate sale is the correct liquid alternative",
    "no onchain listing, bid/ask or funding edge established"],
  "windows":[],"sample_receipts":[],"economic_profit_proved":False,
  "trade_sent":False,"reliable_market_price_sampled":False}
 budget=None;rpc=None
 try:
  if os.getenv("QT_ALLOW_AUTHENTICATED_RPC")!="YES" or os.getenv("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES":raise RPCFailure("RUNTIME_APPROVAL_MISSING")
  key=os.getenv("BLOCKMACHINE_API_KEY","").strip()
  if not key:raise RPCFailure("KEY_MISSING")
  status=read_key_status(key)
  if status.get("ru_remaining",0)<FLOOR+MAX_RU:raise RPCFailure("MONTHLY_RU_FLOOR")
  budget=AuthenticatedBudget(status,reserve_floor=FLOOR,max_run_ru=MAX_RU,approved=True)
  rpc=ReadOnlyRPC(1,OUT/"rpc_raw",api_key=key,status=status,budget=budget,
      max_requests=30,max_attempts=1)
  report["ru_start_snapshot"]=status["ru_remaining"]
  if hx(rpc.rpc("eth_chainId",[]))!=1:raise ValueError("wrong chain")
  head=hx(rpc.rpc("eth_blockNumber",[]))-10
  anchor=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  if not isinstance(anchor,dict) or hx(anchor["number"])!=head:raise ValueError("no canonical head")
  report["pin"]={"number":head,"hash":anchor["hash"]}
  if rpc.rpc("eth_getCode",[QUEUE,hex(head)])=="0x":raise ValueError("Lido queue missing")
  logs_all=[]
  for offset in OFFSETS:
   end=head-offset;start=end-WIDTH+1
   win={"start":start,"end":end,"offset":offset,"state":"UNRESOLVED"}
   report["windows"].append(win)
   if start<0:raise ValueError("negative block")
   try:
    logs=rpc.rpc("eth_getLogs",[{"address":QUEUE,"fromBlock":hex(start),
                  "toBlock":hex(end),"topics":[[TRANSFER,REQUEST,CLAIM]]}])
    if not isinstance(logs,list):raise ValueError("no logs array")
    parsed=[]
    for l in logs:
     if l.get("address","").lower()!=QUEUE:raise ValueError("wrong emitter")
     parsed.append(parse(l))
    logs_all.extend(parsed)
    win["state"]="OK";win["counts"]=dict(Counter(x["kind"] for x in parsed))
    win["total_logs"]=len(parsed)
   except Exception as e:
    win["error_type"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
    if rpc.aborted:break
   (OUT/"REPORT.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
  kinds=Counter(x["kind"] for x in logs_all)
  report["all_sample_counts"]=dict(kinds)
  transfers=[x for x in sorted(logs_all,key=lambda r:(r["block"],r["index"]))
             if x["kind"]=="secondary_owner_transfer"]
  report["secondary_transfer_events"]=len(transfers)
  report["distinct_transferable_claim_ids"]=len({x["id"] for x in transfers})
  report["first_nonmint_transfers"]=transfers[:12]
  chosen=[];seen=set()
  for x in transfers:
   if x["tx"] in seen:continue
   seen.add(x["tx"]);chosen.append(x)
   if len(chosen)>=MAX_RECEIPTS:break
  for x in chosen:
   row={"tx":x["tx"],"block":x["block"],"claim_id":x["id"],"status":"UNRESOLVED"}
   report["sample_receipts"].append(row)
   try:
    rc=rpc.rpc("eth_getTransactionReceipt",[x["tx"]])
    tx=rpc.rpc("eth_getTransactionByHash",[x["tx"]])
    if not rc or not tx or hx(rc["status"])!=1:raise ValueError("invalid receipt")
    if hx(rc["blockNumber"])!=x["block"]:raise ValueError("receipt block changed")
    if not any(l.get("address","").lower()==QUEUE and len(l.get("topics",[]))==4 and
               l["topics"][0].lower()==TRANSFER and hx(l["topics"][3])==x["id"]
               for l in rc.get("logs",[])):raise ValueError("transfer not in receipt")
    row["tx_sender"]=tx["from"].lower()
    row["tx_destination"]=str(tx.get("to") or "").lower()
    row["buyer_to_seller_erc20_direct_payment_hints"]=classify_payment(rc,x["from"],x["to"])
    row["observed_gas_wei"]=str(hx(rc["gasUsed"])*hx(rc["effectiveGasPrice"]))
    row["status"]="TRANSFER_RECEIPT_CONFIRMED_PRICE_UNVERIFIED"
   except Exception as e:row["error_type"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
   (OUT/"REPORT.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
  confirm=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  report["canonical_pin_rechecked"]=confirm["hash"]==anchor["hash"]
  report["status"]=("COMPLETE_ACTIVITY_SCREEN" if report["canonical_pin_rechecked"]
    and len(report["windows"])==len(OFFSETS)
    and all(x["state"]=="OK" for x in report["windows"])
    and all(x["status"]=="TRANSFER_RECEIPT_CONFIRMED_PRICE_UNVERIFIED" for x in report["sample_receipts"])
    else "INCOMPLETE_ACTIVITY_SCREEN")
 except Exception as e:
  report["error_type"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
 report["ru_attempted_conservative"]=budget.attempted_ru if budget else 0
 report["rpc_attempts"]=rpc.attempted if rpc else 0
 (OUT/"REPORT.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:report.get(k) for k in (
   "status","all_sample_counts","secondary_transfer_events",
   "distinct_transferable_claim_ids","ru_attempted_conservative","error_type")},sort_keys=True))
 return 0 if report["status"]=="COMPLETE_ACTIVITY_SCREEN" else 2
if __name__=="__main__":raise SystemExit(main())
