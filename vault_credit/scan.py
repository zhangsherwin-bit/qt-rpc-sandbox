"""Stage1 non-DEX supply of redeemable collateral: Morpho Blue borrowing markets whose
collateral is an ERC4626 USDC vault share. Public read-only API, no funds/orders/trades.
A borrow market or unhealthy-looking API position is NOT a capturable liquidation.
"""
import datetime,decimal,hashlib,json,re,time,traceback,urllib.error,urllib.parse,urllib.request
from pathlib import Path
OUT=Path("vault_collateral_evidence");OUT.mkdir(exist_ok=True)
CHAINS=(1,8453)
USDC={1:"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",8453:"0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"}
N_VAULTS=18;MAX_REQ=150;REQ=0;START=time.monotonic();BLOCKED=False
def save(name,x):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,default=str,sort_keys=True)+"\n")
def fetch(name,url,payload=None):
    global REQ,BLOCKED
    if BLOCKED:raise RuntimeError("Provider denied, stop all subsequent public API reads")
    u=urllib.parse.urlparse(url)
    if u.netloc!="api.morpho.org":raise ValueError("Only official public Morpho API")
    if REQ>=MAX_REQ or time.monotonic()-START>1050:raise RuntimeError("Fixed API request/time cap")
    if REQ:time.sleep(0.7)
    REQ+=1;raw=b"";meta=dict(name=name,url=url,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Accept":"application/json","Content-Type":"application/json","User-Agent":"QT-Stage1-read-only"})
        with urllib.request.urlopen(req,timeout=18) as r:
            raw=r.read(1_700_001);meta["http_status"]=r.status
        if len(raw)>1_700_000:raise ValueError("HTTP response length cap")
        obj=json.loads(raw)
        if isinstance(obj,dict) and obj.get("errors"):
            meta["graphql_errors"]=obj["errors"]
            raise ValueError("GraphQL schema/data error "+str(obj["errors"])[:230])
        if not isinstance(obj,dict):raise ValueError("Unexpected API data shape")
        meta["status"]="OK";save("responses/"+str(REQ).zfill(3)+".json",obj)
        return obj
    except urllib.error.HTTPError as e:
        raw=e.read(80000);meta.update(error=str(e),http_status=e.code)
        if e.code in (401,403,429):BLOCKED=True
        raise
    except Exception as e:meta["error"]=repr(e);raise
    finally:
        meta["sha256"]=hashlib.sha256(raw).hexdigest();meta["length"]=len(raw)
        save("request/"+str(REQ).zfill(3)+".json",meta)
def vaults(chain):
    q="""query { vaults(first: 120, orderBy: TotalAssetsUsd, orderDirection: Desc,
        where: { chainId_in: [%d] }) { items { address name listed asset { address decimals }
        state { totalAssetsUsd } } } }"""%chain
    j=fetch("vaults_"+str(chain),"https://api.morpho.org/graphql",{"query":q})
    return j["data"]["vaults"]["items"]
def pick_vaults(items,chain):
    out=[];seen=set()
    for x in items:
        a=str((x.get("asset") or {}).get("address","")).lower()
        vault=str(x.get("address","")).lower()
        if a!=USDC[chain] or not re.fullmatch("0x[0-9a-f]{40}",vault) or vault in seen:continue
        seen.add(vault)
        out.append({"chain":chain,"address":vault,"name":x.get("name"),"api_tvl_usd":(x.get("state") or {}).get("totalAssetsUsd")})
        if len(out)>=N_VAULTS:break
    return out
def mintoken(x):
    v=str(x or "").lower()
    if ":" in v:v=v.rsplit(":",1)[-1]
    return v
def matches_vault_market(m,chain,vault):
    return mintoken(m.get("collateral_token"))==vault.lower() and mintoken(m.get("loan_token"))==USDC[chain]
def read_markets_for_selected(chain,selected,report):
    """Documented cursor-paginated market enumeration; never classify API 400 as zero markets."""
    by_collateral={x["address"]:{"source_vault":x,"returned_market_count":None,"markets":[]} for x in selected}
    seen=set();cursor=None;scope={"pages":[],"complete_directory":False,"cursor_remaining":False,"scope":"first 4 pages of official unfiltered market directory"}
    for ix in range(4):
        args={"chain_id":chain,"limit":1000}
        if cursor:args["cursor"]=cursor
        url="https://api.morpho.org/v1/blue/markets?"+urllib.parse.urlencode(args)
        j=fetch("market_directory_"+str(chain)+"_"+str(ix),url)
        rows=j.get("data")
        if not isinstance(rows,list):raise ValueError("Official market directory did not return data list")
        scope["pages"].append({"page":ix,"n":len(rows)})
        for m in rows:
            collateral=mintoken(m.get("collateral_token"))
            if collateral not in by_collateral or not matches_vault_market(m,chain,collateral):continue
            mid=str(m.get("market_id","")).lower()
            if not re.fullmatch("0x[0-9a-f]{64}",mid) or mid in seen:continue
            seen.add(mid)
            line={"market_id":mid,"lltv_wad":str(m.get("lltv_wad")),
                  "oracle_address":m.get("oracle_address"),"creation_block":m.get("creation_block_number"),
                  "source_rest_full_market":m}
            by_collateral[collateral]["markets"].append(line)
        cursor=j.get("cursor")
        if not cursor:
            scope["complete_directory"]=True;break
        if BLOCKED:raise RuntimeError("Provider access denied")
    scope["cursor_remaining"]=bool(cursor)
    scope["matched_market_count"]=len(seen)
    for rec in by_collateral.values():
        rec["returned_market_count"]=sum(x["n"] for x in scope["pages"])
        rec["coverage_limited"]=not scope["complete_directory"]
        for line in rec["markets"]:
            try:
                mid=line["market_id"]
                state=fetch("market_state_"+mid,"https://api.morpho.org/v0/blue/markets/"+str(chain)+":"+mid+"/state")
                line["state"]=state.get("data",state)
            except Exception as exc:line["state_error"]=repr(exc)
        save("REPORT.json",report)
    return list(by_collateral.values()),scope

def positions_probe(chain,selected_markets):
    market_ids=[m["market_id"] for m in selected_markets][:8]
    if not market_ids:return dict(markets_requested=[],note="no USDC-borrow market with selected share collateral")
    ids=",".join('"'+s+'"' for s in market_ids)
    q="""query { marketPositions(first: 100, where: { marketUniqueKey_in: [%s],
        chainId_in: [%d] }) { items {
        market { marketId } user { address }
        state { borrowAssetsUsd collateralUsd borrowAssets collateral }
      } } }"""%(ids,chain)
    try:
        got=fetch("position_first_page_"+str(chain),"https://api.morpho.org/graphql",{"query":q})
        items=got["data"]["marketPositions"]["items"]
        diag=[]
        for x in items:
            try:
                a=decimal.Decimal(str((x.get("state") or {}).get("borrowAssetsUsd")))
                b=decimal.Decimal(str((x.get("state") or {}).get("collateralUsd")))
                mid=x.get("market",{}).get("marketId")
                cfg=next((c for c in selected_markets if c["market_id"]==mid),None)
                lltv=decimal.Decimal(str(cfg["lltv_wad"]))/decimal.Decimal(10)**18 if cfg else decimal.Decimal(0)
                if a>0 and b>0 and lltv>0 and a>=b*lltv:
                    diag.append({"market_id":mid,"user":x["user"]["address"],"borrow_usd_api":str(a),"collateral_usd_api":str(b),
                        "approx_lltv":str(lltv),"must_verify_with_onchain_price_and_state":True})
            except Exception:continue
        return {"markets_requested":market_ids,"api_position_rows":len(items),"approx_unhealthy":diag,
            "snapshot_is_not_atomic_eligibility_proof":True,"positions_page_truncated_possible":True}
    except Exception as e:return {"markets_requested":market_ids,"error":repr(e),"unavailable_not_zero":True}
def main():
    rep={"scope":"New Morpho Blue USDC borrow inventory with vault-share collateral across Ethereum/Base",
         "read_only":True,"liquidation_or_cash_profit_proven":False,
         "selection":"Top 18 Morpho Vault V1 USDC shares per chain, ranked by API TVL BEFORE matched credit-market queries",
         "chains":{},"vault_market_rows":[],"errors":[],"complete":False}
    save("REPORT.json",rep)
    try:
        for ch in CHAINS:
            items=vaults(ch);v=pick_vaults(items,ch)
            cr=dict(api_vaults_returned=len(items),selected=len(v),market_count=0,markets_with_debt_unknown=[])
            rep["chains"][str(ch)]=cr
            save("REPORT.json",rep)
            rows,scope=read_markets_for_selected(ch,v,rep)
            rep["vault_market_rows"].extend(rows)
            cr["market_count"]=sum(len(x["markets"]) for x in rows)
            cr["directory_scope"]=scope
            save("REPORT.json",rep)
            if BLOCKED:raise RuntimeError("Provider access/rate denied")
            candidates=[m for row in rep["vault_market_rows"] if row.get("source_vault",{}).get("chain")==ch for m in row.get("markets",[])]
            cr["position_probe"]=positions_probe(ch,candidates)
            save("REPORT.json",rep)
            if BLOCKED:raise RuntimeError("Provider denied")
        rep["complete"]=True
    except Exception as e:rep["errors"].append(repr(e));rep["traceback"]=traceback.format_exc()
    rep["api_requests"]=REQ;rep["provider_denied"]=BLOCKED
    save("REPORT.json",rep)
    print(json.dumps({"complete":rep["complete"],"api_requests":REQ,"markets":sum(x.get("market_count",0) for x in rep["chains"].values()),
        "approx_unhealthy":sum(len(x.get("position_probe",{}).get("approx_unhealthy",[])) for x in rep["chains"].values()),
        "errors":rep["errors"]},indent=2),flush=True)
    if not rep["complete"]:raise SystemExit("Research incomplete; preserve partial evidence and never call unknown markets empty")
if __name__=="__main__":main()
