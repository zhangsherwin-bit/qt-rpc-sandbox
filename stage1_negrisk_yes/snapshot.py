"""QT Stage1: joint logical conversion PLUS selling complementary YES claims.

Prior PR104 sampled 3-outcome negRisk Gamma event 1228387. The leftover
YES after converting TWO NO claims was conservatively valued at zero.
This experiment checks fresh, contemporaneous six public CLOB books:
three NO ask sides, three YES bid sides, for q=10 and 50 shares.
No orders, account, signing, trading, or Blockmachine RU.
Gamma/event group does NOT establish common onchain NegRisk market identity.
"""
import json,hashlib,time,sys
from pathlib import Path
from decimal import Decimal,InvalidOperation,getcontext
from itertools import combinations
from datetime import datetime,timezone
from urllib.parse import urlencode
import requests

getcontext().prec=50
CLOB="https://clob.polymarket.com/book"
SOURCE_EVENT_ID="1228387"
SOURCE_EVENT="Suwon FC vs. Chungnam Asan FC"
LEGS=[
 {"name":"Suwon win",
  "condition_id":"0x32873e942c695beba92b47e244f71aa68baa17ef214340959eebcc6264ab0c28",
  "yes":"99231898181766691923521669564172398282499919053758611146588853527338675556260",
  "no":"55424512431271925347929462825920883782033089367748261334832862470314269723414"},
 {"name":"Draw",
  "condition_id":"0xa35ed38f9e8cef2615f6d5c2722a2395e7a8195d71dc4e55c98d45e4a61e297b",
  "yes":"107025531901372292792255724110647271580719217507047996717290295634346149227044",
  "no":"41572182330897127934334144303749616967477581478446240849812374319933334023853"},
 {"name":"Chungnam win",
  "condition_id":"0x8320c870382ceeb3763001cfc3765b1097c24570dd408ff65bf9305e970ea480",
  "yes":"72794422335830766972252327395839238175586300873815196733193733214981060087021",
  "no":"83869293759688656473158806274375575070608059154863889157837135988147791198853"}
]
SIZES=[Decimal("10"),Decimal("50")]
MAX_HTTP=6
OUT=Path("stage1_negrisk_yes_residual_evidence")
RPT={"at_utc":datetime.now(timezone.utc).isoformat(),
 "hypothesis":"m NO => m-1 collateral plus YES on outcomes not converted; cash sell residual YES at finite bid",
 "selection":"First 3-outcome non-exact-score event from PR104 frozen public Gamma result, selected exploratory after NO-only negative",
 "gamma_event_id":SOURCE_EVENT_ID,"event_title":SOURCE_EVENT,
 "prior_PR104_same_market_identity_not_verified":True,
 "source":"Polymarket NegRiskAdapter docs convertPositions() and public CLOB orders",
 "coin_data":LEGS,"requests":0,"positions":[],"books":{},
 "outcome":"UNRESOLVED","zero_residual_yes_valuation_in_prior_screen":True,
 "risks":["source event grouping not confirmed same marketId",
          "fee rate and physical conversion method / approvals not validated",
          "CLOB books sequential snapshots, not simultaneous atomic matched fills",
          "actual user leg position and collateral capital not owned by QT",
          "market minimum sizes, gas, execution and in-game event resolution",
          "positive margin before fees not a feasible live trade"],
 "profit_verified":False,"trades":0,"authenticated_RU":0}
def dec(x):
 a=Decimal(str(x))
 if not a.is_finite():raise ValueError("Nonfinite")
 return a
def save():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(RPT,indent=2,sort_keys=True,default=str)+"\n")
def quote(book,side,q):
 # BUY NO consumes asks low->high, SELL YES consumes bids high->low.
 levels=book.get("asks" if side=="buy" else "bids",[])
 if not isinstance(levels,list):return {"fill":False,"reason":"NO_LEVELS"}
 try:
  if q<dec(book.get("min_order_size","0")or 0):
   return {"fill":False,"reason":"MIN_ORDER_SIZE"}
  arr=[]
  for row in levels:
   p,v=dec(row["price"]),dec(row["size"])
   if p>0 and p<=1 and v>0:arr.append((p,v))
  arr.sort(key=lambda z:z[0],reverse=side=="sell")
  remaining=q;total=Decimal(0)
  for p,v in arr:
   a=min(v,remaining)
   remaining-=a;total+=a*p
   if remaining<=0:break
  if remaining>0:
   return {"fill":False,"reason":"INSUFFICIENT_DEPTH","available_quantity":str(q-remaining)}
  return {"fill":True,"cash_usdc":str(total),"vwap":str(total/q)}
 except (KeyError,InvalidOperation,TypeError,ValueError):return {"fill":False,"reason":"INVALID_LEVELS"}
def settlement(noask,yesbid,q,chosen_indices):
 idx=set(chosen_indices)
 if len(idx) not in (2,3):raise ValueError("invalid m")
 nos=[noask[i] for i in idx]
 unselected=[i for i in range(3) if i not in idx]
 if not all(x.get("fill") for x in nos):
  return {"classification":"NOT_FILLABLE_NO_DEPTH","m":len(idx)}
 out_yes=[yesbid[i] for i in unselected]
 if not all(x.get("fill") for x in out_yes):
  return {"classification":"NOT_FILLABLE_YES_BID_DEPTH","m":len(idx)}
 cost=sum((dec(x["cash_usdc"])for x in nos),Decimal(0))
 cash=q*Decimal(len(idx)-1)
 sale=sum((dec(x["cash_usdc"])for x in out_yes),Decimal(0))
 net=cash+sale-cost
 return {"m":len(idx),"selected_no_indices":list(sorted(idx)),
  "residual_yes_indices":unselected,"q":str(q),
  "no_ask_cost_usdc":str(cost),"collateral_release_usdc":str(cash),
  "residual_yes_real_book_bid_usdc":str(sale),
  "cash_before_conversion_fee_and_trading_cost":str(net),
  "classification":"POSITIVE_CONDITIONAL_BOOK_BOUND" if net>0 else "NONPOSITIVE_CONDITIONAL_BOOK_BOUND",
  "not_proof_of_same_onchain_negrisk_market":True}
def get_book(side,token,label):
 if RPT["requests"]>=MAX_HTTP:raise RuntimeError("PUBLIC_HTTP_CAP")
 u=CLOB+"?"+urlencode({"token_id":token})
 RPT["requests"]+=1
 tag=f"{RPT['requests']:02}_{label}"
 resp=requests.get(u,timeout=(10,25),allow_redirects=False,
    headers={"Accept":"application/json"})
 raw=resp.content
 if len(raw)>1500000:raise RuntimeError("RESPONSE_TOO_LARGE")
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/(tag+".request")).write_text("GET "+u+"\n")
 (OUT/(tag+".response")).write_bytes(raw)
 RPT.setdefault("original_hashes",[]).append({"name":tag,
     "http":resp.status_code,"request_sha256":hashlib.sha256(("GET "+u+"\n").encode()).hexdigest(),
     "response_sha256":hashlib.sha256(raw).hexdigest()})
 save()
 time.sleep(0.9)
 if resp.status_code in (401,403,429):raise RuntimeError("PUBLIC_CLOB_DENIAL_"+str(resp.status_code))
 if resp.status_code!=200:raise RuntimeError("HTTP_"+str(resp.status_code))
 data=resp.json()
 if not isinstance(data,dict):raise ValueError("INVALID_BOOK_SCHEMA")
 return data
def main():
 save()
 try:
  for i,leg in enumerate(LEGS):
   for side in ("no","yes"):
    raw=get_book(side,leg[side],f"leg{i}_{side}")
    RPT["books"][f"leg{i}_{side}"]={str(q):quote(raw,"buy" if side=="no" else "sell",q)for q in SIZES}
    save()
  all_results=[]
  for q in SIZES:
   buy=[RPT["books"][f"leg{i}_no"][str(q)]for i in range(3)]
   sell=[RPT["books"][f"leg{i}_yes"][str(q)]for i in range(3)]
   for size in (2,3):
    for ids in combinations(range(3),size):
     all_results.append(settlement(buy,sell,q,ids))
  RPT["positions"]=all_results
  RPT["summary"]={"same_event_group_considered":SOURCE_EVENT_ID,
   "tested_portfolios":len(all_results),
   "fully_bid_ask_fillable":sum(x["classification"]in
      ("POSITIVE_CONDITIONAL_BOOK_BOUND","NONPOSITIVE_CONDITIONAL_BOOK_BOUND")for x in all_results),
   "positive_cash_bound_count":sum(x["classification"]=="POSITIVE_CONDITIONAL_BOOK_BOUND"for x in all_results),
   "actual_eligible_onchain_conversions":0,
   "all_event_group_membership_and_fee_still_unverified":True}
  RPT["outcome"]="SIX_FRESH_BOOKS_COMPLETE"
 except Exception as e:
  RPT["outcome"]="BLOCKED_OR_INCOMPLETE"
  RPT["failure"]=str(e)[:72] if "PUBLIC_CLOB_DENIAL_" in str(e) else type(e).__name__
 save()
 print(json.dumps({"status":RPT["outcome"],"requests":RPT["requests"],
   "summary":RPT.get("summary"),"failure":RPT.get("failure"),
   "trades":0,"blockmachine_ru":0},sort_keys=True))
 return 0 if RPT["outcome"]=="SIX_FRESH_BOOKS_COMPLETE" else 2
if __name__=="__main__":sys.exit(main())