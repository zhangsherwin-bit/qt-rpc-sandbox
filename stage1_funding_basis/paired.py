"""QT Stage1: cost-aware WEEKLY funding/risk-warehouse proxy vs spot hedge.

Freeze October 10-17 2026 from earlier PR106 BEFORE new OHLC outcomes.
Nine public read-only API calls max (3 funding histories, 3 perp candles,
3 independent spot candles). NO trading, no keys, no RU.

The output is an UNEXECUTED close-to-close paired-instrument proxy; actual
opening/closing orderbook fill, borrow, basis, funding exact index, capital
at risk, liquidation, stablecoin/fiat exposure and transfer are not proved.
"""
from decimal import Decimal,InvalidOperation,getcontext
from datetime import datetime,timezone
from pathlib import Path
import json,hashlib,time,sys
import requests

getcontext().prec=50
ASSETS=["BTC","ETH","SOL"]
START=1791590400 # 2026-10-10 00:00:00 UTC
END=1792195200   # 2026-10-17 00:00:00 UTC (168 hours later)
HOUR=3600
N=168
MAX_CALLS=9
OUT=Path("stage1_funding_basis_evidence")
HL="https://api.hyperliquid.xyz/info"
COINBASE="https://api.exchange.coinbase.com"
FEE_GRID_BPS=[0,5,10,20,40]
REPORT={"as_of":datetime.now(timezone.utc).isoformat(),
 "type":"close-to-close same-base-quantity long spot / short perp hedge proxy",
 "selection":"exact PR106 holdout week 2026-10-10 to 2026-10-17, BTC ETH SOL, no reselecting dates",
 "data_prerequisites":"168 contiguous hourly funding and 169 contiguous hourly marks and spot closes",
 "limits":{"max_public_http_requests":MAX_CALLS,"base_assets":ASSETS,
           "fee_grid_total_roundtrip_bps_per_initial_spot_notional":FEE_GRID_BPS},
 "important":"Funding and close-to-close PnL are NOT feasible fills or actual hedged trading returns",
 "additional_risks":["spot purchase capital and separate perp margin are required",
       "perp price/liquidation risk can occur intraperiod",
       "Coinbase USD vs Hyperliquid USDC denominations are not perfectly identical",
       "spot exchange custody, market impact, borrowing and transfer costs",
       "candle close not binding bid or ask; mark/funding settlement not at same prices",
       "exit timing from price bars is not guaranteed"],
 "series":{},"status":"UNRESOLVED","requests":0,
 "blockmachine_ru":0,"trades":0,"signatures":0,
 "realized_PnL":None}
def save():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(REPORT,sort_keys=True,indent=2)+"\n")
def d(x):
 v=Decimal(str(x))
 if not v.is_finite():raise ValueError("BAD_DECIMAL")
 return v
def send(method,url,payload,label):
 if REPORT["requests"]>=MAX_CALLS:raise RuntimeError("PUBLIC_REQUEST_CAP")
 REPORT["requests"]+=1
 num=REPORT["requests"]
 OUT.mkdir(parents=True,exist_ok=True)
 if method=="POST":
  req=json.dumps(payload,separators=(",",":")).encode()
  rsp=requests.post(url,data=req,headers={"Content-Type":"application/json",
     "Accept":"application/json"},timeout=(10,28),allow_redirects=False)
  (OUT/f"{num:02}_{label}.request").write_bytes(req)
 else:
  req=url.encode()
  rsp=requests.get(url,headers={"Accept":"application/json"},timeout=(10,28),allow_redirects=False)
  (OUT/f"{num:02}_{label}.request").write_bytes(req)
 raw=rsp.content
 if len(raw)>2500000:raise RuntimeError("RESPONSE_OVERSIZED")
 (OUT/f"{num:02}_{label}.response").write_bytes(raw)
 REPORT.setdefault("original_evidence",[]).append({"label":label,"http":rsp.status_code,
      "request_sha256":hashlib.sha256(req).hexdigest(),
      "response_sha256":hashlib.sha256(raw).hexdigest()})
 save()
 time.sleep(1.35)
 if rsp.status_code in (401,403,429):raise RuntimeError("PUBLIC_ACCESS_"+str(rsp.status_code))
 if rsp.status_code!=200:raise RuntimeError("HTTP_"+str(rsp.status_code))
 try:return rsp.json()
 except Exception:raise RuntimeError("NON_JSON_PUBLIC_DATA")
def one_asset(asset):
 k={"state":"UNRESOLVED"};REPORT["series"][asset]=k;save()
 funding=send("POST",HL,{"type":"fundingHistory","coin":asset,
    "startTime":START*1000,"endTime":END*1000},asset+"_funding")
 marks=send("POST",HL,{"type":"candleSnapshot","req":{"coin":asset,"interval":"1h",
    "startTime":START*1000,"endTime":(END+HOUR)*1000}},asset+"_perpOHLC")
 from urllib.parse import urlencode
 q=urlencode({"start":datetime.fromtimestamp(START,timezone.utc).isoformat().replace("+00:00","Z"),
               "end":datetime.fromtimestamp(END+HOUR,timezone.utc).isoformat().replace("+00:00","Z"),
               "granularity":3600})
 spot=send("GET",f"{COINBASE}/products/{asset}-USD/candles?{q}",None,asset+"_spotOHLC")
 if not isinstance(funding,list) or not isinstance(marks,list) or not isinstance(spot,list):
  raise ValueError("EXPECTED_ARRAY_RESPONSE")
 def time_to_hour(ms):return int(ms)//1000//HOUR
 r_f={time_to_hour(x["time"]):d(x["fundingRate"]) for x in funding}
 r_p={time_to_hour(x["t"]):d(x["c"]) for x in marks}
 r_s={int(row[0])//HOUR:d(row[4]) for row in spot if isinstance(row,list) and len(row)>=5}
 start=START//HOUR;stop=END//HOUR
 required=set(range(start,stop))
 if len(required)!=N:raise ValueError("BAD_FROZEN_WINDOW")
 gaps={kind:sorted(set(range(start,stop+add)) - set(o))[:8]
       for kind,o,add in (("funding",r_f,0),("perp_closes",r_p,1),("spot_closes",r_s,1))}
 k["source_rows"]={"funding":len(funding),"perp_candles":len(marks),"spot_candles":len(spot)}
 k["gaps"]=gaps
 if any(gaps.values()):k["state"]="INCOMPLETE_SOURCE_TIME_COVERAGE";save();return
 spot0,spot1=r_s[start],r_s[stop]
 perp0,perp1=r_p[start],r_p[stop]
 # Unit exposure: long one spot token, short one futures token, delta approx zero.
 spot_delta=spot1-spot0
 short_delta=perp0-perp1
 funding_cash=sum((r_f[h]*r_p[h] for h in range(start,stop)),Decimal(0))
 gross=spot_delta+short_delta+funding_cash
 # Fees grid is pure sensitivity, NOT an observed exchange fee schedule.
 sensitivities={str(bp):str(gross-(Decimal(bp)/Decimal(10000)*spot0)) for bp in FEE_GRID_BPS}
 k.update({"state":"COMPLETE_UNEXECUTED_PROXY",
  "spot_entry_close_USD":str(spot0),"spot_exit_close_USD":str(spot1),
  "perp_entry_close_USDC":str(perp0),"perp_exit_close_USDC":str(perp1),
  "per_base_unit_spot_price_change_USD":str(spot_delta),
  "per_base_unit_short_perp_price_change_USDC":str(short_delta),
  "per_base_unit_funding_income_USDC_proxy":str(funding_cash),
  "cumulative_rate_percent_if_constant_notional":str(sum((r_f[h] for h in range(start,stop)),Decimal(0))*100),
  "per_base_unit_hedged_gross_proxy_before_cost_USD_assuming_USDC_parity":str(gross),
  "gross_proxy_bps_initial_spot_notional":str(gross/spot0*10000),
  "net_proxy_by_total_roundtrip_cost_bps":sensitivities,
  "net_zero_if_cost_bps_above":str(gross/spot0*10000),
  "estimate_limitations":"mid-ish exchange closes, no executable prices or liquidation path"})
 save()
def main():
 save()
 for asset in ASSETS:
  try:one_asset(asset)
  except Exception as e:
   REPORT["series"].setdefault(asset,{})["state"]="DATA_UNAVAILABLE"
   REPORT["series"][asset]["failure_kind"]=str(e)[:72] if str(e).startswith("PUBLIC_ACCESS_") else type(e).__name__
   if str(e).startswith("PUBLIC_ACCESS_"):break
  save()
 REPORT["status"]="COMPLETE_BASIS_AWARE_CLOSE_PROXY" if len(REPORT["series"])==len(ASSETS) and all(v["state"]=="COMPLETE_UNEXECUTED_PROXY" for v in REPORT["series"].values()) else "INCOMPLETE_BASIS_DATA"
 save()
 print(json.dumps({"status":REPORT["status"],"requests":REPORT["requests"],
    "asset_results":{a:{"state":s["state"],
     "funding_pct":s.get("cumulative_rate_percent_if_constant_notional"),
     "basis_aware_gross_bps":s.get("gross_proxy_bps_initial_spot_notional"),
     "missing":s.get("gaps"),"error":s.get("failure_kind")} for a,s in REPORT["series"].items()},
    "blockmachine_ru":0,"trades":0},sort_keys=True))
 return 0 if REPORT["status"]=="COMPLETE_BASIS_AWARE_CLOSE_PROXY" else 2
if __name__=="__main__":sys.exit(main())