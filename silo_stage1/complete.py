"""Resume Silo Stage1 from official schema. Distinguishes indexer-estimated
liquidation rewards from real EVM cash profits; no signing or trades.
"""
import sys,json,traceback,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import screen as S
TYPES=[("defaultingLiquidations","defaultingLiquidation"),("liquidationRewards","liquidationReward"),("vaultDefaultingLiquidations","vaultDefaultingLiquidation")]
PREFERRED=("id","chainId","txHash","blockNumber","timestamp","logIndex","profitUSD","roi","liquidationYield","baseCollateralReceivedUsd","rewardCollateralReceivedUsd","totalCollateralReceivedUsd","keeperAssetsUsd","supplyAssetsSentUsd","marketId","collateralMarketId","rewardUsd","rewardAmountUsd","amountUsd")
def unwrap(t):
 while t and t.get("kind") in ("NON_NULL","LIST"):t=t.get("ofType")
 return t or {}
def fields(name):
 out=S.gql("silo_schema_"+name,'query { __type(name:"'+name+'"){fields{name type{kind name ofType{kind name ofType{kind name}}}}} }')
 return out.get("__type",{}).get("fields") or []
def select_fields(name):
 f=fields(name)
 scalar=[x["name"] for x in f if unwrap(x.get("type")).get("kind") in ("SCALAR","ENUM")]
 chosen=[k for k in PREFERRED if k in scalar]
 if not chosen:chosen=scalar[:8]
 return chosen,scalar
def page(field,item):
 selected,all_scalars=select_fields(item)
 sql="query { "+field+'(limit:100,orderBy:"timestamp",orderDirection:"desc") { items { '+' '.join(selected)+" } } }"
 raw=S.gql("query_"+field,sql)
 data=raw.get(field)
 if not isinstance(data,dict) or not isinstance(data.get("items"),list):raise ValueError("Unexpected page schema")
 return {"selected_scalar_fields":selected,"available_scalar_fields":all_scalars,"items":data["items"]}
def main():
 S.OUT=Path("silo_complete_evidence");S.OUT.mkdir(exist_ok=True)
 report={"scope":"Official Silo V3 defaulting liquidation, keeper reward and vault defaults (three independent endpoints)",
         "research_only":True,"validated_terminal_cash":False,"profitable_trades_claimed":0,
         "sources":{},"errors":[],"finished":False,"warnings":[
           "Indexer USD reward value is NOT actual caller cash, gas or attributable profit",
           "Latest-100 indexed events are a capped retrospective sample, not a complete frequency census",
           "All uncertain collateral ownership, debt repayment, and token rights remain unresolved",
           "No trade, signature, broadcast, keys or simulated state mutation"]}
 S.save("REPORT.json",report)
 try:
  assert S.gql("check_live_api","query { __typename }")["__typename"]=="Query"
  for field,item in TYPES:
   record={"field":field,"type":item,"status":"UNAVAILABLE"}
   report["sources"][field]=record
   try:
    data=page(field,item)
    record.update(status="OK",count=len(data["items"]),selected_scalar_fields=data["selected_scalar_fields"],items=data["items"])
   except Exception as e:record.update(status="ERROR",error=repr(e))
   S.save("REPORT.json",report)
  # Attempt canonical receipts of first, median and last event for each supported EVM chain.
  # No per-deposit profit is inferred from multi-action receipts.
  samples=[]
  seen=set()
  for src in report["sources"].values():
   if src.get("status")!="OK":continue
   arr=src["items"]
   for i in sorted({0,len(arr)//2,len(arr)-1}) if arr else []:
    v=arr[i]; tx=v.get("txHash") or v.get("hash")
    try:ch=int(v.get("chainId"))
    except Exception:ch=None
    if not (isinstance(tx,str) and tx.startswith("0x") and len(tx)==66 and ch in S.RPC):continue
    if (ch,tx.lower()) in seen:continue
    seen.add((ch,tx.lower()));row={"source":src["field"],"chain":ch,"tx":tx,"status":"UNVERIFIED"}
    samples.append(row)
    try:
     if int(S.rpc(ch,"chain_id","eth_chainId",[]),16)!=ch:raise ValueError("Chain mismatch")
     rec=S.rpc(ch,"canonical_liquidation_receipt","eth_getTransactionReceipt",[tx])
     if not rec or rec["transactionHash"].lower()!=tx.lower():raise ValueError("Missing canonical receipt")
     row.update(status="RECEIPT_VERIFIED",transaction_success=rec["status"]=="0x1",
         gas_used=int(rec["gasUsed"],16),effective_gas_price_wei=int(rec["effectiveGasPrice"],16),
         log_count=len(rec["logs"]),fee_chain_native_wei=int(rec["gasUsed"],16)*int(rec["effectiveGasPrice"],16))
    except Exception as e:row.update(status="UNAVAILABLE",error=repr(e))
    S.save("REPORT.json",report)
  report["receipt_controls"]=samples
  report["finished"]=all(x.get("status")=="OK" for x in report["sources"].values())
 except Exception as e:report["errors"].append(repr(e));report["traceback"]=traceback.format_exc()
 report["requests"]=S.n;report["denied"]=sorted(S.denied)
 S.save("REPORT.json",report)
 print(json.dumps({"finished":report["finished"],"requests":S.n,"sources":{k:{"status":v["status"],"n":v.get("count"),"error":v.get("error")} for k,v in report["sources"].items()},
 "receipt_samples":len(report.get("receipt_controls",[])),"errors":report["errors"]},indent=2),flush=True)
 if not report["finished"]:raise SystemExit("Research incomplete; retain partial actual event data")
if __name__=="__main__":main()
