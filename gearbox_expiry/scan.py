"""QT Stage 1: first bounded empirical census for Gearbox *expiration* liquidations.
Nine official historical V3 facades; NOT the entire 2026 Gearbox deployment universe.
READ ONLY. Every amount of cash income remains unproven until full settlement.
"""
import json,time,hashlib,sys,traceback,urllib.request,urllib.error
from pathlib import Path
from Crypto.Hash import keccak
RPC="https://rpc-eth.blockmachine.io"
OUT=Path("gearbox_expiry_evidence"); OUT.mkdir(exist_ok=True)
FACADES=[
"0x958cBC4AEA076640b5D9019c61e7F78F4F682c0C",
"0x5366B8C2dE34f614556D085961b3699Aa1755aF4",
"0xA391c8178d7B951C148302Afb6B20bCfD3BA29B6",
"0xd032e6A87872B0b14CEE17fB7981eD11745A4426",
"0xa27f3622930661fE202423a9383e5E70Cf59C4eE",
"0x840aC757450B2a35d1645167B706c9a83de8b613",
"0x313e1ce56A0386FBf9CC356E34646591b6c31C39",
"0xBF14e9E4d0119E093E1758A6c27799192da779c8",
"0xE1836e82FfF8C179A69D940B9C950d19A50A31f9"]
ANCHOR=26225568
WINDOWS=[{"start":end-2199,"end":end} for end in
         (ANCHOR-15000,ANCHOR-65000,ANCHOR-115000)]
def h(sig, n=64):
    k=keccak.new(digest_bits=256);k.update(sig.encode())
    return "0x"+k.hexdigest()[:n]
EVENT=h("LiquidateCreditAccount(address,address,address,uint256)")
GETTERS={"expirable":h("expirable()",8),
         "expiration_date":h("expirationDate()",8),
         "version":h("version()",8)}
COUNT=0
DENIED=False
def rpc(method,params):
    global COUNT,DENIED
    if DENIED:raise RuntimeError("STOP: provider already denied")
    COUNT+=1
    label=f"{COUNT:03}"
    payload=json.dumps({"jsonrpc":"2.0","id":COUNT,"method":method,"params":params},
                       sort_keys=True).encode()
    (OUT/"requests").mkdir(exist_ok=True)
    (OUT/"raw").mkdir(exist_ok=True)
    (OUT/"requests"/f"{label}.json").write_bytes(payload)
    req=urllib.request.Request(RPC,payload,headers={"Content-Type":"application/json",
                                    "User-Agent":"QT-readonly-expiry-research/1"},method="POST")
    time.sleep(0.8)
    try:
        with urllib.request.urlopen(req,timeout=25) as resp:
            status=resp.status;body=resp.read(2_000_000)
    except urllib.error.HTTPError as e:
        status=e.code;body=e.read(2_000_000)
    except Exception as e:
        raise RuntimeError(f"transport unavailable: {type(e).__name__} {e}") from e
    (OUT/"raw"/f"{label}.body").write_bytes(body)
    (OUT/"raw"/f"{label}.sha256").write_text(hashlib.sha256(body).hexdigest()+"\n")
    if status in (401,403,429):
        DENIED=True;raise RuntimeError(f"STOP: provider denial HTTP {status}")
    if status!=200:raise RuntimeError(f"HTTP {status}")
    try:r=json.loads(body)
    except ValueError:raise RuntimeError("Invalid JSON from provider")
    if "error" in r:raise RuntimeError("JSON-RPC error: "+repr(r["error"])[:300])
    if "result" not in r:raise RuntimeError("No JSON-RPC result")
    return r["result"]
def getter(addr,selector,block):
    try:
        v=rpc("eth_call",[{"to":addr,"data":selector},hex(block)])
        if not isinstance(v,str) or len(v)<66:raise ValueError("short response")
        return int(v,16)
    except Exception as e:
        if DENIED:raise
        return {"unknown":str(e)[:200]}
def main():
    r={"family":"GEARBOX_SCHEDULED_EXPIRY_LIQUIDATION",
       "chain":"Ethereum","sample_frozen_before_outcomes":True,
       "source_registry_scope":"9 older official Gearbox V3 facades; not all 2026 facades",
       "anchor_block":ANCHOR,"facades":FACADES,"windows":WINDOWS,
       "event_topic":EVENT,"states":[],"events":[],"page_results":[],
       "complete":False,"profit_proven":False,
       "caveats":["Same event for expiration and unhealthy positions: no cause attributed",
         "Expiration date is not evidence of any borrower's outstanding debt",
         "Incomplete archive or missing getters is UNKNOWN, not zero",
         "No liquidation calldata path, flash repayment, gas, bribes or tradable final cash",
         "Independent 3 x 2200-block samples, not a continuous rate estimator"]}
    def save():
        r["requests"]=COUNT
        (OUT/"REPORT.json").write_text(json.dumps(r,indent=2)+"\n")
    save()
    try:
        if int(rpc("eth_chainId",[]),16)!=1:raise ValueError("wrong network")
        header=rpc("eth_getBlockByNumber",[hex(ANCHOR),False])
        r["anchor_hash"]=header["hash"];save()
        for addr in FACADES:
            row={"facade":addr}
            for key,selector in GETTERS.items():
                row[key]=getter(addr,selector,ANCHOR)
            r["states"].append(row);save()
        allowed={a.lower() for a in FACADES}
        for window in WINDOWS:
            logs=rpc("eth_getLogs",[{"address":FACADES,
               "fromBlock":hex(window["start"]),"toBlock":hex(window["end"]),
               "topics":[EVENT]}])
            for log in logs:
                if log["address"].lower() not in allowed or log["topics"][0].lower()!=EVENT:
                    raise ValueError("Invalid log source/topic")
                r["events"].append({"facade":log["address"],"tx":log["transactionHash"],
                   "block":int(log["blockNumber"],16),"log_index":int(log["logIndex"],16),
                   "topics":log["topics"],"data":log["data"],
                   "expiry_cause":"UNKNOWN","cash_profit":"UNPROVEN"})
            r["page_results"].append({**window,"events":len(logs)});save()
        for ev in r["events"][:3]:
            receipt=rpc("eth_getTransactionReceipt",[ev["tx"]])
            if receipt and receipt.get("status")=="0x1":
                ev["original_winner"]={"status":"SUCCESS",
                  "gas_used":int(receipt["gasUsed"],16),
                  "effective_gas_price_wei":int(receipt["effectiveGasPrice"],16),
                  "sender":receipt["from"]}
            save()
        if rpc("eth_getBlockByNumber",[hex(ANCHOR),False])["hash"]!=r["anchor_hash"]:
            raise ValueError("Anchor block hash changed")
        r["complete"]=True
    except Exception as e:
        r["error"]=str(e)[:300]
        r["traceback"]=traceback.format_exc(limit=2)
    save()
    print(json.dumps({"complete":r["complete"],"facades_tested":len(r["states"]),
           "windows_tested":len(r["page_results"]),"events":len(r["events"]),
           "requests":COUNT,"error":r.get("error")},indent=2),flush=True)
    if not r["complete"]:sys.exit(1)
if __name__=="__main__":main()
