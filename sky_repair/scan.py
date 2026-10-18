"""Read-only, exact-window Sky keeper incentive census with historical registry fallback.
No signer, no state override, no trading. Old missing registry keys are NOT zero events.
"""
import sys,json,traceback,re,time,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"broad_stage1"))
import collect as C
START=25943261;END=26093737
C.OUT=Path('sky_evidence');C.OUT.mkdir(exist_ok=True)
CHAINLOG="0xda0ab1e0017debcd72be8599041a2aa3ba7e740f"
CLIPN=["ETH_A","ETH_B","ETH_C","WBTC_A","WBTC_B","WBTC_C","WSTETH_A","WSTETH_B","RETH_A"]
PREV=16000000
KEYS=["MCD_DOG","MCD_VAT","MCD_DAI_JOIN","MCD_DAI"]+["MCD_CLIP_"+x for x in CLIPN]
EVENTS={"Bark":"0x"+C.H("Bark(bytes32,address,uint256,uint256,uint256,address,uint256)"),
"Kick":"0x"+C.H("Kick(uint256,uint256,uint256,uint256,address,address,uint256)"),
"Redo":"0x"+C.H("Redo(uint256,uint256,uint256,uint256,address,address,uint256)")}
MAX_LOG_REQUESTS=20
def abiaddr(h):
    if not isinstance(h,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",h) or int(h[2:26],16):
        raise ValueError("invalid address ABI return")
    v="0x"+h[-40:].lower()
    if not int(v,16):raise ValueError("zero contract address")
    return v
def karg(k):
    b=k.encode()
    if len(b)>32:raise ValueError("chainlog key too long")
    return b.hex().ljust(64,"0")
def checkcode(c,a):
    code=c.rpc("runtime_"+a,"eth_getCode",[a,hex(END)])
    return isinstance(code,str) and len(code)>4
def resolve(c,key):
    attempts=[]
    for block,label in [(END,"study_end"),(PREV,"historical_fallback")]:
        try:
            ret=c.view("registry_"+label+"_"+key,CHAINLOG,"getAddress(bytes32)",karg(key),hex(block))
            a=abiaddr(ret)
            attempts.append(dict(source=label,block=block,address=a))
            if checkcode(c,a):
                return dict(address=a,source=label,attempts=attempts)
            attempts[-1]["no_runtime_at_study_end"]=True
        except Exception as e:attempts.append(dict(source=label,block=block,error=str(e)[:270]))
    return dict(address=None,attempts=attempts,unresolved=True)
def typed_event(l):
    t=l["topics"][0].lower();d=l.get("data","0x")
    if t==EVENTS["Bark"].lower():
        return dict(kind="bark",tx=l["transactionHash"],block=int(l["blockNumber"],16),dog=l["address"],
            ilk=l["topics"][1],urn="0x"+l["topics"][2][-40:],auction_id=int(l["topics"][3],16),
            raw_data=d)
    if t in (EVENTS["Kick"].lower(),EVENTS["Redo"].lower()):
        words=[d[2+i:2+i+64] for i in range(0,len(d)-2,64)]
        if len(words)!=4 or len(l["topics"])!=4:raise ValueError("unexpected Kick/Redo event ABI")
        return dict(kind="kick" if t==EVENTS["Kick"].lower() else "redo",
            tx=l["transactionHash"],block=int(l["blockNumber"],16),clip=l["address"],
            auction_id=int(l["topics"][1],16),
            keeper="0x"+l["topics"][3][-40:],
            paid_internal_dai_rad=str(int(words[3],16)),
            paid_dai_wei_floor=str(int(words[3],16)//10**27),
            paid_dai_units=str(int(words[3],16)/10**45))
    return None
def main():
    r={"scope":"Sky historical contract census 2026-09-10 to 2026-10-01 UTC exclusive",
      "research_only":True,"production_mutation":False,"no_profit_claim":True,
      "old_registry_fallback_not_live_permission":True,
      "registry":{},"configs":{},"pagination":[],"events":[],"selected":[],"finished":False,"errors":[]}
    C.save("SKY_REPORT.json",r);c=C.Client()
    try:
        for key in KEYS:
            r["registry"][key]=resolve(c,key);C.save("SKY_REPORT.json",r)
            if c.blocked:raise RuntimeError("STOP provider denial")
        dog=r["registry"]["MCD_DOG"]["address"]
        clips={r["registry"]["MCD_CLIP_"+k]["address"]:k for k in CLIPN if r["registry"]["MCD_CLIP_"+k]["address"]}
        contracts=([dog] if dog else [])+list(clips)
        contracts=list(dict.fromkeys(contracts))
        r["contract_scope"]=contracts
        if not contracts:
            r["errors"].append("No verified deployed Dog/Clipper addresses from current or historical registry")
            raise RuntimeError("No archive-verified contracts for event scan")
        for a in contracts:
            sigs=["live()","Hole()"] if a==dog else ["tip()","chip()","stopped()","count()"]
            values={}
            for sig in sigs:
                try:values[sig]=c.view("config_"+sig,a,sig,block=hex(END))
                except Exception as e:values[sig]={"unavailable":str(e)[:230]}
            r["configs"][a]=values;C.save("SKY_REPORT.json",r)
        topics=[[EVENTS[x] for x in EVENTS]]
        # Addresses are contract-code verified; 10k max provider window; 70 sec per log call.
        for lo in range(START,END+1,10000):
            hi=min(END,lo+9999)
            rows=c.rpc("sky_events_"+str(lo),"eth_getLogs",[{
                 "address":contracts,"topics":topics,
                 "fromBlock":hex(lo),"toBlock":hex(hi)}])
            C.save("page_"+str(lo)+".json",rows)
            events=[typed_event(x) for x in rows]
            r["events"].extend(x for x in events if x)
            r["pagination"].append({"from":lo,"through":hi,"log_count":len(rows),
                "total_reward_events":sum(e.get("kind") in ("kick","redo") for e in events if e)})
            C.save("SKY_REPORT.json",r)
            if c.blocked:raise RuntimeError("STOP provider denial")
        assert r["pagination"][0]["from"]==START and r["pagination"][-1]["through"]==END
        # Observed caller reward denomination is rad internal DAI, not cash at wallet.
        rw=sorted({e["tx"]:e for e in r["events"] if e["kind"] in ("kick","redo")}.values(),
            key=lambda e:(e["block"],e["tx"]))
        r["counts"]={"bark":sum(e["kind"]=="bark" for e in r["events"]),
          "kick":sum(e["kind"]=="kick" for e in r["events"]),
          "redo":sum(e["kind"]=="redo" for e in r["events"]),
          "unique_reward_transactions":len(rw)}
        for e in ([rw[0],rw[len(rw)//2],rw[-1]] if rw else []):
            if e["tx"] in {x["tx"] for x in r["selected"]}:continue
            item=dict(e)
            try:
                receipt=c.rpc("reward_receipt","eth_getTransactionReceipt",[e["tx"]])
                assert receipt and receipt["status"]=="0x1"
                item["gas_wei"]=str(int(receipt["gasUsed"],16)*int(receipt["effectiveGasPrice"],16))
                item["sender"]=receipt.get("from")
                C.save("receipts/"+e["tx"]+".json",receipt)
            except Exception as exc:item["error"]=str(exc)[:270]
            r["selected"].append(item);C.save("SKY_REPORT.json",r)
        r["finished"]=True
    except Exception as exc:r["exception"]=repr(exc);r["traceback"]=traceback.format_exc()
    r["requests"]=c.n;r["blocked_hosts"]=sorted(c.blocked)
    C.save("SKY_REPORT.json",r)
    print(json.dumps({"requests":r["requests"],"finished":r["finished"],
      "counts":r.get("counts"),"registry_found":{k:v.get("source") for k,v in r["registry"].items() if v.get("address")},
      "exception":r.get("exception")},indent=2),flush=True)
    if not r["finished"]:raise SystemExit("Historical census incomplete; evidence preserved, not a zero-income result")
if __name__=="__main__":main()
