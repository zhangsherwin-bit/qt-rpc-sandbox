"""Stage 1 real Yearn auction settlement event cash-flow ledger.
Twelve actual USDC-for-crvUSD kicks and same-contract settlements, 10-30 Sep 2026.
No live transaction, no assumption of beneficial ownership of remaining cash.
"""
import collections,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"stage1_followup"))
import study as S
OUT=Path("settle_evidence");OUT.mkdir(exist_ok=True)
FROM="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WANT="0xf939e0a03fb07f59a73314e73794be0e57ac1b4e"
KICK=S.topic("AuctionKicked(address,uint256)")
SETTLED=S.topic("AuctionSettled(address)")
TRANSFER=S.TRANSFER
def save(r):S.write(OUT,"REPORT.json",r)
def freeze(p):
    auctions={x["auction"].lower():x for x in json.loads((p/"AUCTIONS.json").read_text())}
    logs=json.loads((p/"ALL_LOGS.json").read_text())
    events={"kick":[],"settled":[]}
    for x in logs:
        if len(x.get("topics",[]))!=2:continue
        a=x["address"].lower();info=auctions.get(a)
        if not info or info.get("want","").lower()!=WANT or S.address(x["topics"][1])!=FROM:continue
        if x["topics"][0].lower()==KICK:events["kick"].append(x)
        if x["topics"][0].lower()==SETTLED:events["settled"].append(x)
    kicks=sorted(events["kick"],key=lambda x:int(x["blockNumber"],16))
    settles=sorted(events["settled"],key=lambda x:int(x["blockNumber"],16))
    if len(kicks)!=12 or len(settles)!=12:raise ValueError("Unexpected archived sample counts")
    rows=[]
    for i,k in enumerate(kicks):
        kb=int(k["blockNumber"],16)
        bound=int(kicks[i+1]["blockNumber"],16) if i+1<len(kicks) else 1<<63
        matches=[z for z in settles if z["address"].lower()==k["address"].lower()
                 and kb<=int(z["blockNumber"],16)<bound]
        if len(matches)!=1:raise ValueError("Nonunique historical settlement after kick")
        s=matches[0]
        rows.append({"auction":k["address"].lower(),"from":FROM,"want":WANT,
            "kick_block":kb,"settle_block":int(s["blockNumber"],16),
            "kick_tx":k["transactionHash"],"settle_tx":s["transactionHash"],
            "kick_input_usdc_raw":str(S.scalar(k["data"])),
            "age_seconds":int(s["blockTimestamp"],16)-int(k["blockTimestamp"],16)})
    return rows
def transfer(l):
    if l["topics"][0].lower()!=TRANSFER or len(l["topics"])!=3:return None
    return {"token":l["address"].lower(),"from":S.address(l["topics"][1]),
            "to":S.address(l["topics"][2]),"value":str(S.scalar(l["data"]))}
def ledger(c,row):
    try:
        receipt=c.rpc(1,"original_settled_transaction","eth_getTransactionReceipt",[row["settle_tx"]])
        if not receipt or receipt["status"]!="0x1" or int(receipt["blockNumber"],16)!=row["settle_block"]:
            raise ValueError("Canonical successful settlement receipt missing")
        assert any(l["topics"][0].lower()==SETTLED and l["address"].lower()==row["auction"] for l in receipt["logs"])
        receiver=S.address(c.call(1,row["auction"],"receiver()",[],row["settle_block"]))
        token=[transfer(l) for l in receipt["logs"] if l.get("topics") and l["address"].lower() in (FROM,WANT)
               and l["topics"][0].lower()==TRANSFER]
        token=[x for x in token if x]
        incoming=[x for x in token if x["token"]==FROM and x["from"]==row["auction"]]
        outgoing=[x for x in token if x["token"]==WANT and x["to"]==receiver]
        paid=sum(int(x["value"]) for x in outgoing)
        delivered=sum(int(x["value"]) for x in incoming)
        row.update(verified_receipt=True,buyer=receipt["from"].lower(),receiver=receiver,
            transfer_usdc_from_auction=incoming,transfer_crvusd_to_receiver=outgoing,
            usdc_delivered_raw=str(delivered),crvusd_paid_raw=str(paid),
            approximate_token_nominal_spread_usdc_raw=str(delivered-paid//10**12),
            gas_eth_wei=str(int(receipt["gasUsed"],16)*int(receipt["effectiveGasPrice"],16)),
            observed_token_cash_flow_only=True,
            no_full_profit_or_personal_capture_claim=True)
        # Disallow interpreting unassigned transfers as solely one profitable fill.
        if len(incoming)!=1 or len(outgoing)!=1:
            row["cash_flow_ambiguous"]=True
        else:
            row["cash_flow_ambiguous"]=False
    except Exception as ex:row["error"]=repr(ex)
def main():
    report={"source":"Full earlier frozen Yearn factory and event census",
      "purpose":"Third-party genuine token transfer settlement; not a net profitable independent execution",
      "no_trades_or_signing":True,"cash_profit_verified":False,
      "limitations":["USDC and crvUSD nominal value are not perfectly fungible dollar cash",
       "The buyer may be a contract interacting with multiple actions and assets",
       "Per-transaction gas is not necessarily attributable to just this auction",
       "Builder priority and direct payments, financing/inventory ownership, failure attempts unmeasured"],
      "cases":[],"errors":[]}
    save(report)
    try:
        rows=freeze(Path("input_yearn"));report["selection"]=rows;save(report)
        c=S.Client(OUT)
        assert int(c.rpc(1,"eth_chainId","eth_chainId",[]),16)==1
        for i,row in enumerate(rows):
            # Fixed 4 seconds between reads, stop on provider denial, no alternate-key fallback.
            time.sleep(4)
            ledger(c,row);report["cases"].append(row);save(report)
            if c.denied:raise RuntimeError("Provider access/rate denied")
        report["requests"]=c.n
    except Exception as ex:report["errors"].append(repr(ex));report["traceback"]=traceback.format_exc()
    report["complete"]=len(report["cases"])==12 and not report["errors"] and all(c.get("verified_receipt") for c in report["cases"])
    save(report)
    print(json.dumps({"complete":report["complete"],"cases":len(report["cases"]),
      "single_auction_receipts":sum(x.get("verified_receipt",False) for x in report["cases"]),
      "unambiguous_single_transfer":sum(x.get("cash_flow_ambiguous") is False for x in report["cases"]),
      "errors":report["errors"]},indent=2),flush=True)
    if report["errors"]:raise SystemExit("Evidence incomplete, retained partial artifact")
if __name__=="__main__":main()
