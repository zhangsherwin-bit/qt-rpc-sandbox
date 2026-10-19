"""QT Stage1 prediction-market complete-set finite order-book test, 2026-10-19.
Read-only: public Gamma markets and paired CLOB YES/NO orderbook; no order placing.
No geographic access, execution, FOK simultaneity or settlement guarantee.
"""
import json, hashlib, time, urllib.request, urllib.parse, urllib.error, sys
from decimal import Decimal, InvalidOperation, ROUND_UP
from pathlib import Path
from datetime import datetime, timezone
OUT=Path("pm_complete_set_evidence");OUT.mkdir(exist_ok=True)
API="https://gamma-api.polymarket.com/markets"
CLOB="https://clob.polymarket.com/book"
MAX_MARKETS=20
PER_COHORT=10
SIZES=[Decimal(10),Decimal(50),Decimal(100),Decimal(500)]
FEE_RATE=Decimal("0.07") # conservative maximum July-2026 category-specific 0.00-0.07
GAS_RESERVE=Decimal("1.0") # fixed screening buffer USDC, not measured gas
request_count=0;blocked=set()
RPT={"utc":datetime.now(timezone.utc).isoformat(),
 "hypothesis":"buy YES and NO of same binary conditional claim for less than 1 USDC combined, redeem or merge complete set",
 "fee_reference":"https://help.polymarket.com/en/articles/13364478-trading-fees (2026-07-10): fee in USDC per matched share = rate*p*(1-p)",
 "contracts_accounting":"same-condition binary YES/NO, orderbook asks at depth, 7% upper rate taker fees plus USDC 1 planning gas reserve",
 "research_design":{"discovery":"10 highest volume and 10 highest liquidity active public standard yes-no non-negative-risk markets, ranking independent of same-book outcomes",
  "cohort_limit":MAX_MARKETS,"sizes_shares":[str(x) for x in SIZES],"no_post_orders":True,
  "no_gateway_bypass":True,"no_retries_403_429":True,"no_correlation_or_portfolio_PNL_from_non_atomic_quotes":True},
 "cohort":[],"rows":[],"requests":[],"errors":[],"complete":False,
 "trades_made":0,"stage2_live_ready":False}
def save(): (OUT/"REPORT.json").write_text(json.dumps(RPT,indent=2,sort_keys=True)+"\n")
def qdec(x):
 try:return Decimal(str(x))
 except (InvalidOperation,ValueError):raise ValueError("nondecimal numeric field")
def get(url):
 global request_count
 host=urllib.parse.urlsplit(url).netloc
 if host in blocked:raise RuntimeError("host stopped after prior denial: "+host)
 if request_count>=68:raise RuntimeError("fixed 68 GET cap")
 request_count+=1
 label=f"{request_count:03d}"
 raw=b"";status=-1
 try:
  time.sleep(.26)
  req=urllib.request.Request(url,headers={"User-Agent":"QT-Research-ReadOnly/1","Accept":"application/json"},method="GET")
  with urllib.request.urlopen(req,timeout=20) as o:
   status=o.status;raw=o.read(14000000)
 except urllib.error.HTTPError as e:status=e.code;raw=e.read(120000)
 finally:
  (OUT/"raw").mkdir(exist_ok=True)
  (OUT/"raw"/(label+".request")).write_text("GET "+url+"\n")
  (OUT/"raw"/(label+".response")).write_bytes(raw)
  rec={"id":label,"url":url,"status":status,
       "response_sha256":hashlib.sha256(raw).hexdigest(),
       "size_bytes":len(raw)}
  RPT["requests"].append(rec);save()
 if status in (401,403,429):blocked.add(host);raise RuntimeError("denied HTTP "+str(status)+" at "+host)
 if status!=200:raise RuntimeError("HTTP "+str(status)+" at "+host)
 return json.loads(raw)
def unpack_arr(x):
 if isinstance(x,list):return x
 if isinstance(x,str):
  try:
   y=json.loads(x)
   if isinstance(y,list):return y
  except ValueError:pass
 return []
def market_id(m):
 t=unpack_arr(m.get("clobTokenIds"))
 names=[str(i).strip().lower() for i in unpack_arr(m.get("outcomes"))]
 if len(t)!=2 or len(names)!=2 or set(names)!={"yes","no"}:return None
 if any(not str(v).isdigit() for v in t):return None
 if m.get("closed") is True or m.get("active") is False: return None
 if m.get("negRisk") is True or m.get("enableOrderBook") is False: return None
 if m.get("acceptingOrders") is False:return None
 tokens={names[i]:str(t[i]) for i in range(2)}
 if tokens["yes"]==tokens["no"]:return None
 return tokens
def select():
 markets={}
 for sort in ["volumeNum","liquidityNum"]:
  qs=urllib.parse.urlencode({"closed":"false","active":"true","limit":100,"order":sort,"ascending":"false"})
  data=get(API+"?"+qs)
  if not isinstance(data,list):raise ValueError("Gamma markets response not array")
  parsed=[]
  for m in data:
   t=market_id(m)
   if t is None:continue
   try:vol=qdec(m.get("volumeNum","0"));liq=qdec(m.get("liquidityNum","0"))
   except Exception:continue
   if liq<1000 or vol<1000:continue
   parsed.append({"id":str(m.get("id")),"conditionId":str(m.get("conditionId")),
      "question":str(m.get("question",""))[:200],"slug":str(m.get("slug",""))[:200],
      "volume_usd_reported":str(vol),"liquidity_usd_reported":str(liq),
      "yes_token_id":t["yes"],"no_token_id":t["no"],"cohort_rank":sort,
      "negRisk":m.get("negRisk"),"endDate":str(m.get("endDate",""))})
  parsed.sort(key=lambda r:(-qdec(r["volume_usd_reported"] if sort=="volumeNum" else r["liquidity_usd_reported"]),r["id"]))
  for r in parsed[:PER_COHORT]:
   if r["id"] not in markets:
    markets[r["id"]]=r
  RPT["research_design"][sort+"_eligible_from_top100"]=len(parsed)
 RPT["cohort"]=list(markets.values())[:MAX_MARKETS]
 save()
def offers(book):
 asks=book.get("asks")
 if not isinstance(asks,list):raise ValueError("no asks array")
 out=[]
 for v in asks:
  p=qdec(v["price"]);size=qdec(v["size"])
  if not (Decimal("0")<p<Decimal("1")) or size<0: raise ValueError("invalid price or size")
  if size>0:out.append((p,size))
 return sorted(out,key=lambda x:x[0])
def fill(levels,quantity):
 remain=quantity;cost=Decimal(0);fee=Decimal(0);used=[]
 for p,qty in levels:
  take=min(remain,qty)
  if take<=0:continue
  cost+=take*p
  fee+=FEE_RATE*take*p*(1-p)
  used.append([str(p),str(take)])
  remain-=take
  if remain<=0:break
 if remain>0:return None
 # Taker fee rounds to 5 decimal places on matches. Conservative upward per individual level.
 fee=fee.quantize(Decimal("0.00001"),rounding=ROUND_UP)
 return {"cost":cost,"fee":fee,"levels":used}
def snapshot_ms(b):
 s=str(b.get("timestamp",""))
 if not s.isdigit():return None
 t=int(s)
 if t>10**15:t=t/1000000
 elif t>10**12:t=t/1000
 return float(t)
def evaluate(r):
 row={"id":r["id"],"conditionId":r["conditionId"],"question":r["question"],"cohort_rank":r["cohort_rank"],
      "status":"UNRESOLVED","same_contract":False,"size_checks":[]}
 RPT["rows"].append(row)
 try:
  yes=get(CLOB+"?"+urllib.parse.urlencode({"token_id":r["yes_token_id"]}))
  no=get(CLOB+"?"+urllib.parse.urlencode({"token_id":r["no_token_id"]}))
  if str(yes.get("asset_id"))!=r["yes_token_id"] or str(no.get("asset_id"))!=r["no_token_id"]:
   raise ValueError("book asset id mismatch")
  cond0=str(yes.get("market","")).lower()
  if cond0!=str(no.get("market","")).lower() or cond0!=r["conditionId"].lower():
   raise ValueError("book condition IDs do not align")
  if bool(yes.get("neg_risk"))!=bool(no.get("neg_risk")):
   raise ValueError("neg_risk book mismatch")
  ay=offers(yes);an=offers(no)
  row["book"]={"yes_hash":yes.get("hash"),"no_hash":no.get("hash"),
     "yes_timestamp":yes.get("timestamp"),"no_timestamp":no.get("timestamp"),
     "best_yes_ask":str(ay[0][0]) if ay else None,"best_no_ask":str(an[0][0]) if an else None,
     "best_combined_asks":str(ay[0][0]+an[0][0]) if ay and an else None,
     "yes_total_ask_shares":str(sum((x[1] for x in ay),Decimal(0))),
     "no_total_ask_shares":str(sum((x[1] for x in an),Decimal(0)))}
  yms=snapshot_ms(yes);nms=snapshot_ms(no)
  row["book"]["time_skew_seconds"]=round(abs(yms-nms),3) if yms is not None and nms is not None else None
  row["same_contract"]=True
  for size in SIZES:
   v={"shares":str(size)}
   fyes=fill(ay,size);fno=fill(an,size)
   if fyes is None or fno is None:
    v["status"]="INSUFFICIENT_ORDERBOOK_DEPTH"
   else:
    gross=size-fyes["cost"]-fno["cost"]
    fee=fyes["fee"]+fno["fee"]
    after=gross-fee-GAS_RESERVE
    v.update({"status":"QUOTED","cash_paid_yes_USDC":str(fyes["cost"]),
      "cash_paid_no_USDC":str(fno["cost"]),"gross_complete_set_USDC":str(gross),
      "worst_category_fee_7pct_USDC":str(fee),
      "planning_reserve_USDC":str(GAS_RESERVE),
      "screen_after_fee_reserve_USDC":str(after),
      "yes_levels":fyes["levels"],"no_levels":fno["levels"],
      "cash_result_is_nonatomic_unfilled_orderbooks":True})
   row["size_checks"].append(v)
  row["status"]="BOOKS_MATCHED"
 except Exception as e:
  row["status"]="UNRESOLVED";row["error"]=str(e)[:260]
 save()
def main():
 save()
 try:select()
 except Exception as e:RPT["errors"].append({"phase":"GAMMA","error":str(e)});save();sys.exit(2)
 for r in RPT["cohort"]:
  evaluate(r)
  if "clob.polymarket.com" in blocked:break
 RPT["request_count"]=request_count
 RPT["stopped_hosts"]=sorted(blocked)
 RPT["complete"]=len(RPT["rows"])==len(RPT["cohort"]) and all(x["status"]=="BOOKS_MATCHED" for x in RPT["rows"])
 good=[(row,check) for row in RPT["rows"] for check in row["size_checks"] if check["status"]=="QUOTED"]
 positives=[(row,check) for row,check in good if qdec(check["screen_after_fee_reserve_USDC"])>0]
 RPT["summary"]={"selected":len(RPT["cohort"]),"paired_books":len([x for x in RPT["rows"] if x["status"]=="BOOKS_MATCHED"]),
  "finite_depth_quoted_sizes":len(good),"conservative_screen_positive_count":len(positives),
  "gross_positive_count":len([1 for _,s in good if qdec(s["gross_complete_set_USDC"])>0]),
  "best_conservative_screen_USDC":str(max((qdec(s["screen_after_fee_reserve_USDC"]) for _,s in good),default=Decimal(0))),
  "observation_only_not_trading_pnl":True}
 save()
 print(json.dumps({"complete":RPT["complete"],"summary":RPT["summary"],"errors":RPT["errors"],"requests":request_count}))
if __name__=="__main__":main()
