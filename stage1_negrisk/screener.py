"""QT Stage1: real public books for Polymarket NegRisk conversion portfolios.

PUBLIC GET-ONLY: no authentication, wallet, order, quote acceptance, or trade.
Two Gamma pages (100 events each), first three qualifying negRisk events in
server response order, up to four NO legs each. One snapshot per book. A
possible m-NO->(m-1)USDC+complementary YES conversion is NOT a cash-profit
claim until same NegRisk on-chain market ID, fee, outcome rules, fillability,
rights, executable size and latency are independently confirmed.
"""
from decimal import Decimal, InvalidOperation, getcontext
from datetime import datetime, timezone
from pathlib import Path
from itertools import combinations
from collections import Counter
import json, hashlib, time, urllib.parse, sys

getcontext().prec=45
OUT=Path("stage1_negrisk_evidence")
GAMMA="https://gamma-api.polymarket.com/events"
CLOB="https://clob.polymarket.com/book"
MAX_GAMMA=2
PAGE_SIZE=100
MAX_GROUPS=3
MAX_LEGS=4
QUANTITIES=[Decimal("10"),Decimal("50")]
MAX_HTTP=MAX_GAMMA+MAX_GROUPS*MAX_LEGS
ZERO=Decimal("0")
ONE=Decimal("1")
RPT={
 "date_utc":datetime.now(timezone.utc).isoformat(),
 "hypothesis":"Buy m negRisk NO tokens; contractually convert for m-1 USDC per share plus residual complementary YES",
 "official_adapter":"https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/docs/NegRiskAdapter.md",
 "method":"First three source-ranked eligible groups; first four orderable NO assets/group; no positive-outcome cherry-picking",
 "limits":{"gamma_pages":MAX_GAMMA,"gamma_limit":PAGE_SIZE,"max_groups":MAX_GROUPS,
           "no_assets_per_group":MAX_LEGS,"quantity_shares":[str(x) for x in QUANTITIES],
           "max_http_requests":MAX_HTTP,"sleep_seconds_between_calls":1.6},
 "criteria":{"source_negRisk_flag":True,"source_event_grouping_only_not_onchain_market_id":True,
             "zero_value_assigned_to_residual_yes":True,"fees_and_adapter_execution_unverified":True,
             "market_order_depth_required":True},
 "groups":[],"source_pages":[],"http_requests_sent":0,"overall_status":"UNRESOLVED",
 "trades":0,"key_or_wallet_used":False,"blockmachine_authenticated_ru":0,
 "realized_profit":None,"stage2_promotion":False
}
def record():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(RPT,indent=2,sort_keys=True,default=str)+"\n")
def dec(v):
 if isinstance(v,bool):raise ValueError("bool not decimal")
 z=Decimal(str(v))
 if not z.is_finite():raise ValueError("non-finite price")
 return z
def parse_json_field(x):
 if isinstance(x,list):return x
 if isinstance(x,str):
  v=json.loads(x)
  if isinstance(v,list):return v
 return []
def allowed_market(m):
 if not isinstance(m,dict):return False
 if not (m.get("negRisk") is True):return False
 if m.get("closed") is True or m.get("active") is False:return False
 if m.get("enableOrderBook") is False or m.get("acceptingOrders") is False:return False
 outcomes=parse_json_field(m.get("outcomes"))
 tokens=parse_json_field(m.get("clobTokenIds"))
 if len(outcomes)!=2 or len(tokens)!=2:return False
 return all(isinstance(i,str) and i for i in tokens) and [str(s).lower() for s in outcomes]==["yes","no"]
def candidate_groups(events):
 groups=[]
 for item in events:
  if not isinstance(item,dict):continue
  raw=item.get("markets",[])
  if not isinstance(raw,list):continue
  matches=[]
  for m in raw:
   if allowed_market(m):
    tokens=parse_json_field(m["clobTokenIds"])
    matches.append({"condition_id":str(m.get("conditionId","")),
      "question":str(m.get("question",""))[:240],
      "no_token_id":str(tokens[1]),
      "negRiskMarketID":m.get("negRiskMarketID"),
      "negRiskFeeBips":m.get("negRiskFeeBips")})
  unique=[];seen=set()
  for m in matches:
   if m["condition_id"] and m["condition_id"] not in seen:
    unique.append(m);seen.add(m["condition_id"])
  if len(unique)>=3:
   groups.append({"gamma_event_id":str(item.get("id","")),
                  "event_slug":str(item.get("slug",""))[:200],
                  "event_title":str(item.get("title",""))[:220],
                  "event_negRisk":item.get("negRisk"),
                  "market_count_in_event":len(raw),
                  "qualifying_negRisk_markets":len(unique),
                  "sampled_legs":unique[:MAX_LEGS],
                  "book_checks":[],"tested_portfolios":[],
                  "state":"UNTESTED",
                  "identity_warning":"Event nesting is not proof of single on-chain NegRisk adapter marketId"})
  if len(groups)>=MAX_GROUPS:break
 return groups
def depth_cost(book,qty):
 if not isinstance(book,dict) or not isinstance(book.get("asks"),list):
  return {"eligible":False,"reason":"MALFORMED_ASK_BOOK"}
 try:
  minsize=dec(book.get("min_order_size","0") or "0")
  if qty<minsize:return {"eligible":False,"reason":"BELOW_EXCHANGE_MIN_SIZE"}
  levels=[]
  for r in book["asks"]:
   price=dec(r["price"]);size=dec(r["size"])
   if not ZERO<price<=ONE or size<=ZERO:continue
   levels.append((price,size))
  levels.sort()
  need=qty;paid=ZERO
  for price,vol in levels:
   take=min(need,vol)
   paid+=take*price;need-=take
   if need<=ZERO:break
  if need>ZERO:return {"eligible":False,"reason":"INSUFFICIENT_ASK_DEPTH",
                        "unfilled":str(need),"available_depth":str(qty-need)}
  return {"eligible":True,"gross_cost_usdc":str(paid),
          "weighted_ask_price_usdc":str(paid/qty),
          "min_order_size":str(minsize),"levels_eaten":len(levels)}
 except (ValueError,KeyError,InvalidOperation,TypeError,ArithmeticError):
  return {"eligible":False,"reason":"INVALID_ASK_VALUES"}
def immediate_cash_bounds(legs,qty):
 # m NO token legs, sold by m independent holders; no YES values counted.
 # Source NegRiskAdapter contract converts m positions for m-1 collateral.
 out=[]
 for size in range(2,min(MAX_LEGS,len(legs))+1):
  for comb in combinations(legs,size):
   ds=[m["depth"][str(qty)] for m in comb]
   if not all(d.get("eligible") for d in ds):continue
   spent=sum((dec(d["gross_cost_usdc"]) for d in ds),ZERO)
   received=qty*Decimal(size-1)
   diff=received-spent
   out.append({"m":size,"no_market_questions":[x["question"] for x in comb],
     "no_condition_ids":[x["condition_id"] for x in comb],
     "buy_quantity_per_NO":str(qty),
     "cost_to_acquire_NO_usdc":str(spent),
     "protocol_convert_collateral_before_fee_usdc":str(received),
     "cash_surplus_before_fees_and_execution_usdc":str(diff),
     "yes_positions_residual_value_assumed_usdc":"0",
     "classification":("POSITIVE_THEORETICAL_COLLATERAL_BOUND_UNEXECUTED" if diff>ZERO
       else "NONPOSITIVE_COLLATERAL_BOUND"),
     "ONCHAIN_ADAPTER_RIGHTS_AND_FEES_NOT_VERIFIED":True})
 return out
def get(url,label):
 import requests
 if RPT["http_requests_sent"]>=MAX_HTTP:raise RuntimeError("HTTP_RUN_CAP")
 RPT["http_requests_sent"]+=1
 entry={"label":label,"url":url,"http_status":None,"json_valid":False,
        "utc":datetime.now(timezone.utc).isoformat()}
 raw=b""
 try:
  response=requests.get(url,headers={"Accept":"application/json",
     "User-Agent":"QT-research-readonly/1.0"},timeout=(8,24),allow_redirects=False)
  entry["http_status"]=int(response.status_code)
  if len(response.content)>2400000:raise ValueError("OVERSIZE_RESPONSE")
  raw=response.content
  entry["content_bytes"]=len(raw)
  entry["sha256"]=hashlib.sha256(raw).hexdigest()
  (OUT/(label+".response")).write_bytes(raw)
  (OUT/(label+".request")).write_text("GET "+url+"\n")
  record()
  if response.status_code in (401,403,429):
   raise RuntimeError("PROVIDER_HTTP_DENIAL_"+str(response.status_code))
  if response.status_code!=200:raise RuntimeError("HTTP_"+str(response.status_code))
  obj=response.json();entry["json_valid"]=True
  return obj,entry
 finally:
  RPT.setdefault("requests",[]).append(entry)
  record()
  time.sleep(1.6)
def main():
 record()
 try:
  source=[]
  for page in range(MAX_GAMMA):
   q=urllib.parse.urlencode({"limit":PAGE_SIZE,"offset":page*PAGE_SIZE,
                "active":"true","closed":"false","order":"id","ascending":"false"})
   data,resp=get(GAMMA+"?"+q,"gamma_"+str(page))
   if not isinstance(data,list):raise ValueError("GAMMA_SCHEMA_INVALID")
   source.extend(data)
   RPT["source_pages"].append({"page":page,"events":len(data),
                               "status":resp["http_status"],"sha256":resp["sha256"]})
  chosen=candidate_groups(source)
  RPT["groups"]=chosen
  RPT["events_inspected"]=len(source)
  RPT["eligible_groups_found_in_200_events"]=len(chosen)
  for i,g in enumerate(chosen):
   for j,leg in enumerate(g["sampled_legs"]):
    token=leg["no_token_id"]
    url=CLOB+"?"+urllib.parse.urlencode({"token_id":token})
    try:
     book,_=get(url,f"group{i}_no{j}")
     leg["depth"]={str(q):depth_cost(book,q) for q in QUANTITIES}
     leg["price_tick_size"]=book.get("tick_size") if isinstance(book,dict) else None
    except Exception as exc:
     leg["book_error"]=type(exc).__name__
     if "PROVIDER_HTTP_DENIAL" in str(exc):raise
     leg["depth"]={str(q):{"eligible":False,"reason":"BOOK_UNAVAILABLE"} for q in QUANTITIES}
    record()
   g["tested_portfolios"]=sum([immediate_cash_bounds(g["sampled_legs"],q) for q in QUANTITIES],[])
   g["book_coverage"]=sum(all(x.get("eligible") or x.get("reason")=="INSUFFICIENT_ASK_DEPTH"
                     for x in (leg["depth"].values())) for leg in g["sampled_legs"])
   g["state"]="PORTFOLIO_CASH_ENVELOPES_EVALUATED"
   record()
  RPT["screener_summary"]={"groups_with>=3_source_legs":len(chosen),
   "portfolios_evaluated":sum(len(g["tested_portfolios"]) for g in chosen),
   "positive_theoretical_cash_envelopes":sum(
     1 for g in chosen for p in g["tested_portfolios"]
     if p["classification"]=="POSITIVE_THEORETICAL_COLLATERAL_BOUND_UNEXECUTED"),
   "contractual_conversion_eligibility_unverified":True,
   "zero_actual_trades":True}
  RPT["overall_status"]="PUBLIC_ORDER_BOOK_COHORT_COMPLETE"
 except Exception as e:
  RPT["overall_status"]="UNRESOLVED_PUBLIC_DATA"
  RPT["error_class"]=str(e)[:80] if "PROVIDER_HTTP_DENIAL" in str(e) else type(e).__name__
 record()
 print(json.dumps({"status":RPT["overall_status"],"requests":RPT["http_requests_sent"],
    "events":RPT.get("events_inspected"),"groups":len(RPT["groups"]),
    "summary":RPT.get("screener_summary"),"error":RPT.get("error_class"),
    "no_trades":True,"blockmachine_ru":0},sort_keys=True))
 return 0 if RPT["overall_status"]=="PUBLIC_ORDER_BOOK_COHORT_COMPLETE" else 2
if __name__=="__main__":sys.exit(main())