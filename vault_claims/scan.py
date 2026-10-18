"""Stage 1: ERC-4626 share claim-to-cash mispricing screen, public read-only.
Morpo Vault V1 metadata -> canonical chain state -> V3 real pool -> finite-size
exact-input quote -> previewRedeem into the SAME USDC. NO trade, approvals,
wallet, signing, state overrides, or fabricated liquidity. Preview isn't payout.
"""
import datetime,hashlib,json,os,re,time,traceback,urllib.error,urllib.parse,urllib.request
from pathlib import Path

OUT=Path("vault_scan_evidence");OUT.mkdir(exist_ok=True)
USDC={1:"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
      8453:"0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"}
RPC={1:"https://rpc-eth.blockmachine.io",8453:"https://mainnet.base.org"}
FACTORY="0x1f98431c8ad98523631ae4a59f267346ea31f984"
QUOTER={1:"0x61ffe014ba17989e743c5f6cb21bf9697530b21e",8453:"0x3d4e44eb1374240ce5f1b871ab261cd16335b76a"}
FEE_TIERS=(100,500,3000,10000)
SIZES=(500,5000,25000)
LIMIT_VAULTS_PER_CHAIN=18
RPC_BUDGET=300
CALL_COUNT=0;BAD=set();CACHE={};START=time.monotonic()
def save(name,data):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,indent=2,sort_keys=True,default=str)+"\n")
def rawread(name,url,payload=None,chain=None):
    global CALL_COUNT
    host=urllib.parse.urlsplit(url).netloc
    if host not in {"api.morpho.org","rpc-eth.blockmachine.io","mainnet.base.org"}:raise ValueError("unapproved host")
    if host in BAD:raise RuntimeError("Provider denied; stop chain/provider")
    if CALL_COUNT>=RPC_BUDGET or time.monotonic()-START>1120:raise RuntimeError("research request/time cap")
    key=json.dumps([url,payload],sort_keys=True)
    if key in CACHE:return CACHE[key]
    if CALL_COUNT:time.sleep(0.5)
    CALL_COUNT+=1;body=b"";status={"id":CALL_COUNT,"name":name,"chain":chain,"host":host}
    try:
        req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Accept":"application/json","Content-Type":"application/json","User-Agent":"QT-Stage1-readonly-claim/1"})
        with urllib.request.urlopen(req,timeout=22) as r:
            body=r.read(1_400_001);status["http_status"]=r.status
        if len(body)>1_400_000:raise ValueError("response cap exceeded")
        j=json.loads(body)
        if isinstance(j,dict) and j.get("errors"):raise ValueError("GraphQL errors "+str(j["errors"])[:280])
        if isinstance(j,dict) and j.get("error"):
            e=j["error"];status["rpc_error"]=e
            if any(z in str(e).lower() for z in ("rate limit","access denied","client adjustable limit","unauthorized")):BAD.add(host)
            raise RuntimeError(str(e)[:300])
        CACHE[key]=j;status["status"]="OK"
        save("response/"+str(CALL_COUNT).zfill(4)+".json",j)
        return j
    except urllib.error.HTTPError as e:
        body=e.read(100000);status.update(status="HTTP_ERROR",http_status=e.code,error=str(e))
        if e.code in (401,403,429):BAD.add(host)
        raise
    except Exception as e:status.update(status="ERROR",error=repr(e));raise
    finally:
        status.update(sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
        save("request/"+str(CALL_COUNT).zfill(4)+".json",status)
def rpc(chain,name,method,params):
    if method not in {"eth_chainId","eth_getBlockByNumber","eth_getCode","eth_call"}:raise ValueError("read-only methods")
    ans=rawread(name,RPC[chain],{"jsonrpc":"2.0","id":CALL_COUNT+1,"method":method,"params":params},chain)
    if "result" not in ans:raise ValueError("missing RPC result")
    return ans["result"]
def word(x):return format(int(x),"064x")
def arg_addr(a):
    if not isinstance(a,str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}",a):raise ValueError("Invalid address")
    return a[2:].lower().zfill(64)
def decode_address(x):
    if not isinstance(x,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",x):raise ValueError("Bad address ABI")
    if int(x[2:26],16):raise ValueError("High bits not zero")
    return "0x"+x[-40:].lower()
def scalar(s):
    if not isinstance(s,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",s):raise ValueError("Bad uint")
    return int(s,16)
def call(chain,name,to,data,block):
    return rpc(chain,name,"eth_call",[{"to":to,"data":data},hex(block)])
def signature(name):
    # fixed verified selectors, no runtime ABI guessing
    return {"asset()":"0x38d52e0f",
            "decimals()":"0x313ce567",
            "previewRedeem(uint256)":"0x4cdad506",
            "getPool(address,address,uint24)":"0x1698ee82",
            "liquidity()":"0x1a686502",
            "quoteExactInputSingle((address,address,uint256,uint24,uint160))":"0xc6a5026a"}[name]
def gql_vaults(chain):
    query="""query { vaults(first: 120, orderBy: TotalAssetsUsd, orderDirection: Desc,
     where: {chainId_in: [%d]}) { items {
       address name symbol listed asset { address decimals }
       state { totalAssetsUsd }
    } } }"""%chain
    out=rawread("morpho_vault_list_"+str(chain),"https://api.morpho.org/graphql",{"query":query},chain)
    return out["data"]["vaults"]["items"]
def select(items,chain):
    cand=[];seen=set()
    for v in items:
        a=v.get("asset") or {}
        address=str(v.get("address","")).lower()
        if str(a.get("address","")).lower()!=USDC[chain] or not re.fullmatch("0x[0-9a-f]{40}",address):continue
        if address in seen:continue
        seen.add(address)
        cand.append({"chain":chain,"address":address,"asset":USDC[chain],
                     "name":v.get("name"),"listed":v.get("listed"),
                     "tvlUsd_api":(v.get("state") or {}).get("totalAssetsUsd")})
        if len(cand)>=LIMIT_VAULTS_PER_CHAIN:break
    return cand
def quoter(chain,token,amount,fee,block):
    data=(signature("quoteExactInputSingle((address,address,uint256,uint24,uint160))")
          +arg_addr(USDC[chain])+arg_addr(token)+word(amount)+word(fee)+word(0))
    out=call(chain,"quoter_"+str(fee)+"_"+str(amount),QUOTER[chain],data,block)
    if not isinstance(out,str) or not re.fullmatch(r"0x(?:[0-9a-fA-F]{64}){4}",out):
        raise ValueError("QuoterV2 expects exactly four ABI words")
    return [int(out[2+i:2+i+64],16) for i in (0,64,128,192)]
def scan_vault(chain,v,block):
    record=dict(v,block=block,state="UNRESOLVED",pools=[],quotes=[],positive_indicative_count=0)
    address=v["address"]
    try:
        if rpc(chain,"vault_code","eth_getCode",[address,hex(block)]) in ("0x",None):raise ValueError("Not deployed at pinned state")
        asset=decode_address(call(chain,"vault_underlying",address,signature("asset()"),block))
        if asset!=USDC[chain]:raise ValueError("Underlying mismatch; do not value in USDC")
        decimals=scalar(call(chain,"vault_share_decimals",address,signature("decimals()"),block))
        if not 0<decimals<=24:raise ValueError("Unreasonable vault decimals")
        record.update(verified_asset=asset,share_decimals=decimals)
        one_share=10**decimals
        nav=scalar(call(chain,"vault_preview_one_share",address,signature("previewRedeem(uint256)")+word(one_share),block))
        record["preview_one_share_usdc_raw"]=str(nav)
        if nav==0:raise ValueError("zero preview redemption")
        for fee in FEE_TIERS:
            row={"fee":fee}
            record["pools"].append(row)
            try:
                data=signature("getPool(address,address,uint24)")+arg_addr(USDC[chain])+arg_addr(address)+word(fee)
                pool=decode_address(call(chain,"factory_get_pool",FACTORY,data,block))
                row["pool"]=pool
                if int(pool,16)==0:
                    row["status"]="NO_POOL";continue
                liq=scalar(call(chain,"pool_liquidity",pool,signature("liquidity()"),block))
                row["liquidity_raw"]=str(liq)
                if liq==0:row["status"]="EMPTY_POOL";continue
                row["status"]="POOL_PRESENT"
                for size in SIZES:
                    quote={"fee":fee,"spend_usdc_raw":size*10**6,
                      "claim_cash_settled":False,"spent_input_amount_verified":False,
                      "source":"UniswapV3 quote + ERC4626 previewRedeem, same block",
                      "network_financing_inclusion_costs_unmeasured":True}
                    record["quotes"].append(quote)
                    try:
                        amountOut,priceAfter,ticks,gas=quoter(chain,address,size*10**6,fee,block)
                        quote.update(shares_out_raw=str(amountOut),post_sqrt_price=str(priceAfter),
                              ticks_crossed=ticks,uniswap_quote_gas_estimate=gas)
                        if amountOut==0:raise ValueError("zero shares")
                        cash=scalar(call(chain,"redeem_preview",address,signature("previewRedeem(uint256)")+word(amountOut),block))
                        diff=cash-size*10**6
                        quote.update(redeem_preview_usdc_raw=str(cash),gross_indicative_usdc_raw=str(diff),
                              positive_indicative=diff>0,needs_atomic_validation=True)
                        if diff>0:record["positive_indicative_count"]+=1
                    except Exception as e:quote["error"]=repr(e)
            except Exception as e:row["error"]=repr(e)
        record["state"]="SCREEN_COMPLETE"
    except Exception as e:record["state"]="UNAVAILABLE";record["error"]=repr(e)
    return record
def main():
    report={"research":"Stage1 vault-share claim conversion discovery",
      "no_signed_or_sent_trades":True,"quote_is_not_profit":True,
      "conditions":["Actual Uniswap pool inventory, exact same-state swap, ERC4626 redeem, no transfer gates, gas and winning inclusion price required before declaring profit",
        "Uniswap Quoter exact-input partial consumption near price limits may not be identifiable",
        "PreviewRedeem does not guarantee instant vault redemption or account permissions",
        "GraphQL listed vault universe is ranking-biased, not all vaults"],
      "selection_rule":"Morpho vaults V1 ranked by API TVL, first 18 USDC-asset entries on each of Ethereum and Base; selection before quotations",
      "selected":[],"chains":{},"results":[],"errors":[],"finished":False}
    save("REPORT.json",report)
    try:
        for chain in (1,8453):
            if int(rpc(chain,"network_identity","eth_chainId",[]),16)!=chain:raise ValueError("wrong chain")
            header=rpc(chain,"pin_header","eth_getBlockByNumber",["latest",False])
            report["chains"][str(chain)]={"block":int(header["number"],16),"hash":header["hash"],"timestamp":int(header["timestamp"],16)}
            items=gql_vaults(chain);records=select(items,chain)
            report["chains"][str(chain)]["gql_rows"]=len(items)
            report["chains"][str(chain)]["selected"]=len(records)
            report["selected"].extend(records)
            save("REPORT.json",report)
            if "api.morpho.org" in BAD:raise RuntimeError("API denied")
            for v in records:
                item=scan_vault(chain,v,report["chains"][str(chain)]["block"])
                report["results"].append(item)
                save("REPORT.json",report)
                if RPC[chain].split("://")[1] in BAD:raise RuntimeError("chain provider denied")
            check=rpc(chain,"recheck_header","eth_getBlockByNumber",[header["number"],False])
            if check["hash"]!=header["hash"]:raise ValueError("Pinned block hash changed")
            report["chains"][str(chain)]["hash_rechecked"]=True
        report["finished"]=True
    except Exception as e:report["errors"].append(repr(e));report["traceback"]=traceback.format_exc()
    report["request_count"]=CALL_COUNT;report["denied_hosts"]=sorted(BAD)
    report["positive_indicative_quotes"]=sum(v["positive_indicative_count"] for v in report["results"])
    report["screened_vaults"]=len(report["results"])
    save("REPORT.json",report)
    print(json.dumps({"finished":report["finished"],"screened_vaults":report["screened_vaults"],
      "positive_indicative_quotes":report["positive_indicative_quotes"],
      "nonzero_pool_count":sum(p.get("status")=="POOL_PRESENT" for r in report["results"] for p in r["pools"]),
      "requests":CALL_COUNT,"errors":report["errors"]},indent=2),flush=True)
    if not report["finished"]:raise SystemExit("Unfinished: evidence retained and missing states not labelled zero profit")
if __name__=="__main__":main()
