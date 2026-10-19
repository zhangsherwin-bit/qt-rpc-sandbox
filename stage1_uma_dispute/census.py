"""QT Stage 1: UMA OOv3 disputer capital-at-risk income, independent of DeFi arbitrage.
Official UMA public Goldsky subgraphs, predeclared networks and cohorts.
Only public GraphQL POST queries, never trade, dispute, wallet, RPC or Blockmachine RU.
"""
import json,hashlib,time,sys
from datetime import datetime,timezone
from pathlib import Path
from collections import Counter,defaultdict
from urllib.parse import urlsplit
import requests

OUT=Path("uma_oov3_evidence");OUT.mkdir(exist_ok=True)
PREFIX="https://api.goldsky.com/api/public/project_clus2fndawbcc01w31192938i/subgraphs/"
CHAINS={
 "ethereum":PREFIX+"mainnet-optimistic-oracle-v3/latest/gn",
 "polygon":PREFIX+"polygon-optimistic-oracle-v3/1/gn",
 "arbitrum":PREFIX+"arbitrum-optimistic-oracle-v3/1/gn",
 "base":PREFIX+"base-optimistic-oracle-v3/latest/gn",
}
ROWS_PER_QUERY=120
COHORTS=[
 {"name":"latest","where":None},
 {"name":"2026_Q1","where":{"assertionTimestamp_gte":"1767225600","assertionTimestamp_lt":"1775001600"}},
 {"name":"2026_Q3","where":{"assertionTimestamp_gte":"1782864000","assertionTimestamp_lt":"1790812800"}},
]
MAX_POSTS=12
RPT={
 "run_utc":datetime.now(timezone.utc).isoformat(),
 "mechanism":"challenge false optimistic-oracle assertions in exchange for bond, capital at risk",
 "original_hypothesis":"Economic incentive comes from correctness and opponent error, not swap prices",
 "predeclared":{
   "official_subgraphs":CHAINS,"cohorts":COHORTS,
   "max_rows_per_cohort_network":ROWS_PER_QUERY,
   "max_post_queries":MAX_POSTS,
   "winner_net_currency_raw":"reported settlementPayout - original bond for winner==disputer",
   "capital_locked":"disputer must post full bond first; non-flash-financeable",
   "no_token_parity_assumption":True,
   "no_partial_claim_of_recurrence_from_top120":True,
 },
 "network_results":{},"http_requests":[],"errors":[],
 "complete":False,"no_trading":True,"no_blockmachine_ru":True,
 "stage2_ready":False
}
def save():(OUT/"REPORT.json").write_text(json.dumps(RPT,sort_keys=True,indent=2)+"\n")
def query_for(cohort):
 where=cohort["where"]
 clauses=",".join(k+':"'+v+'"' for k,v in (where or {}).items())
 arg=(",where:{"+clauses+"}") if clauses else ""
 return """query Stage1OOv3 {
 _meta { block { number } }
 assertions(first:120,orderBy:assertionBlockNumber,orderDirection:desc%s) {
 id assertionId assertionTimestamp assertionBlockNumber expirationTime
 currency bond asserter disputer escalationManager
 settlementPayout settlementRecipient settlementResolution
 disputeTimestamp settlementTimestamp
 }
 }""" %arg
def http_post(url,query,chain,cohort):
 if len(RPT["http_requests"])>=MAX_POSTS:raise RuntimeError("hard public API GET/POST ceiling")
 n=len(RPT["http_requests"])+1;label="%02d_%s_%s"%(n,chain,cohort)
 body=json.dumps({"query":query},separators=(",",":"),sort_keys=True).encode()
 req_name=OUT/(label+".request.json");rsp_name=OUT/(label+".response")
 req_name.write_bytes(body)
 status=-1;raw=b"";headers={}
 try:
  time.sleep(.55)
  with requests.post(url,data=body,headers={"Content-Type":"application/json",
      "Accept":"application/json","User-Agent":"QT-Stage1-Research/1"},
      allow_redirects=False,timeout=(10,28),stream=True) as r:
   status=r.status_code
   total=0;parts=[]
   for part in r.iter_content(65536):
    if part:
     total+=len(part)
     if total>1_900_000:break
     parts.append(part)
   raw=b"".join(parts)
 except requests.RequestException as exc:
  headers={"transport_error":type(exc).__name__}
 rsp_name.write_bytes(raw)
 rec={"chain":chain,"cohort":cohort,"http_status":status,
  "request_sha256":hashlib.sha256(body).hexdigest(),
  "response_sha256":hashlib.sha256(raw).hexdigest(),
  "bytes":len(raw),
  "no_bearer_header":True}
 rec.update(headers)
 RPT["http_requests"].append(rec);save()
 if status in (401,403,429):
  raise RuntimeError("provider_denial_%d"%status)
 if status!=200:raise RuntimeError("http_not_ok_%d"%status)
 data=json.loads(raw)
 if "errors" in data:raise RuntimeError("graphql_errors_present")
 core=data.get("data",{})
 if not isinstance(core,dict) or not isinstance(core.get("assertions"),list):
  raise RuntimeError("invalid_assertion_schema")
 if len(core["assertions"])>ROWS_PER_QUERY:
  raise RuntimeError("provider_breached_declared_page_cap")
 return core

def parse_assertion(d):
 out={}
 if not isinstance(d,dict):raise ValueError("non-object Assertion")
 for k in ("id","assertionId","asserter","disputer","currency","settlementRecipient",
           "escalationManager"):
  v=d.get(k)
  out[k]=str(v).lower() if v is not None else None
 if not out["id"] or not out["currency"] or not out["asserter"]:
  raise ValueError("mandatory identity missing")
 for k in ("bond","settlementPayout","assertionTimestamp",
           "disputeTimestamp","settlementTimestamp","assertionBlockNumber"):
  v=d.get(k)
  out[k]=None if v is None else int(v)
  if v is not None and out[k]<0:raise ValueError("negative unsigned quantity")
 out["settlementResolution"]=d.get("settlementResolution")
 out["settlement_winner"]="UNRESOLVED"
 out["dispute_realized_raw"]=None
 if out["disputer"] is None:
  out["settlement_winner"]="UNOPPOSED" if out["settlementTimestamp"] is not None else "PENDING_UNOPPOSED"
 elif out["settlementTimestamp"] is None or out["settlementRecipient"] is None or out["settlementPayout"] is None:
  out["settlement_winner"]="DISPUTED_NOT_SETTLED"
 elif out["settlementRecipient"]==out["disputer"]:
  out["settlement_winner"]="DISPUTER"
  # Bond was deposited and locked for resolution.
  out["dispute_realized_raw"]=out["settlementPayout"]-out["bond"]
 elif out["settlementRecipient"]==out["asserter"]:
  out["settlement_winner"]="ASSERTER"
  # Losing disputer forfeits its posted bond.
  out["dispute_realized_raw"]=-out["bond"]
 else:
  out["settlement_winner"]="UNRECOGNIZED_RECIPIENT"
 return out

def main():
 save()
 seen={}
 counts={}
 provider_denied=False
 for chain,url in CHAINS.items():
  result={"chain":chain,"cohorts":[],"observations":[],"state":"UNRESOLVED"}
  RPT["network_results"][chain]=result
  for cohort in COHORTS:
   entry={"cohort":cohort["name"],"status":"UNRESOLVED"}
   result["cohorts"].append(entry)
   try:
    payload=http_post(url,query_for(cohort),chain,cohort["name"])
    rows=[parse_assertion(d) for d in payload["assertions"]]
    entry.update({"status":"OK","rows":len(rows),
                  "subgraph_head":payload.get("_meta",{}).get("block",{}).get("number"),
                  "full_page_potential_truncation":len(rows)==ROWS_PER_QUERY})
    for row in rows:
     key=chain+"::"+row["id"]
     if key not in seen:
      seen[key]=row
      result["observations"].append(row)
   except Exception as exc:
    entry["status"]="UNRESOLVED";entry["error_kind"]=str(exc)[:90]
    RPT["errors"].append({"chain":chain,"cohort":cohort["name"],
                          "reason":entry["error_kind"]})
    if "provider_denial" in str(exc):
     provider_denied=True
     break
   save()
  result["state"]="ALL_COHORTS_OK" if len(result["cohorts"])==len(COHORTS) and all(x["status"]=="OK" for x in result["cohorts"]) else "UNRESOLVED"
  seen_result=result["observations"]
  winner_counts=Counter(x["settlement_winner"] for x in seen_result)
  currencies=Counter(x["currency"] for x in seen_result)
  winner_events=[x for x in seen_result if x["settlement_winner"]=="DISPUTER"]
  realized_by_currency=defaultdict(int)
  for a in winner_events:
   realized_by_currency[a["currency"]]+=a["dispute_realized_raw"]
  result["summary"]={
   "distinct_assertions_sampled":len(seen_result),
   "sample_only_not_full_chain_census":True,
   "winner_counts":dict(winner_counts),
   "distinct_disputer_accounts":len(set(x["disputer"] for x in seen_result if x["disputer"])),
   "settled_disputer_wins_sample":len(winner_events),
   "winner_positive_gross_raw_count":sum(x["dispute_realized_raw"]>0 for x in winner_events),
   "positive_gross_by_unpriced_currency_raw":dict(realized_by_currency),
   "currencies_sampled":dict(currencies),
   "gross_values_not_net_return_and_not_your_pnl":True,
   "future_capture_rate_not_measured":True}
  save()
  if provider_denied:
   # All four chains share the same public GraphQL service; a first 429
   # is a provider-wide stop, not grounds for trying three more endpoints.
   break
 if provider_denied:
  RPT["shared_provider_denial_stop"]=True
  RPT["unqueried_networks"]=[n for n in CHAINS if n not in RPT["network_results"]]
 RPT["complete"]=len(RPT["network_results"])==len(CHAINS) and all(
  v["state"]=="ALL_COHORTS_OK" for v in RPT["network_results"].values())
 RPT["summary"]={
  "network_cohorts_complete":sum(x["status"]=="OK" for v in RPT["network_results"].values() for x in v["cohorts"]),
  "cohorts_expected":len(CHAINS)*len(COHORTS),
  "sampled_distinct_assertions":sum(v["summary"]["distinct_assertions_sampled"] for v in RPT["network_results"].values()),
  "sampled_settled_disputer_wins":sum(v["summary"]["settled_disputer_wins_sample"] for v in RPT["network_results"].values()),
  "qualified_statement":"Not annual recurrence, nor expected outsider profit, nor same-currency net USDC without decimals and verified payout"
 }
 save()
 print(json.dumps({"complete":RPT["complete"],"summary":RPT["summary"],
  "errors":RPT["errors"],"zero_blockmachine_ru":True},sort_keys=True))
 return 0 if RPT["complete"] else 2
if __name__=="__main__":sys.exit(main())
