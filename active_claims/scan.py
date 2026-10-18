"""Stage 1: start with ACTIVE Morpho Blue debt, not with popular vault shares.
Which high-borrow markets accept collateral convertible atomically to the loan asset?
Public read-only, chain-pinned. No liquidation, signing, funds or profit claim.
"""
import datetime,decimal,hashlib,json,re,time,traceback,urllib.error,urllib.parse,urllib.request
from pathlib import Path
OUT=Path("debt_claim_evidence");OUT.mkdir(exist_ok=True)
CHAINS=(8453,1)
LOANS={8453:{"USDC":"0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
             "WETH":"0x4200000000000000000000000000000000000006"},
       1:{"USDC":"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
          "WETH":"0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
          "DAI":"0x6b175474e89094c44da98b954eedeac495271d0f",
          "USDT":"0xdac17f958d2ee523a2206206994597c13d831ec7"}}
RPC={8453:"https://mainnet.base.org",1:"https://rpc-eth.blockmachine.io"}
ALLOWED={"eth_chainId","eth_getBlockByNumber","eth_call","eth_getCode"}
START=time.monotonic();REQUESTS=0;CAP=290;DENIED=set();CACHE={}
def save(name,d):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,indent=2,sort_keys=True,default=str)+"\n")
def raw(name,url,payload,chain=None):
    global REQUESTS
    host=urllib.parse.urlsplit(url).netloc
    if host not in {"api.morpho.org","mainnet.base.org","rpc-eth.blockmachine.io"}:raise ValueError("Unapproved host")
    if host in DENIED:raise RuntimeError("STOP provider access/rate denial")
    if REQUESTS>=CAP or time.monotonic()-START>1000:raise RuntimeError("Research request/time budget")
    key=json.dumps([url,payload],sort_keys=True)
    if key in CACHE:return CACHE[key]
    if REQUESTS:time.sleep(0.6)
    REQUESTS+=1;buf=b'';metadata={"request":REQUESTS,"name":name,"chain":chain,"host":host}
    try:
        req=urllib.request.Request(url,data=json.dumps(payload).encode(),
            headers={"Accept":"application/json","Content-Type":"application/json","User-Agent":"QT-Stage1-public-claim-cash/1"})
        with urllib.request.urlopen(req,timeout=24) as response:
            buf=response.read(2_400_001);metadata["http_status"]=response.status
        if len(buf)>2_400_000:raise ValueError("Response cap")
        obj=json.loads(buf)
        if isinstance(obj,dict) and obj.get("errors"):raise RuntimeError("GraphQL error "+str(obj["errors"])[:300])
        if isinstance(obj,dict) and obj.get("error"):
            e=obj["error"];metadata["rpc_error"]=e
            if any(k in str(e).lower() for k in ("rate limit","unauthorized","access denied","client adjustable limit")):DENIED.add(host)
            raise RuntimeError("RPC "+str(e)[:180])
        CACHE[key]=obj;metadata["status"]="OK"
        save("responses/"+str(REQUESTS).zfill(4)+".json",obj)
        return obj
    except urllib.error.HTTPError as exc:
        buf=exc.read(80000);metadata.update(error=str(exc),http_status=exc.code)
        if exc.code in (401,403,429):DENIED.add(host)
        raise
    except Exception as exc:metadata.update(error=repr(exc));raise
    finally:
        metadata.update(sha256=hashlib.sha256(buf).hexdigest(),bytes=len(buf))
        save("requests/"+str(REQUESTS).zfill(4)+".json",metadata)
def rpc(chain,name,method,params):
    if method not in ALLOWED:raise ValueError("Read-only methods only")
    obj=raw(name,RPC[chain],{"jsonrpc":"2.0","id":REQUESTS+1,"method":method,"params":params},chain)
    if "result" not in obj:raise ValueError("No RPC result")
    return obj["result"]
def pad(n):return format(int(n),"064x")
def address(word):
    if not isinstance(word,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",word):raise ValueError("Not a complete address return")
    if int(word[2:26],16):raise ValueError("Address high bits nonzero")
    return "0x"+word[-40:].lower()
def scalar(word):
    if not isinstance(word,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",word):raise ValueError("Bad uint ABI")
    return int(word,16)
def call(chain,name,to,data,block):
    return rpc(chain,name,"eth_call",[{"to":to,"data":data},hex(block)])
def markets(chain):
    query="""query { markets(first: 700, orderBy: BorrowAssetsUsd, orderDirection: Desc,
       where: {chainId_in: [%d]}) { items {
         marketId lltv chain { id }
         loanAsset {address decimals symbol}
         collateralAsset {address decimals symbol}
         state {borrowAssetsUsd collateralAssetsUsd}
       } } }"""%chain
    j=raw("largest_active_markets_"+str(chain),"https://api.morpho.org/graphql",{"query":query},chain)
    return j["data"]["markets"]["items"]
def select(items,chain):
    selected=[];count={}
    seen=set()
    for market in items:
        loan=str((market.get("loanAsset") or {}).get("address","")).lower()
        coll=str((market.get("collateralAsset") or {}).get("address","")).lower()
        if not re.fullmatch(r"0x[0-9a-f]{40}",coll):continue
        wanted=next((symbol for symbol,t in LOANS[chain].items() if t==loan),None)
        if wanted is None or (wanted,coll) in seen or coll==loan:continue
        if count.get(wanted,0)>=24:continue
        amt=(market.get("state") or {}).get("borrowAssetsUsd")
        try:
            if decimal.Decimal(str(amt))<=0:continue
        except Exception:continue
        seen.add((wanted,coll));count[wanted]=count.get(wanted,0)+1
        selected.append(dict(chain=chain,market_id=market.get("marketId"),loan=loan,loan_symbol=wanted,
           collateral=coll,collateral_symbol=(market.get("collateralAsset") or {}).get("symbol"),
           api_borrow_usd=str(amt),api_collateral_usd=(market.get("state") or {}).get("collateralAssetsUsd"),
           lltv=str(market.get("lltv"))))
    return selected
def probe(chain,market,block):
    out=dict(market,block=block,classification="UNAVAILABLE",profit_verified=False,
        eligibility_verified=False,redeem_success_verified=False)
    try:
        token=market["collateral"]
        code=rpc(chain,"collateral_code","eth_getCode",[token,hex(block)])
        if not isinstance(code,str) or len(code)<=2:raise ValueError("No collateral contract code")
        try:
            underlying=address(call(chain,"collateral_asset",token,"0x38d52e0f",block))
        except Exception as e:
            out["classification"]="NO_ERC4626_ASSET_VIEW";out["asset_view_error"]=str(e)[:200];return out
        out["underlying_asset_onchain"]=underlying
        if underlying!=market["loan"]:
            out["classification"]="VAULT_UNDERLYING_DIFFERS_FROM_DEBT";return out
        try:
            decimals=scalar(call(chain,"collateral_decimals",token,"0x313ce567",block))
            if decimals<1 or decimals>24:raise ValueError("Unreasonable decimals")
            one=10**decimals
            preview=scalar(call(chain,"one_share_preview_redeem",token,"0x4cdad506"+pad(one),block))
            if not preview:raise ValueError("zero cash preview")
            out.update(classification="SAME_TOKEN_PREVIEW_ROUTE",share_decimals=decimals,
                one_share_redeems_loan_raw=str(preview),
                requires_real_eligible_borrower_and_liquidation=True)
        except Exception as e:out.update(classification="SAME_ASSET_PREVIEW_FAILED",preview_error=repr(e))
    except Exception as e:out["error"]=repr(e)
    return out
def main():
    report={"goal":"Find real high-borrow Morpho collateral shares redeemable into the debt token",
        "research_only":True,"profit_or_liquidation_executed":False,
        "sample_rule":"Top 700 markets by current borrow USD on each chain; first 24 positive-borrow markets per supported loan token with distinct collateral, selected BEFORE ERC4626 compatibility checks",
        "exclusions":["Gated vault shares, delayed queues, non-ERC4626 vaults, no same-token underlying, no unhealthy borrower or insufficient cash remain unresolved",
          "API borrow USD and ERC4626 previews are not same-time inclusion proof",
          "All opportunities would need canonical liquidation eligibility, actual callback-redeem, full loan repayment and competitive net cash test"],
        "chains":{},"results":[],"errors":[],"finished":False}
    save("REPORT.json",report)
    try:
        for chain in CHAINS:
            if int(rpc(chain,"chain_identity","eth_chainId",[]),16)!=chain:raise ValueError("wrong chain")
            header=rpc(chain,"pin_state","eth_getBlockByNumber",["latest",False])
            block=int(header["number"],16)
            data=markets(chain);sel=select(data,chain)
            report["chains"][str(chain)]={
               "block":block,"hash":header["hash"],"ranked_market_rows":len(data),
               "selected_credit_collateral_pairs":len(sel),"selection":sel,"complete":False}
            save("REPORT.json",report)
            for market in sel:
                result=probe(chain,market,block)
                report["results"].append(result)
                save("REPORT.json",report)
                if urllib.parse.urlsplit(RPC[chain]).netloc in DENIED:raise RuntimeError("STOP provider denial")
            canonical=rpc(chain,"recheck_hash","eth_getBlockByNumber",[header["number"],False])
            if canonical["hash"]!=header["hash"]:raise ValueError("block hash changed")
            report["chains"][str(chain)]["complete"]=True;save("REPORT.json",report)
        report["finished"]=True
    except Exception as e:report["errors"].append(repr(e));report["traceback"]=traceback.format_exc()
    report["requests"]=REQUESTS;report["denied_hosts"]=sorted(DENIED)
    report["same_asset_preview_count"]=sum(x["classification"]=="SAME_TOKEN_PREVIEW_ROUTE" for x in report["results"])
    save("REPORT.json",report)
    print(json.dumps({"finished":report["finished"],"requests":REQUESTS,
       "selected_markets":sum(x["selected_credit_collateral_pairs"] for x in report["chains"].values()),
       "same_asset_preview_count":report["same_asset_preview_count"],
       "errors":report["errors"]},indent=2),flush=True)
    if not report["finished"]:raise SystemExit("Incomplete: retained all errors; do not classify unavailable as no profit")
if __name__=="__main__":main()
