"""Public, read-only Compound Comet cash-inventory discovery across 11 official markets.
Historical block samples, real AbsorbCollateral/BuyCollateral logs and finite quotes.
No signing, trades, state changes, or profits inferred from unfilled quotes.
"""
import collections,datetime as dt,json,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"stage1_followup"))
import study as S

OUT=Path("comet_evidence"); OUT.mkdir(exist_ok=True)
DEPLOYMENTS={
 1:{"usdc":"0xc3d688b66703497daa19211eedff47f25384cdc3","usds":"0x5d409e56d886231adaf00c8775665ad0f9897b56",
    "usdt":"0x3afdc9bca9213a35503b077a6072f3d0d5ab0840","wbtc":"0xe85dc543813b8c2cfeaac371517b925a166a9293",
    "weth":"0xa17581a9e3356d9a858b789d68b4d866e593ae94","wsteth":"0x3d0bb1ccab520a66e607822fc55bc921738fafe3"},
 8453:{"aero":"0x784efeb622244d2348d4f2522f8860b96fbece89","usdbc":"0x9c4ec768c28520b50860ea7a15bd7213a9ff58bf",
    "usdc":"0xb125e6687d4313864e53df431d5425969c15eb2f","usds":"0x2c776041ccfe903071af44aa147368a9c8eea518",
    "weth":"0x46e6b214b524310239732d51387075e0e70970bf"}}
# Event-selection sample frozen without seeing margins. Oct 3-9 reserved outcome dates not used.
WINDOWS={1:[(26082000,26094000),(26205000,26219000)],8453:[(52608000,52636000),(52664000,52684000)]}
BUY=S.topic("BuyCollateral(address,address,uint256,uint256)")
ABS=S.topic("AbsorbCollateral(address,address,address,uint256,uint256)")
QUOTER={1:"0x61ffe014ba17989e743c5f6cb21bf9697530b21e",8453:"0x3d4e44eb1374240ce5f1b871ab261cd16335b76a"}
def report_save(x): S.write(OUT,"REPORT.json",x)
def interpret(log):
    ts=log["topics"];data=S.words(log["data"]);sig=ts[0].lower()
    row={"tx":log["transactionHash"],"block":int(log["blockNumber"],16),
         "market":log["address"].lower(),"logIndex":int(log["logIndex"],16)}
    if sig==BUY:
        if len(ts)!=3 or len(data)!=2:raise ValueError("Unexpected BuyCollateral ABI")
        row.update(kind="buy",asset=S.address(ts[2]),buyer=S.address(ts[1]),base_amount_raw=str(data[0]),collateral_raw=str(data[1]))
    elif sig==ABS:
        if len(ts)!=4 or len(data)!=2:raise ValueError("Unexpected AbsorbCollateral ABI")
        row.update(kind="absorb",asset=S.address(ts[3]),absorber=S.address(ts[1]),borrower=S.address(ts[2]),
                   collateral_raw=str(data[0]),usd_value_raw=str(data[1]))
    else:raise ValueError("Unsupported Comet log")
    return row
def choose(events):
    # First distinct market observation, then earliest other unique state: no selection by profit.
    unique={}
    for e in sorted(events,key=lambda e:(e["block"],e["tx"],e["logIndex"])):
        unique.setdefault((e["market"],e["asset"],e["block"]),e)
    first=[];other=[];seen=set()
    for e in unique.values():
        if e["market"] not in seen:first.append(e);seen.add(e["market"])
        else:other.append(e)
    return (first+other)[:10]
def view(c,chain,addr,method,args,block,signed=False):
    return c.call(chain,addr,method,args,block,signed)
def check(c,chain,event):
    b=event["block"] if event["kind"]=="absorb" else event["block"]-1
    row={"event":event,"state_block":b,"state_type":"POST_ABSORB_BLOCK" if event["kind"]=="absorb" else "PRE_BUY_PRIOR_BLOCK",
         "exact_intrablock_state":False,"complete_cash_executions":0,"quotes":[]}
    try:
        hdr=c.rpc(chain,"state_anchor","eth_getBlockByNumber",[hex(b),False])
        row.update(hash=hdr["hash"],timestamp=int(hdr["timestamp"],16))
        market=event["market"];asset=event["asset"]
        base=S.address(view(c,chain,market,"baseToken()",[],b))
        scale=view(c,chain,market,"baseScale()",[],b)
        reserves=view(c,chain,market,"getReserves()",[],b,True)
        target=view(c,chain,market,"targetReserves()",[],b)
        paused=view(c,chain,market,"isBuyPaused()",[],b)
        inventory=view(c,chain,market,"getCollateralReserves(address)",[asset],b)
        row.update(base=base,scale=str(scale),reserve_signed=str(reserves),target=str(target),buy_paused=bool(paused),
                   available_inventory=str(inventory))
        if not inventory or reserves>=target or paused:
            row["disposition"]="NO_ACTIVE_COMET_SALE_AT_THIS_BLOCK";return row
        q1=view(c,chain,market,"quoteCollateral(address,uint256)",[asset,scale],b)
        if q1<=0:
            row["disposition"]="NO_USABLE_COLLATERAL_QUOTE";return row
        max_raw=inventory*scale//q1
        name=next((name for name,address in DEPLOYMENTS[chain].items() if address==market),None)
        cap_raw=scale*(10000 if name in ("usdc","usds","usdt","usdbc") else (2 if name=="wbtc" else 10))
        size=min(max_raw,cap_raw)
        if size<=1:row["disposition"]="INSUFFICIENT_BASE_SCALE";return row
        for quantity in sorted({max(1,size//10),max(1,size//2),max(1,size*9//10)}):
            case={"base_spend_raw":str(quantity),"dex":[]};row["quotes"].append(case)
            try:
                collateral=view(c,chain,market,"quoteCollateral(address,uint256)",[asset,quantity],b)
                case["collateral_received_raw"]=str(collateral)
                if collateral<=0 or collateral>inventory:
                    case["fits_inventory"]=False;continue
                case["fits_inventory"]=True
                for fee in (500,3000):
                    dex={"fee_tier":fee};case["dex"].append(dex)
                    try:
                        data=S.selector("quoteExactInputSingle((address,address,uint256,uint24,uint160))")
                        data+="".join(S.enc(v) for v in (asset,base,collateral,fee,0))
                        decoded=S.words(c.rpc(chain,"dex_exit_quote","eth_call",[{"to":QUOTER[chain],"data":data},hex(b)]))
                        if len(decoded)!=4:raise ValueError("Wrong UniV3 QuoterV2 ABI")
                        dex.update(out_base_raw=str(decoded[0]),gross_base_margin_raw=str(decoded[0]-quantity),
                                   positive_gross=decoded[0]>quantity,gross_only_no_fees_or_approval=True)
                    except Exception as ex:dex["error"]=repr(ex)
            except Exception as ex:case["error"]=repr(ex)
        row["disposition"]="POSITIVE_GROSS_CASH_QUOTE" if any(d.get("positive_gross") for q in row["quotes"] for d in q["dex"]) else "NO_POSITIVE_QUOTE_IN_TESTED_SIZES"
    except Exception as ex:row.update(disposition="UNRESOLVED",error=repr(ex))
    return row
def main():
    report={"purpose":"Stage 1: new external collateral-sale inventory feeding immediate cash exits",
        "scope":"Eleven official Compound Comet markets on Ethereum and Base, fixed disjoint historical windows",
        "full_cash_execution":False,"no_trades_or_signatures":True,"frozen_windows":WINDOWS,
        "selection_rule":"Earliest unique real market event per Comet, then earliest additional asset/block; at most 10 per chain; NOT selected by quote profit",
        "warnings":["Historical end-of-block and previous-block reads are NOT actual pre-transaction insertion states",
          "Gross quote is not cash closure or a profitable opportunity after gas, financing, exclusivity or auction competition",
          "Zero observations in a partial or refused scan are not a zero-frequency claim",
          "Selected market events are retrospective, not necessarily observable before the transaction"],
        "chains":{}}
    report_save(report)
    c=S.Client(OUT)
    for chain in (1,8453):
        r={"raw_event_log_count":0,"events":[],"selected":[],"quotes":[],"pages":[],"errors":[],"scope_complete":False}
        report["chains"][str(chain)]=r;report_save(report)
        try:
            assert int(c.rpc(chain,"chain_identity","eth_chainId",[]),16)==chain
            valid=[]
            for market,address in DEPLOYMENTS[chain].items():
                try:
                    code=c.rpc(chain,"known_comet_runtime","eth_getCode",[address,hex(WINDOWS[chain][0][0])])
                    if not isinstance(code,str) or len(code)<12:raise ValueError("No deployed contract code")
                    valid.append(address)
                except Exception as ex:r["errors"].append({"market":market,"runtime_error":repr(ex)})
            if not valid:raise RuntimeError("No deployed Comet markets")
            for low,high in WINDOWS[chain]:
                for left in range(low,high+1,9500):
                    right=min(high,left+9499)
                    try:
                        logs=c.rpc(chain,"comet_events","eth_getLogs",[{"address":valid,"topics":[[ABS,BUY]],
                              "fromBlock":hex(left),"toBlock":hex(right)}])
                        events=[interpret(z) for z in logs]
                        r["pages"].append({"from":left,"to":right,"n_events":len(events)})
                        r["raw_event_log_count"]+=len(logs);r["events"].extend(events)
                    except Exception as ex:
                        r["errors"].append({"range":[left,right],"error":repr(ex)});break
                    report_save(report)
                    if chain in c.denied:raise RuntimeError("Stop provider rate or access denial")
            r["selected"]=choose(r["events"])
            for e in r["selected"]:
                r["quotes"].append(check(c,chain,e));report_save(report)
                if chain in c.denied:raise RuntimeError("Provider denied; stop chain")
            expected=sum((high-low)//9500+1 for low,high in WINDOWS[chain])
            r["scope_complete"]=len(r["pages"])==expected and not r["errors"]
        except Exception as ex:r["chain_error"]=repr(ex)
        report_save(report)
    report["requests"]=c.n;report["provider_denied_chains"]=sorted(c.denied)
    report["gross_positive_cases"]=sum(x.get("disposition")=="POSITIVE_GROSS_CASH_QUOTE" for y in report["chains"].values() for x in y["quotes"])
    report["all_chains_complete"]=all(x["scope_complete"] for x in report["chains"].values())
    report_save(report)
    print(json.dumps({"requests":c.n,"positives":report["gross_positive_cases"],
       "chains":{k:{"events":v["raw_event_log_count"],"selected":len(v["selected"]),"tested":len(v["quotes"]),
       "complete":v["scope_complete"],"chain_error":v.get("chain_error"),"errors":v["errors"][:2]} for k,v in report["chains"].items()}},indent=2),flush=True)
    if not any(x["events"] for x in report["chains"].values()):
        raise SystemExit("No sale events collected in defined windows; preserve evidence as coverage failure or quiet sample")
if __name__=="__main__":main()
