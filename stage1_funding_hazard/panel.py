"""QT Stage1: independent demand-for-leverage fee market, stochastic sign persistence.

6 public Hyperliquid info fundingHistory requests only; no key, wallet,
account, order or position. Fixed 168h training and 168h forward holdout
on BTC/ETH/SOL, chosen before examining rates. Never report the historical
funding sum as hedged trading PnL; hedging basis, fees, capital, liquidation
and counterparty risk need their own proof.
"""
from decimal import Decimal,InvalidOperation
from datetime import datetime,timezone
from collections import Counter
from pathlib import Path
import requests,json,time,hashlib,math,sys

API="https://api.hyperliquid.xyz/info"
COINS=["BTC","ETH","SOL"]
WINDOWS=[
 ("TRAIN","2026-09-10T00:00:00+00:00","2026-09-17T00:00:00+00:00"),
 ("HOLDOUT","2026-10-10T00:00:00+00:00","2026-10-17T00:00:00+00:00")]
MAX_REQUESTS=6
OUT=Path("stage1_funding_evidence")
RPT={"as_of_utc":datetime.now(timezone.utc).isoformat(),
 "hypothesis":"Funding paid by leverage users may yield non-priority revenue, but sign persistence and financing are uncertain",
 "frozen":{"coins":COINS,"windows":WINDOWS,"max_http_posts":MAX_REQUESTS,
  "primary_predictor":"binary first-order Markov sign transition, Laplace smoothing",
  "baseline_predictor":"unconditional positive rate from training window",
  "constant_holdout_direction":"short perp (long funded spot) sign from training average"},
 "status":"UNRESOLVED","requests":0,"coins":{},
 "permissions":{"keyless":True,"no_orders":True,"no_trades":True,
  "blockmachine_authenticated_RU":0,"no_venue_account":True},
 "no_realized_pnl":True,
 "missing_for_profit":["spot acquisition funding and borrow APR","perp/spot executions at same clock",
   "liquidation and margin buffer","change in spot-perp basis","fees and adverse selection",
   "exchange downtime, insurance, transfer/withdrawal timing"]}
def store():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(RPT,indent=2,sort_keys=True)+"\n")
def millis(iso):
 return int(datetime.fromisoformat(iso).timestamp()*1000)
def funding_rows(rows,start,end):
 if not isinstance(rows,list):raise ValueError("FUNDING_RESPONSE_NOT_LIST")
 map_hour={};invalid=0;duplicates=0
 for r in rows:
  try:
   if not isinstance(r,dict):raise ValueError()
   tm=int(r["time"])
   rt=Decimal(str(r["fundingRate"]))
   if not rt.is_finite() or abs(rt)>Decimal("0.5"):raise ValueError()
   if tm<start or tm>=end:continue
   hr=tm//3600000
   if hr in map_hour:duplicates+=1;continue
   map_hour[hr]=rt
  except (ValueError,TypeError,InvalidOperation,KeyError):invalid+=1
 return map_hour,{"invalid":invalid,"duplicates":duplicates,"raw_rows":len(rows)}
def analyse(rows,start,end):
 vals,d=funding_rows(rows,start,end)
 hours=list(range(start//3600000,end//3600000))
 observed=[vals[k] for k in hours if k in vals]
 positive=sum(1 for x in observed if x>0)
 negative=sum(1 for x in observed if x<0)
 zero=sum(1 for x in observed if x==0)
 return {"expected_hours":len(hours),"observed_hours":len(observed),
  "complete":len(observed)==len(hours) and d["duplicates"]==0 and d["invalid"]==0,
  "sum_of_rates_short_perp_percent_of_notional":str(sum(observed,Decimal("0"))*100),
  "mean_hourly_funding_rate":str(sum(observed,Decimal("0"))/len(observed)) if observed else None,
  "positive":positive,"negative":negative,"zero":zero,
  "sign_changes":sum((a>0)!=(b>0) for a,b in zip(observed,observed[1:])),
  "data":d,"hourly_rates":{str(k):str(v)for k,v in vals.items()}}
def markov_assessment(train,held,start_train,start_held):
 trainhours=list(range(start_train//3600000,start_train//3600000+168))
 holdhours=list(range(start_held//3600000,start_held//3600000+168))
 x=[int(train[k]>0) for k in trainhours]
 y=[int(held[k]>0) for k in holdhours]
 base_p=(sum(x)+1)/(len(x)+2)
 mat=[[1,1],[1,1]]
 for a,b in zip(x,x[1:]):mat[a][b]+=1
 p0=mat[0][1]/sum(mat[0]);p1=mat[1][1]/sum(mat[1])
 base_scores=[(base_p,t) for t in y]
 markov_scores=[(p1 if ((y[i-1] if i else x[-1])==1) else p0,y[i])
                for i in range(len(y))]
 def logloss(pairs):
  return sum(-(v*math.log(p)+(1-v)*math.log(1-p)) for p,v in pairs)/len(pairs)
 def brier(pairs):
  return sum((p-y)**2 for p,y in pairs)/len(pairs)
 hold_rates=[held[k] for k in holdhours]
 sumrate=sum(hold_rates,Decimal("0"))
 train_rate=sum((train[k] for k in trainhours),Decimal("0"))
 # Hypothetical SPOT long + PERP short only, no financing or margin/hedge PnL.
 funding_earned_for_short=sumrate
 return {"training_positive_fraction":sum(x)/len(x),
  "p_after_positive_from_train":p1,"p_after_nonpositive_from_train":p0,
  "baseline_holdout_logloss":logloss(base_scores),
  "markov_holdout_logloss":logloss(markov_scores),
  "baseline_holdout_brier":brier(base_scores),
  "markov_holdout_brier":brier(markov_scores),
  "funding_short_perp_holdout_percent_notional":str(funding_earned_for_short*100),
  "hypothetical_roundtrip_cost_budget_bps_if_short_held_full_week":str(funding_earned_for_short*Decimal("10000")),
  "train_sign_positive":train_rate>0,
  "holdout_sign_positive":sumrate>0,
  "MARKOV_NOT_ASSUMED_CORRECT":True,
  "FUNDING_SUM_IS_NOT_TRADING_PNL":True}
def fetch(coin,label,from_ms,to_ms):
 if RPT["requests"]>=MAX_REQUESTS:raise RuntimeError("REQUEST_CAP")
 RPT["requests"]+=1
 body=json.dumps({"type":"fundingHistory","coin":coin,"startTime":from_ms,
                  "endTime":to_ms-1},separators=(",",":")).encode()
 k=f"{label}_{coin}"
 report={"coin":coin,"period":label,
         "request_sha256":hashlib.sha256(body).hexdigest()}
 try:
  response=requests.post(API,data=body,headers={"Content-Type":"application/json","Accept":"application/json",
   "User-Agent":"QT-Stage1-Keyless-Research/1.0"},timeout=(10,28),allow_redirects=False)
  if len(response.content)>2_000_000:raise RuntimeError("RESPONSE_TOO_LARGE")
  raw=response.content
  report["http_status"]=response.status_code
  report["response_sha256"]=hashlib.sha256(raw).hexdigest()
  (OUT/(k+".request")).write_bytes(body)
  (OUT/(k+".response")).write_bytes(raw)
  RPT.setdefault("raw_evidence",[]).append(report);store()
  if response.status_code in (401,403,429):raise RuntimeError("PROVIDER_DENIED_"+str(response.status_code))
  if response.status_code!=200:raise RuntimeError("HTTP_"+str(response.status_code))
  return response.json()
 finally:time.sleep(2.1)
def main():
 store()
 try:
  for coin in COINS:
   obj={"training":None,"holdout":None,"decision":"UNRESOLVED"}
   RPT["coins"][coin]=obj
   history={}
   for label,start_iso,end_iso in WINDOWS:
    start,end=millis(start_iso),millis(end_iso)
    rows=fetch(coin,label,start,end)
    obj[label.lower()]=analyse(rows,start,end)
    history[label],_ = funding_rows(rows,start,end)
    store()
   if all(obj[k] and obj[k]["complete"] for k in ["train","holdout"]):
    obj["sign_transition_evaluation"]=markov_assessment(
      history["TRAIN"],history["HOLDOUT"],millis(WINDOWS[0][1]),millis(WINDOWS[1][1]))
    obj["decision"]="COMPLETE_FUNDING_ONLY_NO_HEDGED_PNL"
   else:obj["decision"]="INCOMPLETE_FUNDING_TIME_SERIES"
   store()
  RPT["status"]="FUNDING_PANELS_COMPLETE" if all(
   x["decision"]=="COMPLETE_FUNDING_ONLY_NO_HEDGED_PNL" for x in RPT["coins"].values()) else "PARTIAL"
 except Exception as exc:
  RPT["status"]="UNRESOLVED_PROVIDER_OR_SCHEMA"
  RPT["error_kind"]=str(exc)[:85] if "PROVIDER_DENIED" in str(exc) else type(exc).__name__
 store()
 print(json.dumps({"status":RPT["status"],"http_requests":RPT["requests"],
    "result":{k:{"decision":v.get("decision"),
          "holdout_week_funding_pct":v.get("sign_transition_evaluation",{}).get("funding_short_perp_holdout_percent_notional"),
          "markov_vs_baseline":v.get("sign_transition_evaluation",{}).get("markov_holdout_logloss")}
         for k,v in RPT["coins"].items()},"error":RPT.get("error_kind"),
       "keyless":True,"trades":0},sort_keys=True))
 return 0 if RPT["status"]=="FUNDING_PANELS_COMPLETE" else 2
if __name__=="__main__":sys.exit(main())
