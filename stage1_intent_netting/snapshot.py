"""QT Stage1 novel order-netting test: publicly offered UniswapX Dutch signed orders.
GET-only, no account, key, submit, wallet, signed tx or exchange interaction.
A positive clearing ENVELOPE is NOT an executable auction or trading P&L.
"""
import json
import time
import itertools
import hashlib
import urllib.parse
from collections import defaultdict,Counter
from datetime import datetime,timezone
from pathlib import Path

OUT=Path("uniswapx_netting_evidence");OUT.mkdir(exist_ok=True)
API="https://api.uniswap.org/v2/orders"
SOURCES=[(1,"Dutch_V2"),(8453,"Dutch_V3")]
SAMPLE_WAVES=4
WAVE_WAIT_SECONDS=13
MAX_ORDERS_PER_CALL=50
MAX_ORDER_MATCHES_SAVED=12
RPT={"utc_start":datetime.now(timezone.utc).isoformat(),
 "hypothesis":"two or three simultaneous opposite-direction signed UniswapX orders may be jointly cash-self-financing under reactor executeBatchWithCallback",
 "selection":"all open orders in newest 50 on fixed chain/type, not selected by outcome",
 "predeclared":{"sources":[{"chain":c,"type":t} for c,t in SOURCES],
               "waves":SAMPLE_WAVES,"wait_seconds":WAVE_WAIT_SECONDS,
               "query_limit":MAX_ORDERS_PER_CALL,"pair_three_cycle":True,
               "scoring":"min(input start,end) vs max(all outputs start,end) in raw token units",
               "no_decimals_or_nominal_usd_assumptions":True},
 "wave_results":[],"errors":[],"http_get_count":0,"no_wallet_no_trade":True,
 "no_auth_or_rate_bypass":True,"profitable_execution_proved":False}
ADDRESS_LEN=42
def save():
 (OUT/"REPORT.json").write_text(json.dumps(RPT,sort_keys=True,indent=2)+"\n")
def address(s):
 return isinstance(s,str) and len(s)==42 and s[:2]=="0x" and all(ch in "0123456789abcdefABCDEF" for ch in s[2:])
def unsigned(a):
 if isinstance(a,bool) or not isinstance(a,(int,str)):raise ValueError("non-integer amount")
 if isinstance(a,str) and (not a.isdigit() or len(a)>78):raise ValueError("invalid amount string")
 v=int(a)
 if v<0 or v>2**256-1:raise ValueError("amount outside uint256")
 return v
def normalize_order(o,chain,order_type):
 if not isinstance(o,dict):return None
 if o.get("orderStatus")!="open":return None
 if o.get("chainId") is not None and int(o["chainId"])!=chain:return None
 if str(o.get("type",o.get("orderType",order_type))).lower() not in [order_type.lower(),"dutch"]:
  return None
 inp=o.get("input"); outs=o.get("outputs")
 if not isinstance(inp,dict) or not isinstance(outs,list) or not outs:return None
 tin=inp.get("token"); key=o.get("orderHash") or o.get("orderId")
 if not address(tin) or not key:return None
 start=unsigned(inp["startAmount"]);end=unsigned(inp["endAmount"])
 if min(start,end)==0:return None
 output_map=defaultdict(int)
 for x in outs:
  if not isinstance(x,dict) or not address(x.get("token")):return None
  # EVERY output counted including protocol/filler/recipient fee outputs.
  token=x["token"].lower()
  a=unsigned(x["startAmount"]);b=unsigned(x["endAmount"])
  output_map[token]+=max(a,b)
 rec={
  "id":str(key)[:130],"chain":chain,"type":order_type,
  "input_token":tin.lower(),"conservative_input_raw":min(start,end),
  "outputs_max_raw":dict(output_map),
  "fee_outputs_count":sum(bool(x.get("isFeeOutput")) for x in outs),
  "created_at":str(o.get("createdAt",""))[:50],
  "expiry_claim_UNVERIFIED":True}
 return rec
def net(orders):
 v=defaultdict(int)
 for o in orders:
  v[o["input_token"]]+=o["conservative_input_raw"]
  for t,qty in o["outputs_max_raw"].items():v[t]-=qty
 return {t:x for t,x in v.items() if x!=0}
def all_nonnegative_inventory(orders):
 v=net(orders)
 return bool(v) and all(q>=0 for q in v.values()) and any(q>0 for q in v.values())
def evaluate(orders):
 # Only true opposite-direction order pairs and 3-asset paths; other possible
 # multilateral clears are outside this inexpensive finite test.
 pair_count=0;triangle_count=0;safe=[];evaluated_pair=0;evaluated_tri=0
 directional=defaultdict(list)
 for x in orders:
  if len(x["outputs_max_raw"])==1:
   other=next(iter(x["outputs_max_raw"]))
   if other!=x["input_token"]:directional[(x["input_token"],other)].append(x)
 for (a,b),forward in directional.items():
  for x in forward:
   for y in directional.get((b,a),[]):
    if x["id"]>=y["id"]:continue
    evaluated_pair+=1
    if all_nonnegative_inventory((x,y)):
     pair_count+=1
     if len(safe)<MAX_ORDER_MATCHES_SAVED:
      safe.append({"family":"opposing_pair","order_ids":[x["id"],y["id"]],
                   "raw_token_residuals":{k:str(v) for k,v in net((x,y)).items()}})
 # No more than 50 open orders -> <=125000 triples. Restrict distinct assets
 # and unique orders to avoid doubled paths (canonical rotated order id).
 for (a,b),first in directional.items():
  for (bb,c),second in directional.items():
   if b!=bb or len({a,b,c})!=3:continue
   for x in first:
    for y in second:
     if x["id"]==y["id"]:continue
     for z in directional.get((c,a),[]):
      ids=[x["id"],y["id"],z["id"]]
      if len(set(ids))<3 or x["id"]!=min(ids):continue
      evaluated_tri+=1
      if all_nonnegative_inventory((x,y,z)):
       triangle_count+=1
       if len(safe)<MAX_ORDER_MATCHES_SAVED:
        safe.append({"family":"three_order_cycle","order_ids":ids,
                     "raw_token_residuals":{k:str(v) for k,v in net((x,y,z)).items()}})
 return {"open_orders_normalized":len(orders),"opposing_pairs_checked":evaluated_pair,
         "three_order_cycles_checked":evaluated_tri,
         "conservative_envelope_pass_pair":pair_count,
         "conservative_envelope_pass_cycle":triangle_count,
         "examples":safe,
         "IMPORTANT":"A conservative inventory envelope is only necessary cash accounting; signer validity, exclusivity expiration, nonce, gas, prices, same-call batch and order cancellation remain unproven"}
def get_order_snapshot(chain,kind,wave):
 import requests
 qs={"orderStatus":"open","chainId":chain,"orderType":kind,"limit":MAX_ORDERS_PER_CALL}
 url=API+"?"+urllib.parse.urlencode(qs)
 label=f"wave{wave}_chain{chain}"
 rec={"chain":chain,"type":kind,"wave":wave,"utc":datetime.now(timezone.utc).isoformat(),
      "status":"UNRESOLVED"}
 RPT["wave_results"].append(rec)
 RPT["http_get_count"]+=1
 raw=b"";status=-1
 try:
  with requests.get(url,headers={"Accept":"application/json","User-Agent":"QT-Stage1-Research/1"},
                    timeout=(10,23),allow_redirects=False,stream=True) as response:
   status=response.status_code
   raw=response.raw.read(2_400_000)
 except Exception as exc:
  rec["transport_failure"]=type(exc).__name__
 finally:
  (OUT/(label+".http_request")).write_text("GET "+url+"\n")
  (OUT/(label+".http_response")).write_bytes(raw)
  rec["http_status"]=status
  rec["response_sha256"]=hashlib.sha256(raw).hexdigest()
  rec["bytes"]=len(raw)
  save()
 if status!=200:
  rec["status"]="HTTP_UNAVAILABLE"
  return rec
 try:
  data=json.loads(raw)
  originals=data.get("orders") if isinstance(data,dict) else None
  if not isinstance(originals,list):raise ValueError("missing orders list")
  orders=[];seen=set();rejected=0
  for entry in originals:
   try:o=normalize_order(entry,chain,kind)
   except Exception:o=None
   if o is None or o["id"] in seen:rejected+=1;continue
   seen.add(o["id"]);orders.append(o)
  rec["source_returned_rows"]=len(originals)
  rec["rejected_or_duplicated_rows"]=rejected
  rec["selected_orders"]=orders
  rec["test"]=evaluate(orders)
  rec["status"]="OPEN_BOOK_SNAPSHOT"
 except Exception as e:
  rec["status"]="UNRESOLVED"
  rec["parser_exception"]=type(e).__name__
 save()
 return rec
def main():
 save()
 for wave in range(SAMPLE_WAVES):
  for chain,kind in SOURCES:
   rec=get_order_snapshot(chain,kind,wave)
   if rec.get("http_status") in (401,403,429):
    RPT["errors"].append({"phase":"provider_denial","chain":chain,"http":rec["http_status"]})
    RPT["complete"]=False;save()
    print(json.dumps({"complete":False,"cause":"provider request rejected; did not rotate or retry"}));return 1
   time.sleep(2) # below Uniswap's 4 RPS documented ceiling
  if wave+1<SAMPLE_WAVES:time.sleep(WAVE_WAIT_SECONDS)
 RPT["complete"]=len(RPT["wave_results"])==SAMPLE_WAVES*len(SOURCES) and all(w["status"]=="OPEN_BOOK_SNAPSHOT" for w in RPT["wave_results"])
 RPT["summary"]={
  "completed":sum(w["status"]=="OPEN_BOOK_SNAPSHOT" for w in RPT["wave_results"]),
  "orders_observed_per_wave":[w.get("source_returned_rows") for w in RPT["wave_results"]],
  "conservative_cash_envelope_pair_hits":sum(w.get("test",{}).get("conservative_envelope_pass_pair",0) for w in RPT["wave_results"]),
  "conservative_cash_envelope_cycle_hits":sum(w.get("test",{}).get("conservative_envelope_pass_cycle",0) for w in RPT["wave_results"]),
  "not_revenue_and_not_execution_proof":True}
 save()
 print(json.dumps({"complete":RPT["complete"],"summary":RPT["summary"],"requests":RPT["http_get_count"],"no_trades":True}))
 return 0 if RPT["complete"] else 2
if __name__=="__main__":
 raise SystemExit(main())
