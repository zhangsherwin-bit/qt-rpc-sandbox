"""QT Stage 1: two independent HIGH-LEVEL forms of economic ownership.

A. Sablier Lockup v3: an NFT can control time-contingent token receivables,
   conditional on transferability and sender cancellation rights.
B. ERC-6551: owning one NFT can control a deterministically bound account
   holding multiple assets, conditional on implementation/signer rules.
This is presence and rights-source evidence ONLY, never a buyer profit claim.

Keyless documented public Blockmachine Ethereum RPC ONLY; zero authenticated
request units, no wallet, trades, signing, bids or purchases.
"""
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC,RPCFailure
import json,os
SABLIER="0x93b37bd5b6b278373217333ac30d7e74c85fbdcb"
TBA_REGISTRY="0x000000006551c19487814612e58fe06813775758"
ZERO="0x"+"0"*40
WINDOW=950
OFFSETS=[200,32000,275000]
MAX_EVIDENCE_TX_PER_FAMILY=4
OUT=Path("stage1_timed_nested_rights")
def k(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
TRANSFER=k("Transfer(address,address,uint256)")
S_CANCEL=k("CancelLockupStream(uint256,address,address,address,uint128,uint128)")
S_WITHDRAW=k("WithdrawFromLockupStream(uint256,address,address,uint128)")
S_RENOUNCE=k("RenounceLockupStream(uint256)")
TBA_CREATED=k("ERC6551AccountCreated(address,address,bytes32,uint256,address,uint256)")
def n(v):
 if isinstance(v,str) and v.startswith("0x"):return int(v,16)
 raise ValueError("invalid hex")
def address_topic(t):
 if not isinstance(t,str) or len(t)!=66:raise ValueError("invalid address topic")
 return "0x"+t[-40:].lower()
def parse_sablier(log):
 t=log["topics"];typ=t[0].lower()
 o={"tx":log["transactionHash"],"block":n(log["blockNumber"]),"index":n(log["logIndex"])}
 if typ==TRANSFER:
  if len(t)!=4 or log.get("data")!="0x":raise ValueError("not ERC721 transfer")
  frm=address_topic(t[1]);to=address_topic(t[2])
  kind="mint" if frm==ZERO else "burn" if to==ZERO else "secondary_owner_transfer"
  return {**o,"kind":kind,"stream_id":n(t[3]),"from":frm,"to":to}
 if typ==S_CANCEL:
  if len(t)!=4 or len(log.get("data",""))!=194:raise ValueError("cancel ABI")
  dat=log["data"][2:];return {**o,"kind":"stream_cancel",
    "stream_id":int(dat[:64],16),
    "sender":address_topic(t[1]),"recipient":address_topic(t[2]),
    "asset":address_topic(t[3]),"sender_refund_raw":str(int(dat[64:128],16)),
    "recipient_receivable_raw":str(int(dat[128:192],16))}
 if typ==S_WITHDRAW:
  if len(t)!=4 or len(log.get("data",""))!=66:raise ValueError("withdraw ABI")
  return {**o,"kind":"withdraw","stream_id":n(t[1]),
    "to":address_topic(t[2]),"asset":address_topic(t[3]),
    "amount_raw":str(n(log["data"]))}
 if typ==S_RENOUNCE:
  if len(t)!=2 or log.get("data")!="0x":raise ValueError("renounce ABI")
  return {**o,"kind":"renounced_cancel_right","stream_id":n(t[1])}
 raise ValueError("unknown Sablier event")
def parse_tba(log):
 t=log["topics"];d=log.get("data","")
 if len(t)!=4 or t[0].lower()!=TBA_CREATED or len(d)!=194:raise ValueError("TBA ABI")
 return {"tx":log["transactionHash"],"block":n(log["blockNumber"]),
  "index":n(log["logIndex"]),"account":"0x"+d[2:66][-40:].lower(),
  "implementation":address_topic(t[1]),
  "salt":"0x"+d[66:130],
  "chain_id":int(d[130:194],16),
  "token_contract":address_topic(t[2]),"token_id":n(t[3])}
def run():
 OUT.mkdir(exist_ok=True,parents=True)
 rpt={"timestamp":datetime.now(timezone.utc).isoformat(),
  "sources":{
    "Sablier":"sablier-labs/evm-monorepo lockup/src/SablierLockup.sol and ISablierLockup.sol, July 2026 maintenance mode",
    "ERC6551":"erc6551/reference src/ERC6551Registry.sol, EIP-6551 official singleton registry"},
  "contracts":{"Sablier":SABLIER,"ERC6551Registry":TBA_REGISTRY},
  "frozen_width_blocks":WINDOW,"frozen_head_offsets":OFFSETS,
  "keyless_only":True,"authenticated_RU":0,
  "status":"UNRESOLVED","windows":[],"family_summaries":{},"receipts":[],
  "no_wallet_no_orders_no_external_outreach":True,
  "can_redeem_someone_elses_stream":False,
  "NFT_ownership_guarantees_resale_profit":False,
  "limitations":["ERC721 transfer may be internal migration, gift, escrow or consensual OTC; NOT necessarily a priced sale",
   "ERC6551 account creation does not prove token owner has valid access to ALL account assets",
   "Sablier sender may retain cancellation right, and not all streams transferable",
   "token-bound account asset balances can be emptied immediately before NFT purchase",
   "ERC6551 implementation dependent ownership cycles may make assets inaccessible",
   "a marketplace order must commit to asset state and use a safe delivery route",
   "activity windows sparse/noncontinuous and are NOT recurrence or earnings forecasts"]}
 rpc=None
 try:
  rpc=ReadOnlyRPC(1,OUT/"raw",api_key="",max_attempts=1,max_requests=45)
  if n(rpc.rpc("eth_chainId",[]))!=1:raise ValueError("Wrong chain")
  head=n(rpc.rpc("eth_blockNumber",[]))-10
  anchor=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  rpt["anchor"]={"number":head,"hash":anchor["hash"]}
  for x in [SABLIER,TBA_REGISTRY]:
   if rpc.rpc("eth_getCode",[x,hex(head)]) in (None,"0x"):raise ValueError("Source contract not deployed")
  all_sablier=[];all_tba=[]
  for fam,contract,topics in [
    ("Sablier",SABLIER,[TRANSFER,S_CANCEL,S_WITHDRAW,S_RENOUNCE]),
    ("ERC6551",TBA_REGISTRY,[TBA_CREATED])
  ]:
   for offset in OFFSETS:
    end=head-offset;start=end-WINDOW+1
    win={"family":fam,"offset":offset,"start":start,"end":end,"state":"UNRESOLVED"}
    rpt["windows"].append(win)
    try:
     logs=rpc.rpc("eth_getLogs",[{"address":contract,"fromBlock":hex(start),"toBlock":hex(end),"topics":[topics]}])
     if not isinstance(logs,list):raise ValueError("Missing log list")
     rows=[parse_sablier(l) if fam=="Sablier" else parse_tba(l) for l in logs]
     if fam=="Sablier":all_sablier.extend(rows)
     else:all_tba.extend(rows)
     win["state"]="OK";win["events"]=len(rows);win["kinds"]=(dict(Counter(x["kind"] for x in rows)) if fam=="Sablier" else {"created":len(rows)})
    except Exception as e:
     win["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
     if rpc.aborted:break
    (OUT/"REPORT.json").write_text(json.dumps(rpt,indent=2,sort_keys=True)+"\n")
  rpt["family_summaries"]={
    "Sablier":{"observed":len(all_sablier),"kinds":dict(Counter(x["kind"] for x in all_sablier)),
      "distinct_stream_tokens":len(set(x.get("stream_id") for x in all_sablier if x.get("stream_id") is not None)),
      "unique_secondary_stream_ids":len(set(x["stream_id"] for x in all_sablier if x["kind"]=="secondary_owner_transfer")),
      "selected_transfers":[x for x in all_sablier if x["kind"]=="secondary_owner_transfer"][:6]},
    "ERC6551":{"registrations":len(all_tba),
      "different_implementations":len(set(x["implementation"] for x in all_tba)),
      "different_nft_collections":len(set(x["token_contract"] for x in all_tba)),
      "selected_created_accounts":all_tba[:6]}}
  selected=[]
  for x in [q for q in all_sablier if q["kind"]=="secondary_owner_transfer"][:MAX_EVIDENCE_TX_PER_FAMILY]:
   selected.append(("Sablier",x))
  for x in all_tba[:MAX_EVIDENCE_TX_PER_FAMILY]:
   selected.append(("ERC6551",x))
  for family,x in selected:
   rec={"family":family,"tx":x["tx"],"state":"UNRESOLVED"}
   rpt["receipts"].append(rec)
   try:
    receipt=rpc.rpc("eth_getTransactionReceipt",[x["tx"]])
    tx=rpc.rpc("eth_getTransactionByHash",[x["tx"]])
    if n(receipt["status"])!=1 or n(receipt["blockNumber"])!=x["block"]:raise ValueError("Wrong receipt")
    rec["tx_sender"]=tx["from"].lower()
    rec["tx_to"]=str(tx.get("to") or "").lower()
    rec["tx_gas_wei"]=str(n(receipt["gasUsed"])*n(receipt["effectiveGasPrice"]))
    rec["origin_event_verified"]=any(l.get("address","").lower()==
       (SABLIER if family=="Sablier" else TBA_REGISTRY) and
       n(l["logIndex"])==x["index"] for l in receipt.get("logs",[]))
    if not rec["origin_event_verified"]:raise ValueError("Missing event in receipt")
    if family=="ERC6551":
      rec["created_account"]=x["account"]
      rec["native_eth_balance_at_creation_block_raw"]=str(n(rpc.rpc("eth_getBalance",[x["account"],hex(x["block"])])))
      rec["nonstandard_account_code_present"]=rpc.rpc("eth_getCode",[x["account"],hex(x["block"])])!="0x"
    rec["state"]="OBSERVED_CONTRACT_EVENT_NOT_MARKET_PROFIT"
   except Exception as e:rec["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
   (OUT/"REPORT.json").write_text(json.dumps(rpt,indent=2,sort_keys=True)+"\n")
  verify=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  rpt["anchor_verified"]=verify["hash"]==anchor["hash"]
  rpt["status"]="COMPLETE_ACTIVITY_SCREEN" if rpt["anchor_verified"] and len(rpt["windows"])==2*len(OFFSETS) and all(w["state"]=="OK" for w in rpt["windows"]) and all(x["state"]=="OBSERVED_CONTRACT_EVENT_NOT_MARKET_PROFIT" for x in rpt["receipts"]) else "INCOMPLETE_MISSING_EVIDENCE"
 except Exception as e:rpt["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
 rpt["rpc_requests_sent"]=rpc.attempted if rpc else 0
 (OUT/"REPORT.json").write_text(json.dumps(rpt,sort_keys=True,indent=2)+"\n")
 print(json.dumps({"status":rpt["status"],"families":rpt["family_summaries"],
  "rpc_requests_sent":rpt["rpc_requests_sent"],"authenticated_RU":0,
  "error_kind":rpt.get("error_kind")},sort_keys=True)[:2900])
 return 0 if rpt["status"]=="COMPLETE_ACTIVITY_SCREEN" else 2
if __name__=="__main__":raise SystemExit(run())
