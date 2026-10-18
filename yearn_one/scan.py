"""Read-only Yearn single-sided auction → stablecoin cash price study.
Fixed archive-origin sample of all USDC-for-crvUSD kicks in Sept 10–30 2026.
This is NOT a transaction, trade, external cash settlement or inclusion proof.
"""
import json,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"stage1_followup"))
import study as S
OUT=Path("yearn_evidence");OUT.mkdir(exist_ok=True)
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
CRVUSD="0xf939e0a03fb07f59a73314e73794be0e57ac1b4e"
QUOTER="0x61ffe014ba17989e743c5f6cb21bf9697530b21e"
KICK=S.topic("AuctionKicked(address,uint256)")
def save(d):S.write(OUT,"REPORT.json",d)
def freeze(path):
    a={x["auction"].lower():x for x in json.loads((path/"AUCTIONS.json").read_text())}
    logs=json.loads((path/"ALL_LOGS.json").read_text())
    out=[]
    for l in logs:
        if not l.get("topics") or l["topics"][0].lower()!=KICK:continue
        meta=a.get(l["address"].lower())
        if not meta or meta.get("want","").lower()!=CRVUSD:continue
        if len(l["topics"])!=2 or S.address(l["topics"][1])!=USDC:continue
        out.append({"auction":l["address"].lower(),"want":CRVUSD,"from":USDC,
            "kick_block":int(l["blockNumber"],16),"kick_timestamp":int(l["blockTimestamp"],16),
            "kick_amount_raw":str(S.scalar(l["data"])),"version":meta.get("version"),
            "kick_tx":l["transactionHash"]})
    return sorted(out,key=lambda z:(z["kick_block"],z["kick_tx"]))
def evaluate(c,kick):
    b=kick["kick_block"];auction=kick["auction"];row=dict(kick);row["sampled_states"]=[]
    # 1 immediately after kick block, and at 1h/4h after in canonical real block states.
    for offset in (1,300,1200):
        block=b+offset
        case={"offset_blocks":offset,"block":block,"complete_cash_executions":0,"alternatives":[]}
        row["sampled_states"].append(case)
        try:
            h=c.rpc(1,"historical_block","eth_getBlockByNumber",[hex(block),False])
            if not h:raise ValueError("Missing canonical block")
            case["block_hash"]=h["hash"];case["timestamp"]=int(h["timestamp"],16)
            avail=c.call(1,auction,"available(address)",[USDC],block)
            case["available_usdc_raw"]=str(avail)
            if avail<=0:
                case["status"]="NOT_ACTIVE_OR_NO_USDC";continue
            quantity=min(avail,2500*10**6)
            for fraction in (25,75):
                amount=max(1,quantity*fraction//100)
                item={"fraction_percent":fraction,"input_usdc_raw":str(amount),"uni_quotes":[]}
                case["alternatives"].append(item)
                try:
                    needed=c.call(1,auction,"getAmountNeeded(address,uint256)",[USDC,amount],block)
                    item["want_crvusd_required_raw"]=str(needed)
                    if needed<=0:continue
                    for fee in (500,3000):
                        q={"fee":fee};item["uni_quotes"].append(q)
                        try:
                            data=S.selector("quoteExactInputSingle((address,address,uint256,uint24,uint160))")
                            data+="".join(S.enc(x) for x in (USDC,CRVUSD,amount,fee,0))
                            rsp=c.rpc(1,"uniswap_v3_exit","eth_call",[{"to":QUOTER,"data":data},hex(block)])
                            vals=S.words(rsp)
                            if len(vals)!=4:raise ValueError("Uniswap QuoterV2 ABI mismatch")
                            q.update(quoted_crvusd_raw=str(vals[0]),required_crvusd_raw=str(needed),
                                gross_spread_raw=str(vals[0]-needed),gross_positive=vals[0]>needed,
                                not_executable_or_captured_proof=True)
                        except Exception as e:q["quote_error"]=repr(e)
                except Exception as e:item["error"]=repr(e)
            case["status"]="QUOTED_OR_PARTIAL"
        except Exception as e:case["error"]=repr(e)
    return row
def main():
    report={"scope":"Frozen Sep10–30 Yearn AuctionKicked events selling USDC for crvUSD",
      "comparison":"buy USDC from auction paying crvUSD; separately price selling exactly that USDC on UniV3",
      "selection_rule":"All observed USDC-for-crvUSD kick events in fixed census, before any profitability quotes",
      "full_execution":False,"no_signing_or_transfers":True,
      "caveats":["Public archive-origin events are selected without profitability, but not an independent prospective sample",
        "Actual take callback allowance, reentrancy protection and financing unverified",
        "Quoted exit and auction view are separate reads, not one settled EVM transaction",
        "Gross crvUSD is not USD profit, and does not include gas, MEV, conversion, timing or inclusion costs",
        "Some auction address versions may not expose the same query methods; errors are UNKNOWN"],
      "cases":[],"errors":[]};save(report)
    try:
        cases=freeze(Path("input_yearn"))
        if not cases:raise ValueError("No exact USDC-for-crvUSD observed kicks")
        report["frozen_count"]=len(cases)
        report["frozen_sha"]=S.hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest()
        save(report)
        c=S.Client(OUT)
        assert int(c.rpc(1,"verify_ethereum","eth_chainId",[]),16)==1
        for case in cases:
            report["cases"].append(evaluate(c,case));save(report)
            if c.denied:raise RuntimeError("Provider denied; stop without bypass")
        report["requests"]=c.n;report["all_cases_attempted"]=len(report["cases"])==len(cases)
    except Exception as e:report["errors"].append(repr(e));report["traceback"]=traceback.format_exc()
    report["positive_gross_state_quotes"]=sum(any(z.get("gross_positive") for s in x["sampled_states"] for alt in s["alternatives"] for z in alt["uni_quotes"]) for x in report["cases"])
    save(report)
    print(json.dumps({"frozen_kicks":report.get("frozen_count"),"tested":len(report["cases"]),
       "positive_gross_cases":report["positive_gross_state_quotes"],"errors":report["errors"]},indent=2),flush=True)
    if report["errors"]:raise SystemExit("Partial/invalid historical study; evidence preserved")
if __name__=="__main__":main()
