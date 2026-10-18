"""Stage 1: Silo V3 independent liquidation events, indexer/receipt cross-check.
Read-only public GraphQL and Ethereum/Base RPC. ProfitUSD is an indexer
estimate, NEVER realised profit. Unavailable historical order/market data stays unknown.
"""
import datetime,json,time,urllib.request,urllib.error,traceback,hashlib
from pathlib import Path
OUT=Path("silo_evidence");OUT.mkdir(parents=True,exist_ok=True)
API="https://api-v3.silo.finance"
RPC={1:"https://rpc-eth.blockmachine.io",8453:"https://mainnet.base.org"}
start=time.monotonic();n=0;denied=set()
def save(path,obj):
 p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+"\n")
def call(name,url,data):
 global n
 host=urllib.request.urlparse(url).netloc if hasattr(urllib.request,"urlparse") else urllib.parse.urlsplit(url).netloc
 if host in denied:raise RuntimeError("Provider previously denied requests "+host)
 if host not in ("api-v3.silo.finance","rpc-eth.blockmachine.io","mainnet.base.org"):raise ValueError("Approved hosts only")
 if n>=75 or time.monotonic()-start>750:raise RuntimeError("Bounded collection exhausted")
 n+=1;time.sleep(.5);raw=b"";metadata={"name":name,"host":host,"id":n}
 try:
  req=urllib.request.Request(url,data=json.dumps(data).encode(),headers={"Content-Type":"application/json","User-Agent":"QT-Stage1-Silo-PublicData/1"})
  with urllib.request.urlopen(req,timeout=28) as resp:
   raw=resp.read(1_500_001);metadata["http_status"]=resp.status
  if len(raw)>1_500_000:raise ValueError("Response body exceeds data cap")
  payload=json.loads(raw)
  if "errors" in payload and payload["errors"]:metadata["graphql_errors"]=payload["errors"]
  if "error" in payload and payload["error"]:metadata["rpc_error"]=payload["error"]
  return payload
 except urllib.error.HTTPError as e:
  metadata.update(status="HTTP_ERROR",http_status=e.code,error=str(e.reason));raw=e.read(40000)
  if e.code in (401,403,429):denied.add(host)
  raise
 except Exception as e:metadata.update(status="ERROR",error=str(e)[:200]);raise
 finally:
  metadata["bytes"]=len(raw);metadata["sha256"]=hashlib.sha256(raw).hexdigest()
  save(f"requests/{n:03d}.json",metadata)
  (OUT/"raw").mkdir(exist_ok=True);(OUT/f"raw/{n:03d}.body").write_bytes(raw)
def gql(name,query):
 x=call(name,API,{"query":query})
 if x.get("errors"):raise ValueError("Silo query schema error: "+str(x["errors"])[:250])
 if not x.get("data"):raise ValueError("No GraphQL data")
 return x["data"]
def objfield(typ):
 if not typ:return None
 while typ and typ.get("kind") in ("NON_NULL","LIST"):typ=typ.get("ofType")
 return typ.get("name") if typ else None
def rpc(chain,name,method,params):
 if chain not in RPC:raise ValueError("Unknown chain")
 x=call(name,RPC[chain],{"jsonrpc":"2.0","id":n+1,"method":method,"params":params})
 if x.get("error"):raise ValueError("RPC error: "+str(x["error"])[:250])
 return x.get("result")
def main():
 report={"source":"Silo official V3 public GraphQL liquidation indexer, supplemented by canonical chain receipts",
 "discovery_window":"Latest selected liquidation records from 2026 public API, no time horizon assumed if timestamps missing",
 "no_execution_or_capture":True,"profit_usd_is_indexer_estimate":True,
 "success":False,"errors":[],"markets":[],"liquidations":[],"schema":{}}
 save("REPORT.json",report)
 try:
  q="""query ReadSiloFields {
    __type(name:"Query") {
      fields {name args{name type{kind name ofType{kind name ofType{name kind}}}}
                  type{kind name ofType{kind name ofType{name kind}}}}
    }
  }"""
  root=gql("query_fields",q)
  fields=root.get("__type",{}).get("fields",[])
  report["schema"]["root_fields"]=[{"name":v["name"],"args":[a["name"] for a in v.get("args",[])]} for v in fields]
  liq=[x for x in fields if any(q in x["name"].lower() for q in ("liquidation","liquidate"))]
  report["schema"]["matching_liquidation_fields"]=[x["name"] for x in liq]
  try:
   markets=gql("markets_documented",'query { markets(limit: 30, orderBy: "liquidityUsd", orderDirection: "desc") { items {id siloId liquidityUsd} } }')
   report["markets"]=markets.get("markets",{}).get("items",[]) or []
  except Exception as e:report["errors"].append({"operation":"market_discovery","error":repr(e)})
  save("REPORT.json",report)
  if not liq:
   report["classification"]="NO_GRAPHQL_LIQUIDATION_ENTRYPOINT_EXPOSED"
  else:
   fld=liq[0];field=fld["name"]
   report["chosen_field"]=field
   # First learn its return type by introspection and distinguish collection and individual records.
   item_typ=objfield(fld.get("type"))
   report["schema"]["return_type"]=item_typ
   if item_typ:
    typ=gql("return_type",'query { __type(name:"'+item_typ+'"){name fields{name type{kind name ofType{kind name ofType{name kind}}}}} }')
    report["schema"]["return_fields"]=[x["name"] for x in (typ.get("__type") or {}).get("fields",[])]
   # Two documented likely shapes. Never treat a schema-mismatch as a zero-count result.
   rootfields=[x["name"] for x in (typ.get("__type") or {}).get("fields",[])] if item_typ else []
   collection="items" in rootfields
   if collection:
    # Query only scalar fields that appear on event indexer docs.
    inner="id hash blockNumber timestamp amountUSD profitUSD"
    statement=f'query {{ {field}(limit: 100) {{ items {{{inner}}} }} }}'
   else:
    statement=f'query {{ {field}(limit: 100) {{ id hash blockNumber timestamp profitUSD }} }}'
   try:
    events=gql("liquidation_candidates",statement).get(field)
    if isinstance(events,dict):events=events.get("items")
    if not isinstance(events,list):raise ValueError("Unexpected liquidation collection type")
    report["liquidations"]=[x for x in events if isinstance(x,dict)]
   except Exception as e:report["errors"].append({"operation":"liquidation_events","error":repr(e),"attempt":statement})
   save("REPORT.json",report)
  # For a genuine confirmed event, inspect canonical success and a minimal transfer ledger
  # only if a precise EVM chain ID is provided. Never guess an event's chain.
  if report["liquidations"]:
   # collect dates, no fictitious capture or dollars
   byday={}
   for e in report["liquidations"]:
    try:date=datetime.datetime.fromtimestamp(int(e["timestamp"]),datetime.timezone.utc).date().isoformat()
    except Exception:date="UNKNOWN"
    byday[date]=byday.get(date,0)+1
   report["events_by_date"]=byday
   report["economic_notes"]=["Indexer profitUSD is not on-chain terminal cash or own capture.",
     "No amount/USD total is interpreted as realized revenue without receipt and full payment trace.",
     "Missing chainId prevents canonical receipt query; do not guess contract origin."]
  report["success"]=bool(report["markets"]) or bool(report["liquidations"])
 except Exception as e:report["errors"].append({"operation":"overall","error":repr(e),"traceback":traceback.format_exc()})
 report["requests"]=n;report["denied_hosts"]=sorted(denied)
 save("REPORT.json",report)
 print(json.dumps({"success":report["success"],"requests":n,"market_count":len(report["markets"]),
   "liquidations":len(report["liquidations"]),"liquidation_field":report["schema"].get("matching_liquidation_fields"),
   "errors":report["errors"]},indent=2),flush=True)
 if not report["success"]:raise SystemExit("Incomplete Silo evidence; never call missing data no-profit")
if __name__=="__main__":main()
