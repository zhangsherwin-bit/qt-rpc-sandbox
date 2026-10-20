"""QT Stage1: keyless read-only Cork Phoenix tokenized-risk market existence gate.

This is NOT an exercise, offer, insurance transaction, trade or subscription.
Do not mistake market creation or source documentation for a liquid, accessible
profitable swap. Investigate market activity, live contracts and whitelist.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC,RPCFailure
import json,os

POOL="0xccccccccccccfae2ee43f0e727a8c2969d74b9ec"
WHITELIST="0xccccccccccc6e38a2772eb42d2f408eeb89cb0ee"
OFFSETS=[200,19000,96000,300000,550000,900000]
WINDOW=100
MAX_MARKETS=3
OUT=Path("cork_phoenix_keyless_evidence")
def event_sig(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
MARKET=event_sig("MarketCreated(bytes32,address,address,uint256,address,address,address)")
SWAP=event_sig("PoolSwap(bytes32,address,address,uint256,uint256,uint256,uint256,bool)")
MODIFY=event_sig("PoolModifyLiquidity(bytes32,address,address,uint256,uint256,bool)")
SELECTOR_MARKET=event_sig("market(bytes32)")[:10]
SELECTOR_WHITELIST=event_sig("isMarketWhitelistEnabled(bytes32)")[:10]
TOPICS={MARKET:"MarketCreated",SWAP:"PoolSwap",MODIFY:"PoolModifyLiquidity"}
def number(v):
 if not isinstance(v,str) or not v.startswith("0x"):raise ValueError("invalid uint")
 return int(v,16)
def eth_addr(word):
 if len(word)!=64:raise ValueError("invalid ABI word")
 return "0x"+word[-40:].lower()
def parse(log):
 t=log.get("topics",[])
 if not t or t[0].lower() not in TOPICS:raise ValueError("not a frozen event")
 if str(log.get("address","")).lower()!=POOL:raise ValueError("unexpected emitter")
 if len(t)!=4:raise ValueError("unexpected indexed topics")
 return {"kind":TOPICS[t[0].lower()],"market_id":t[1].lower(),
         "tx":log["transactionHash"].lower(),
         "block":number(log["blockNumber"]),
         "log_index":number(log["logIndex"])}
def market_result(out):
 # Market in Solidity stores eight static fields: two addresses, expiry,
 # rateMin, rateMax, rateChangePerDayMax, rateChangeCapacityMax, rateOracle.
 if len(out)<2+8*64 or not out.startswith("0x"):raise ValueError("malformed market output")
 data=out[2:]
 words=[data[x:x+64] for x in range(0,8*64,64)]
 return {"collateral":eth_addr(words[0]),"reference":eth_addr(words[1]),
         "expiry_timestamp":int(words[2],16),"rate_min":int(words[3],16),
         "rate_max":int(words[4],16),"rate_oracle":eth_addr(words[7])}
def save(report):
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
def run():
 report={"date_utc":datetime.now(timezone.utc).isoformat(),
    "kind":"QT Stage1 source/rights activity gate",
    "contract_source":"Cork-Technology/phoenix (official) contracts/interfaces/IPoolManager.sol",
    "chain":"ethereum","manager":POOL,"whitelist":WHITELIST,
    "keyless_only":True,"authenticated_ru_spent":0,
    "account_secrets_used":False,"no_wallets_no_trades":True,
    "hypothesis":"CA + controlled token rights (cST or cPT) can settle cash or specific risk exposures only when market active/accessible",
    "rights_conditions":["own cST and REF for exercise","unexpired, not paused",
        "current market liquidity","market whitelist allowed",
        "quote versus actual paid acquisition cost","fees and adverse risk"],
    "sample":{"end_offsets":OFFSETS,"length_blocks":WINDOW},
    "windows":[],"market_previews":[],"outcome":"UNRESOLVED"}
 rpc=None
 try:
  # EXPLICIT keyless: do not implicitly read injected GitHub secret.
  rpc=ReadOnlyRPC(1,OUT/"rpc_raw",api_key="",max_requests=28,max_attempts=2)
  if number(rpc.rpc("eth_chainId",[]))!=1:raise ValueError("wrong chain")
  head=number(rpc.rpc("eth_blockNumber",[]))-12
  state=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  if number(state["number"])!=head:raise ValueError("wrong anchor")
  report["anchor"]={"number":head,"timestamp":number(state["timestamp"]),"hash":state["hash"]}
  for label,address in [("PoolManager",POOL),("WhitelistManager",WHITELIST)]:
   code=rpc.rpc("eth_getCode",[address,hex(head)])
   report["contract_"+label+"_deployed_at_anchor"]=bool(code and code!="0x")
  all_events=[]
  for offset in OFFSETS:
   end=head-offset;start=end-WINDOW+1
   row={"start":start,"end":end,"state":"UNRESOLVED"}
   report["windows"].append(row)
   try:
    logs=rpc.rpc("eth_getLogs",[{"address":POOL,"topics":[list(TOPICS)],
        "fromBlock":hex(start),"toBlock":hex(end)}])
    events=[parse(v) for v in logs]
    row.update({"state":"OK","events":len(events),
        "counts":dict(Counter(x["kind"] for x in events)),
        "examples":events[:7]})
    all_events.extend(events)
   except Exception as e:
    row["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
   save(report)
  seen=set()
  for ev in sorted(all_events,key=lambda z:(z["block"],z["log_index"])):
   mid=ev["market_id"]
   if mid in seen:continue
   seen.add(mid)
   if len(report["market_previews"])>=MAX_MARKETS:break
   item={"market_id":mid,"trigger":ev["kind"],"status":"UNRESOLVED"}
   report["market_previews"].append(item)
   try:
    p=rpc.rpc("eth_call",[{"to":POOL,"data":SELECTOR_MARKET+mid[2:]},hex(head)])
    item.update(market_result(p))
    auth=rpc.rpc("eth_call",[{"to":WHITELIST,"data":SELECTOR_WHITELIST+mid[2:]},hex(head)])
    item["market_whitelist_enabled"]=number(auth)!=0
    item["expired_at_anchor"]=item["expiry_timestamp"]<=report["anchor"]["timestamp"]
    item["status"]="MARKET_METADATA_READ"
   except Exception as e:
    item["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
  again=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  report["header_pinned"]=again["hash"]==state["hash"]
  report["activity_event_totals"]=dict(Counter(x["kind"] for x in all_events))
  report["distinct_observed_market_ids"]=len(seen)
  report["complete_windows"]=sum(x["state"]=="OK" for x in report["windows"])
  done=(report["complete_windows"]==len(OFFSETS) and report["header_pinned"] and
    all(x["status"]=="MARKET_METADATA_READ" for x in report["market_previews"]))
  report["outcome"]="BOUNDED_ACTIVITY_TEST_COMPLETE" if done else "INCOMPLETE_DATA"
 except Exception as e:
  report["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
 report["rpc_attempts"]=rpc.attempted if rpc else 0
 save(report)
 print(json.dumps({"outcome":report["outcome"],"complete_windows":report.get("complete_windows",0),
   "events":report.get("activity_event_totals",{}),"previewed_markets":len(report["market_previews"]),
   "authenticated_RU":0,"error":report.get("error_kind")},sort_keys=True))
 return 0 if report["outcome"]=="BOUNDED_ACTIVITY_TEST_COMPLETE" else 2
if __name__=="__main__":raise SystemExit(run())
