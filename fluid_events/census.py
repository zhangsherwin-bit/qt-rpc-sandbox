"""Read-only canonical Fluid Vault Liquidate EVENT census in a frozen 57k block window.
Complements zero-eligible snapshots: observed winners may eliminate the opportunities.
No strategy profitability attribution from nominal incentive; preserve actual receipts.
"""
import sys,json,time,traceback,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fluid_stage1 import screen as S
OUT=Path("fluid_event_evidence");OUT.mkdir(parents=True,exist_ok=True)
END=26220131;WINDOW=57000;START=END-WINDOW+1
BLOCK_STEP=9500
EVENT=S.sig("LogLiquidate(address,uint256,uint256,address)")
LAST_LOG=-10**10
def save(d):
 (OUT/"REPORT.json").write_text(json.dumps(d,indent=2)+"\n")
def event_decode(log,addresses):
 if len(log["topics"])!=1 or log["topics"][0].lower()!=EVENT.lower():raise ValueError("Invalid signature/indexed event layout")
 if log["address"].lower() not in addresses:raise ValueError("Unverified Fluid vault event")
 w=S.decode_words(log["data"])
 if len(w)!=4:raise ValueError("Unexpected liquidation ABI")
 return {"tx":log["transactionHash"],"block":int(log["blockNumber"],16),"index":int(log["logIndex"],16),
  "vault":log["address"].lower(),"liquidator":S.address(w[0]),"collateral_raw":str(w[1]),
  "debt_raw":str(w[2]),"recipient":S.address(w[3]),
  "gross_profit_USDC":"UNKNOWN","not_proven_capture":True}
def main():
 global LAST_LOG
 report={"scope":"Official Fluid Ethereum VaultResolver registry matched to canonical emitted LogLiquidate",
  "window":{"from_block":START,"through_block":END},
  "snapshot_negative_controls":"28 inspected Fluid Ethereum vaults were NOT liquidatable at Sep30 and Oct17 snapshots",
  "market_coverage":"All 182 Ethereum vaults listed at pinned Oct17 block, not sampled",
  "original_financial_profit":False,
  "warnings":["An event records actual collateral/debt movements but not liquidator's full value, all costs or permissions",
              "Different denomination of collateral/debt means reward cannot be computed as unit ratio",
              "Replayed historical winner is not available to a new bot at the winning timestamp",
              "No live addresses/funds/contracts modified","Provider errors mean incomplete sample, not zero events"],
  "pages":[],"events":[],"sampled_receipts":[],"complete":False}
 save(report)
 try:
  if int(S.request(1,"eth_chainId",[],"chain"),16)!=1:raise ValueError("Wrong network")
  h=S.request(1,"eth_getBlockByNumber",[hex(END),False],"pinned_end")
  bf=int(h["baseFeePerGas"],16)
  vaults=S.get_vaults(1,END,bf)
  if not vaults:raise ValueError("No authentic Fluid vaults")
  addrs={a.lower() for a in vaults}
  report["actual_registry_size"]=len(addrs)
  for i in range(START,END+1,BLOCK_STEP):
   to=min(i+BLOCK_STEP-1,END)
   time.sleep(max(0,67-(time.monotonic()-LAST_LOG)))
   LAST_LOG=time.monotonic()
   logs=S.request(1,"eth_getLogs",[{"address":list(sorted(addrs)),"fromBlock":hex(i),"toBlock":hex(to),"topics":[EVENT]}],"liquidation_events")
   values=[event_decode(x,addrs) for x in logs]
   report["pages"].append({"from":i,"through":to,"events":len(values)})
   report["events"].extend(values)
   save(report)
  # Three freeze-determined observed winning receipts: first, middle and last.
  distinct=list({v["tx"]:v for v in report["events"]}.values())
  distinct.sort(key=lambda x:(x["block"],x["tx"]))
  report["unique_transaction_count"]=len(distinct)
  report["event_count"]=len(report["events"])
  chosen=[distinct[i] for i in sorted({0,len(distinct)//2,len(distinct)-1})] if distinct else []
  for e in chosen:
   record={"tx":e["tx"],"block":e["block"],"status":"UNAVAILABLE"}
   report["sampled_receipts"].append(record);save(report)
   try:
    receipt=S.request(1,"eth_getTransactionReceipt",[e["tx"]],"canonical_winner_receipt")
    if not receipt or receipt["status"]!="0x1" or int(receipt["blockNumber"],16)!=e["block"]:
     raise ValueError("Unverified original winner")
    records=[x for x in receipt["logs"] if x["address"].lower() in addrs and x["topics"][0].lower()==EVENT.lower()]
    record.update(status="ORIGINAL_RECEIPT_VERIFIED",events_in_tx=len(records),
       gas_used=int(receipt["gasUsed"],16),
       effective_gas_price_wei=int(receipt["effectiveGasPrice"],16),
       source_sender=receipt["from"].lower(),
       source_transaction_cost_wei=str(int(receipt["gasUsed"],16)*int(receipt["effectiveGasPrice"],16)))
   except Exception as ex:record["error"]=repr(ex)
   save(report)
  if S.request(1,"eth_getBlockByNumber",[hex(END),False],"header_recheck")["hash"]!=h["hash"]:
   raise ValueError("Pinned end reorg")
  if len(report["pages"])!=6 or report["pages"][0]["from"]!=START or report["pages"][-1]["through"]!=END:
   raise ValueError("Incomplete window")
  report["complete"]=True
 except Exception as ex:report["error"]=repr(ex);report["traceback"]=traceback.format_exc()
 report["rpc_requests"]=S.COUNT;report["denied_chains"]=sorted(S.DENIED)
 save(report)
 print(json.dumps({"complete":report["complete"],"requests":report["rpc_requests"],
    "vaults":report.get("actual_registry_size"),"events":len(report["events"]),
    "unique_transactions":report.get("unique_transaction_count"),"pages":len(report["pages"]),
    "error":report.get("error")},indent=2),flush=True)
 if not report["complete"]:raise SystemExit("Partial historical liquidations, not a completed census")
if __name__=="__main__":main()
