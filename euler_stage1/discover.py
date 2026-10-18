"""Euler Vault Kit historical liquidation cash-conversion DISCOVERY, read-only.
Select candidate debt vaults by present borrow inventory, NEVER by outcomes.
Freeze three separate historical block windows; sample each identical cohort.
No data credentials, trading, signatures or production state changes.
"""
import datetime, hashlib, json, re, time, traceback, urllib.error, urllib.parse, urllib.request
from pathlib import Path
from Crypto.Hash import keccak

OUT=Path("euler_evidence");OUT.mkdir(exist_ok=True)
RPC="https://rpc-eth.blockmachine.io"
GQL="https://api.goldsky.com/api/public/project_cm4iagnemt1wp01xn4gh1agft/subgraphs/euler-simple-mainnet/latest/gn"
BLOCKS=[(25950000,25957999),(26010000,26017999),(26080000,26087999)]
MAX_REQUESTS=95
MAX_SELECTED=6
REQUESTS=0;HEAVY=0;DENIED=False;START=time.monotonic();LAST_LOG=-1e6
def save(n,v):
 p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(v,indent=2,default=str)+"\n")
def keccak_hex(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
def addr(a):
 if not isinstance(a,str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}",a):
  raise ValueError("Not a 20-byte Ethereum address")
 return a.lower()
def decode_abi_address(raw):
 if not isinstance(raw,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",raw):
  raise ValueError("Not ABI address")
 if int(raw[2:26],16):raise ValueError("Bad padded address")
 return addr("0x"+raw[-40:])
def words(raw):
 if not isinstance(raw,str) or not raw.startswith("0x") or (len(raw)-2)%64:
  raise ValueError("Malformed ABI words")
 return [int(raw[i:i+64],16) for i in range(2,len(raw),64)]
def fetch(name,url,payload):
 global REQUESTS,DENIED,HEAVY,LAST_LOG
 if DENIED:raise RuntimeError("Provider denial, stop")
 if REQUESTS>=MAX_REQUESTS or time.monotonic()-START>2200:
  raise RuntimeError("Bounded research resource limit")
 if url not in (GQL,RPC):raise ValueError("Unexpected data host")
 if payload.get("method") not in ("eth_chainId","eth_getBlockByNumber","eth_call","eth_getCode","eth_getLogs",None):
  raise ValueError("Read-only method violation")
 if payload.get("method")=="eth_getLogs":
  time.sleep(max(0,66-(time.monotonic()-LAST_LOG)));LAST_LOG=time.monotonic();HEAVY+=1
 else:time.sleep(.75)
 REQUESTS+=1
 raw=b"";note={"name":name,"n":REQUESTS,"utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(url,data=json.dumps(payload).encode(),
       headers={"Content-Type":"application/json","User-Agent":"QT-Stage1-Euler-ReadOnly/1"})
  with urllib.request.urlopen(req,timeout=36) as r:raw=r.read(2000001);note["http_status"]=r.status
  if len(raw)>2000000:raise ValueError("Response >2MB")
  p=json.loads(raw)
  if p.get("error"):
   note["error"]=p["error"]
   if any(z in str(p["error"]).lower() for z in ("access denied","rate limit","unauthorized","client adjustable limit")):
    DENIED=True
   raise RuntimeError(str(p["error"])[:300])
  if url==GQL and p.get("errors"):
   note["graphql_errors"]=p["errors"]
   raise RuntimeError("GraphQL errors "+str(p["errors"])[:200])
  note["success"]=True
  return p["result"] if url==RPC else p["data"]
 except urllib.error.HTTPError as e:
  note["http_status"]=e.code;raw=e.read(100000)
  if e.code in (401,403,429):DENIED=True
  raise
 except Exception as e:note["exception"]=repr(e);raise
 finally:
  note["length"]=len(raw);note["sha256"]=hashlib.sha256(raw).hexdigest()
  (OUT/"raw").mkdir(exist_ok=True)
  (OUT/f"raw/{REQUESTS:03d}.body").write_bytes(raw)
  save(f"raw/{REQUESTS:03d}.json",note)
def rpc(name,method,params):
 return fetch(name,RPC,{"jsonrpc":"2.0","id":REQUESTS+1,"method":method,"params":params})
def view(name,to,signature,args=(),block="latest"):
 selector=keccak_hex(signature)[:10]
 calldata=selector+"".join(f"{int(a):064x}" for a in args)
 return rpc(name,"eth_call",[{"to":addr(to),"data":calldata},block])
def logpages(vault,lo,hi):
 if hi-lo>=10000:raise ValueError("Provider 10,000-block maximum")
 return rpc("Liquidate_"+vault+"_"+str(lo),"eth_getLogs",[
  {"address":vault,"fromBlock":hex(lo),"toBlock":hex(hi),"topics":[keccak_hex("Liquidate(address,address,address,uint256,uint256)")]}])
def go():
 rep={"study":"Euler EVK historical liquidation cohort and same-asset collateral cash redemption diagnostics",
    "read_only":True,"no_fills_or_cash_profit_tested":True,"no_signing_or_broadcast":True,
    "windows":[{"lo":lo,"hi":hi} for lo,hi in BLOCKS],
    "selection":"Deterministic first 35 sorted Euler simple-subgraph vault IDs, rank by positive present borrows among historically deployed; select max six vaults BEFORE historical events",
    "selected":[],"events":[],"errors":[],"complete":False,
    "limitations":["Subgraph coverage/late vaults may omit past accounts; this is NOT a full Euler universe",
    "Ranking by current borrow volume may bias discovery; not a prospective holdout",
    "Historical block-end view is not exact intrablock pre-liquidation state",
    "Collateral shares can have hooks, liquidity restrictions, stale oracle prices and fees",
    "Liquidation seized shares and debt are NOT spendable profit without exact actual repayment and sale",
    "Do not annualise selective event counts or infer current capture probability"]}
 save("REPORT.json",rep)
 try:
  if rpc("chain","eth_chainId",[])!="0x1":raise ValueError("Wrong chain")
  for lo,hi in BLOCKS:
   h0=rpc("header_lo","eth_getBlockByNumber",[hex(lo),False])
   h1=rpc("header_hi","eth_getBlockByNumber",[hex(hi),False])
   if int(h1["timestamp"],16)<=int(h0["timestamp"],16):raise ValueError("Nonmonotonic headers")
  query="{ vaults(first: 35, orderBy: id, orderDirection: asc) { id factory } }"
  data=fetch("vault_list",GQL,{"query":query})
  vs=data.get("vaults",[])
  if len(vs)<6:raise ValueError("Subgraph did not return 6 vaults")
  cands=[]
  for v in vs:
   a=addr(v["id"])
   try:
    code=rpc("hist_vault_code","eth_getCode",[a,hex(BLOCKS[0][0])])
    if not isinstance(code,str) or len(code)<4:continue
    res=view("latest_borrows",a,"totalBorrows()",block="latest")
    debt=int(res,16)
    cands.append({"vault":a,"current_borrow_raw":str(debt),"factory":v.get("factory"),"historically_deployed":True})
   except Exception as e:rep["errors"].append({"vault":a,"error":repr(e)})
   save("REPORT.json",rep)
   if DENIED:raise RuntimeError("Stop after provider refusal")
  cands.sort(key=lambda x:(-int(x["current_borrow_raw"]),x["vault"]))
  rep["selected"]=cands[:MAX_SELECTED];save("REPORT.json",rep)
  if len(rep["selected"])<4:raise RuntimeError("Insufficient archive-deployed vaults")
  for v in rep["selected"]:
   debtvault=v["vault"]
   try:
    base=decode_abi_address(view("debt_asset",debtvault,"asset()",block=hex(BLOCKS[0][0])))
   except Exception as e:base=None;v["asset_error"]=str(e)
   v["debt_asset"]=base
   save("REPORT.json",rep)
   for lo,hi in BLOCKS:
    events=logpages(debtvault,lo,hi)
    row={"vault":debtvault,"window":[lo,hi],"event_count":len(events),"liquidations":[]}
    rep.setdefault("segments",[]).append(row)
    for log in events:
     t=log.get("topics",[])
     w=words(log["data"])
     if len(t)!=3 or len(w)!=3:raise ValueError("EVK Liquidate ABI mismatch")
     event={"tx":log["transactionHash"],"block":int(log["blockNumber"],16),
       "liquidator":decode_abi_address(t[1]),"violator":decode_abi_address(t[2]),
       "collateral_vault":addr("0x"+format(w[0],"040x")),"debt_vault":debtvault,
       "repay_assets_raw":str(w[1]),"collateral_shares_seized_raw":str(w[2])}
     row["liquidations"].append(event);rep["events"].append(event)
     if len(rep["events"])<=12:
      try:
       col=event["collateral_vault"]
       asset=decode_abi_address(view("collateral_asset",col,"asset()",block=hex(event["block"])))
       event["collateral_underlying"]=asset
       if asset==base:
        probe=view("postblock_previewRedeem",col,"previewRedeem(uint256)",
            [int(event["collateral_shares_seized_raw"])],hex(event["block"]))
        event["postblock_same_asset_cash_preview_raw"]=str(int(probe,16))
        event["indicative_gross_raw"]=str(int(probe,16)-int(event["repay_assets_raw"]))
        event["note"]="THIS IS A POST-BLOCK PREVIEW ONLY; NOT A SUCCESSFUL LIQUIDATION AND NOT RETAINED CASH"
      except Exception as e:event["preview_error"]=repr(e)
    save("REPORT.json",rep)
    if DENIED:raise RuntimeError("Stop on denial")
  rep["complete"]=True
 except Exception as exc:rep["fatal_error"]=repr(exc);rep["traceback"]=traceback.format_exc()
 rep["request_count"]=REQUESTS;rep["heavy_log_requests"]=HEAVY;rep["provider_denied"]=DENIED
 save("REPORT.json",rep)
 print(json.dumps({"complete":rep["complete"],"selected":len(rep["selected"]),
    "liquidations":len(rep["events"]),"requests":REQUESTS,"fatal_error":rep.get("fatal_error")},indent=2),flush=True)
 if not rep["complete"]:raise SystemExit("Historical Euler window incomplete; negative profit inference forbidden")
if __name__=="__main__":go()
