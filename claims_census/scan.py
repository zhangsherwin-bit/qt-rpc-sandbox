"""Read-only dated liquidation-event census for three independently preselected cash-claim lending markets."""
import json,urllib.request,urllib.error,time,hashlib,datetime,traceback
from pathlib import Path
from Crypto.Hash import keccak
OUT=Path("claim_events_evidence");OUT.mkdir(exist_ok=True)
MORPHO="0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb"
CASES=[
{"name":"USD3_USDC_Ethereum","chain":1,"block":26220131,"market":"0xe3df58f9d3011b7481ff36b939fa5f8da642f34ea5792d25d3958dbf1efa26d7","vault":"0x056b269eb1f75477a8666ae8c7fe01b64dd55ecc","debt":"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48","url":"https://rpc-eth.blockmachine.io"},
{"name":"yoETH_WETH_Base","chain":8453,"block":52772707,"market":"0x94f344f8db8c950faa45206c269dd0c2787a86ae3a7b988423e1e6e8173ae269","vault":"0x3a43aec53490cb9fa922847385d82fe25d0e9de7","debt":"0x4200000000000000000000000000000000000006","url":"https://mainnet.base.org"},
{"name":"sUSDX_USDC_Base","chain":8453,"block":52772707,"market":"0x4c8e1349aa58fb02b17347d2e2916ae84a2930744b0a062413d7851aa73cec35","vault":"0xeb6d2c72422e17517d483097a2df29b753a5856c","debt":"0x833589fcd6edb6e08f4c7c32d4f71b54bda02913","url":"https://mainnet.base.org"}
]
def sig(s):
 k=keccak.new(digest_bits=256);k.update(s.encode());return '0x'+k.hexdigest()
EVENT=sig("Liquidate(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)")
NUM=0;DENIED=set();last={};started=time.monotonic()
def save(path,data):
 p=OUT/path;p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(data,indent=2)+"\n")
def rpc(c,method,params,name):
 global NUM
 chain=c["chain"]
 if chain in DENIED:raise RuntimeError("STOP_AFTER_PROVIDER_DENIAL")
 if NUM>=85 or time.monotonic()-started>1300:raise RuntimeError("BOUNDED_COLLECTION_LIMIT")
 if method=="eth_getLogs":time.sleep(max(0,68-(time.monotonic()-last.get(chain,-1000))));last[chain]=time.monotonic()
 else:time.sleep(0.4)
 NUM+=1;body=b"";meta={"name":name,"chain":chain,"method":method,"params":params}
 try:
  req=urllib.request.Request(c["url"],data=json.dumps({"jsonrpc":"2.0","id":NUM,"method":method,"params":params}).encode(),headers={"Content-Type":"application/json"})
  with urllib.request.urlopen(req,timeout=24) as resp:body=resp.read(2000000);meta["status"]=resp.status
  r=json.loads(body)
  if r.get("error"):
   msg=str(r["error"]);meta["error"]=r["error"]
   if any(x in msg.lower() for x in ("rate limit","access denied","client adjustable limit","unauthorized")):DENIED.add(chain)
   raise ValueError(msg)
  return r["result"]
 except urllib.error.HTTPError as exc:
  if exc.code in (401,403,429):DENIED.add(chain)
  meta["error"]="HTTP "+str(exc.code);raise
 finally:
  meta["hash"]=hashlib.sha256(body).hexdigest()
  meta["bytes"]=len(body)
  save("requests/"+str(NUM)+".json",meta)
  (OUT/"raw").mkdir(exist_ok=True);(OUT/f"raw/{NUM:03d}.body").write_bytes(body)
def decode(log):
 if log["topics"][0].lower()!=EVENT.lower() or len(log["topics"])!=4:raise ValueError("Event mismatch")
 a=[int(log["data"][i:i+64],16) for i in range(2,len(log["data"]),64)]
 if len(a)!=5:raise ValueError("Invalid liquidation data ABI")
 return {"tx":log["transactionHash"],"block":int(log["blockNumber"],16),"log":int(log["logIndex"],16),
 "market":log["topics"][1],"caller":"0x"+log["topics"][2][-40:],"borrower":"0x"+log["topics"][3][-40:],
 "repaid_assets_raw":str(a[0]),"repaid_shares_raw":str(a[1]),"seized_vault_shares_raw":str(a[2]),
 "bad_debt_assets_raw":str(a[3]),"bad_debt_shares_raw":str(a[4])}
def main():
 report={"research_only":True,"all_market_liquidation_episodes":[],"markets":[],"completed":False,
         "profit_proven":False,"selection":"Three pinned USD3/yoETH/sUSDX Morpho collateral markets, BEFORE historical outcomes",
         "scope":"Last 30,000 blocks ending at each fixed block from previous completed eligibility scan",
         "warnings":["Liquidation event and incentive are not a complete cash settlement","No failed-attempt denominator or inclusion bid data","Missing RPC pages not zero liquidations"]}
 save("REPORT.json",report)
 try:
  for c in CASES:
   row={k:v for k,v in c.items() if k!="url"};row.update(pages=[],events=[],errors=[]);report["markets"].append(row)
   if int(rpc(c,"eth_chainId",[],"chainid"),16)!=c["chain"]:raise ValueError("Wrong chain")
   h=rpc(c,"eth_getBlockByNumber",[hex(c["block"]),False],"pinned_header")
   row["canonical_block_hash"]=h["hash"]
   code=rpc(c,"eth_getCode",[MORPHO,hex(c["block"])],"core_code")
   if not code or code=="0x":raise ValueError("Missing Morpho deployment")
   lo=c["block"]-29999
   for start in range(lo,c["block"]+1,9500):
    stop=min(start+9499,c["block"])
    logs=rpc(c,"eth_getLogs",[{"address":MORPHO,"fromBlock":hex(start),"toBlock":hex(stop),
            "topics":[EVENT,c["market"]]}],"market_liquidation_page")
    es=[decode(x) for x in logs]
    row["pages"].append({"start":start,"end":stop,"events":len(es)})
    row["events"].extend(es)
    report["all_market_liquidation_episodes"].extend(dict(x,market_name=c["name"]) for x in es)
    save("REPORT.json",report)
   row["fully_paged"]=row["pages"][0]["start"]==lo and row["pages"][-1]["end"]==c["block"]
  report["completed"]=True
 except Exception as exc:
  report["exception"]=repr(exc);report["traceback"]=traceback.format_exc()
 report["requests"]=NUM;report["denied"]=sorted(DENIED)
 save("REPORT.json",report)
 print(json.dumps({"complete":report["completed"],"markets":[{"name":x["name"],"events":len(x["events"]),"pages":len(x["pages"])} for x in report["markets"]],"error":report.get("exception")},indent=2),flush=True)
 if not report["completed"]:raise SystemExit("Incomplete historical census; not a zero-profit observation")
if __name__=="__main__":main()
