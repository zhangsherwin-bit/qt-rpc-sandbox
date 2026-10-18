"""Public-data-only negative-risk conversion screen, no betting/trading, no orders.
Uses actual contemporaneous CLOB bids and asks, never Gamma indicative prices.
Incomplete event universes are REJECTED rather than called profitable.
"""
import json,urllib.request,urllib.error,urllib.parse,time,datetime,hashlib,traceback
from decimal import Decimal,InvalidOperation
from pathlib import Path

OUT=Path("negative_risk_evidence");OUT.mkdir(exist_ok=True)
REQ=0;MAX=75;DENIED=set();T0=time.monotonic()
def dump(path,data):
    p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,indent=2,default=str)+"\n")
def request(name,url,data=None):
    global REQ
    host=urllib.parse.urlparse(url).netloc
    if host not in {"gamma-api.polymarket.com","clob.polymarket.com"}:raise ValueError("Unapproved host")
    if host in DENIED:raise RuntimeError("Provider denied "+host)
    if REQ>=MAX or time.monotonic()-T0>1050:raise RuntimeError("Research budget")
    if REQ:time.sleep(1.5)
    REQ+=1;buf=b"";note=dict(name=name,url=url,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        body=None if data is None else json.dumps(data).encode()
        req=urllib.request.Request(url,data=body,method="POST" if body is not None else "GET",
            headers={"Accept":"application/json","Content-Type":"application/json","User-Agent":"QT-Stage1-ReadOnly-PublicData"})
        with urllib.request.urlopen(req,timeout=18) as r:
            buf=r.read(3000001);note["http_status"]=r.status
        if len(buf)>3000000:raise ValueError("Response exceeds cap")
        payload=json.loads(buf);note["status"]="OK"
        dump("responses/"+str(REQ).zfill(3)+".json",payload)
        return payload
    except urllib.error.HTTPError as e:
        buf=e.read(100000);note.update(status="HTTP_ERROR",code=e.code,message=str(e.reason))
        if e.code in (401,403,429):DENIED.add(host)
        raise
    except Exception as e:note.update(status="ERROR",message=repr(e));raise
    finally:
        note["sha256"]=hashlib.sha256(buf).hexdigest()
        note["bytes"]=len(buf)
        dump("requests/"+str(REQ).zfill(3)+".json",note)
def parsed(x):
    if isinstance(x,list):return x
    if isinstance(x,str):
        try:
            a=json.loads(x)
            return a if isinstance(a,list) else []
        except Exception:return []
    return []
def tokenpair(m):
    arr=parsed(m.get("clobTokenIds"))
    return (str(arr[0]),str(arr[1])) if len(arr)==2 else None
def ladders(book,side):
    levels=book.get(side,[]) or []
    arr=[]
    for x in levels:
        try:
            p=Decimal(str(x["price"]));s=Decimal(str(x["size"]))
            if 0<p<1 and s>0:arr.append((p,s))
        except (InvalidOperation,KeyError,TypeError):continue
    return sorted(arr,key=lambda x:x[0],reverse=side=="bids")
def notional(book,side,q):
    q=Decimal(q);paid=Decimal(0);left=q
    for p,s in ladders(book,side):
        take=min(left,s);paid+=p*take;left-=take
        if left==0:return paid
    return None
def eligible(m):
    if not m.get("active") or m.get("closed"):return False
    if not m.get("enableOrderBook",True):return False
    return tokenpair(m) is not None
def event_select(e):
    # Augmented "other" and placeholder events require special completeness proofs.
    if not e.get("negRisk") or e.get("negRiskAugmented"):return False
    markets=[m for m in e.get("markets",[]) if eligible(m)]
    if not 3<=len(markets)<=12:return False
    if len(markets)!=len(e.get("markets",[])):return False
    if any(m.get("negRisk") is False for m in markets):return False
    return True
def calc(e,books):
    ms=e["markets"];rows=[]
    for i,m in enumerate(ms):
        pair=tokenpair(m)
        if not pair:continue
        no=books.get(pair[1])
        if not no:continue
        for q in (Decimal(5),Decimal(25),Decimal(100)):
            a=notional(no,"asks",q)
            if a is None:rows.append({"source":m.get("id"),"q":str(q),"status":"INSUFFICIENT_NO_ASK_DEPTH"});continue
            vals=[];missing=[]
            for j,other in enumerate(ms):
                if j==i:continue
                otherpair=tokenpair(other);yes=books.get(otherpair[0]) if otherpair else None
                amt=notional(yes,"bids",q) if yes else None
                if amt is None:missing.append(other.get("id"))
                else:vals.append(amt)
            if missing:rows.append({"source":m.get("id"),"q":str(q),"status":"MISSING_YES_BID_DEPTH","missing":missing});continue
            gross=sum(vals,Decimal(0))-a
            rows.append({"source":m.get("id"),"q":str(q),"status":"GROSS_QUOTE_ONLY","no_ask_cost":str(a),"yes_bid_cash":str(sum(vals,Decimal(0))),
                "gross_spread_before_fees":str(gross),"positive":bool(gross>0),
                "note":"Non-atomic multi-leg books, adapter permissions and fees unverified"})
    return rows
def main():
    report={"read_only":True,"no_order_placement_or_capital":True,
      "jurisdiction":"Public-data research only; US and UK cannot be presumed eligible",
      "sampling":"First six eligible, non-augmented, complete-looking multioutcome events from first twenty small active Gamma event pages; frozen BEFORE CLOB quotes",
      "caveat":"API event grouping is not a proof that every possible outcome is registered, nor a historical book or executable payout.",
      "events":[],"errors":[],"completed":False}
    dump("REPORT.json",report)
    try:
        candidates=[]
        for offset in range(0,300,15):
            url="https://gamma-api.polymarket.com/events?active=true&closed=false&limit=15&offset="+str(offset)
            items=request("gamma_page_"+str(offset),url)
            if not isinstance(items,list):raise ValueError("Unexpected Gamma schema")
            candidates.extend(x for x in items if event_select(x))
            if len(candidates)>=6:break
        unique=list({str(e["id"]):e for e in candidates}.values())[:6]
        report["selected_event_ids"]=[e["id"] for e in unique]
        dump("REPORT.json",report)
        for e in unique:
            item={"id":e["id"],"title":e.get("title"),"outcome_count":len(e["markets"]),"quote_rows":[],"complete":False}
            report["events"].append(item);dump("REPORT.json",report)
            try:
                check=request("gamma_event_"+str(e["id"]),"https://gamma-api.polymarket.com/events/"+str(e["id"]))
                if isinstance(check,list):check=check[0] if check else {}
                if not event_select(check):raise ValueError("Event no longer eligible or incomplete")
                if {m["id"] for m in e["markets"]}!={m["id"] for m in check["markets"]}:
                    raise ValueError("Event outcome inventory changed between selection and book test")
                tids=[v for m in check["markets"] for v in tokenpair(m)]
                books={}
                for i in range(0,len(tids),30):
                    part=request("clob_books_"+str(e["id"])+"_"+str(i),"https://clob.polymarket.com/books",[{"token_id":x} for x in tids[i:i+30]])
                    if not isinstance(part,list):raise ValueError("Unexpected CLOB book response")
                    for b in part:
                        if isinstance(b,dict) and str(b.get("asset_id")) in tids:books[str(b["asset_id"])]=b
                item["available_books"]=len(books)
                item["required_books"]=len(tids)
                item["quote_rows"]=calc(check,books)
                item["complete"]=len(books)==len(tids)
                item["positive_gross_quotes"]=sum(r.get("positive",False) for r in item["quote_rows"])
                item["notes"]=["All prices are public snapshots, not simultaneous guaranteed executable fills",
                  "NOT eligible for user trading where location restricted",
                  "Fees, conversion allowance, gas and capital requirements excluded"]
            except Exception as exc:item["exception"]=repr(exc)
            dump("REPORT.json",report)
            if DENIED:raise RuntimeError("Stop after provider refusal")
        report["completed"]=True
    except Exception as exc:report["exception"]=repr(exc);report["errors"].append(traceback.format_exc())
    report["requests"]=REQ;report["denied_hosts"]=sorted(DENIED)
    dump("REPORT.json",report)
    print(json.dumps({"completed":report["completed"],"events":len(report["events"]),
        "gross_positive_quotes":sum(e.get("positive_gross_quotes",0) for e in report["events"]),
        "exception":report.get("exception"),"requests":REQ},indent=2),flush=True)
    if not report["completed"]:raise SystemExit("Public-data census incomplete; partial artifact saved")
if __name__=="__main__":main()
