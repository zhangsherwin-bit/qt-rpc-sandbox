"""Read-only 2026 Angle USDA wind-down discount: public Odos buy quote versus
actual fee-adjusted Transmuter USDC redemption. No trading, signatures or RFQs.
Quote-only, not a filled route nor a complete sequential EVM transaction.
"""
import urllib.request,urllib.error,json,time,hashlib,traceback,datetime
from pathlib import Path
from Crypto.Hash import keccak
OUT=Path("winddown_evidence");OUT.mkdir(exist_ok=True)
RPC="https://rpc-eth.blockmachine.io";ODOS="https://api.odos.xyz/sor/quote/v2"
TRANS="0x222222fd79264bbe280b4986f6fefbc3524d0137"
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
EXPECTED_USDA="0x0000206329b97db379d5e1bf586bbdb969c63274"
QUOTE_RECEIVER="0x000000000000000000000000000000000000dEaD"
SIZES=[100,1000,5000]
MAX=35;COUNT=0;DENIED=set();START=time.monotonic()
def save(path,data):
 p=OUT/path;p.parent.mkdir(exist_ok=True,parents=True)
 p.write_text(json.dumps(data,indent=2)+"\n")
def selector(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()[:8]
def w(x):return format(int(x),"064x")
def a(x):return x[2:].lower().zfill(64)
def call(name,url,data):
 global COUNT
 host=urllib.request.urlparse(url).netloc if hasattr(urllib.request,"urlparse") else url.split("/")[2]
 if host not in ("api.odos.xyz","rpc-eth.blockmachine.io"):raise ValueError("Unapproved host")
 if host in DENIED:raise RuntimeError("STOP after provider refusal "+host)
 if COUNT>=MAX or time.monotonic()-START>540:raise RuntimeError("Research budget reached")
 COUNT+=1;time.sleep(.7);raw=b"";rec={"name":name,"host":host,"id":COUNT}
 try:
  body=json.dumps(data).encode()
  req=urllib.request.Request(url,data=body,method="POST",
     headers={"Accept":"application/json","Content-Type":"application/json","User-Agent":"QT-Stage1-Winddown-Research"})
  with urllib.request.urlopen(req,timeout=22) as resp:
   raw=resp.read(850001);rec["http"]=resp.status
  if len(raw)>850000:raise ValueError("Excessive response, abort")
  obj=json.loads(raw)
  rec["status"]="OK"
  if url==RPC and obj.get("error"):rec["status"]="RPC_ERROR";rec["rpc_error"]=obj["error"];raise RuntimeError(str(obj["error"]))
  return obj
 except urllib.error.HTTPError as e:
  rec.update(http=e.code,error=str(e.reason));raw=e.read(60000)
  if e.code in (401,403,429):DENIED.add(host)
  raise
 except Exception as e:rec["error"]=repr(e);raise
 finally:
  rec["sha256"]=hashlib.sha256(raw).hexdigest();rec["bytes"]=len(raw)
  save(f"requests/{COUNT:03d}.json",rec)
  (OUT/"raw").mkdir(exist_ok=True)
  (OUT/f"raw/{COUNT:03d}.body").write_bytes(raw)
def rpc(method,params,name):
 d=call(name,RPC,{"jsonrpc":"2.0","id":COUNT+1,"method":method,"params":params})
 if "result" not in d:raise ValueError("Missing JSON-RPC result")
 return d["result"]
def abiwords(s):
 if not isinstance(s,str) or not s.startswith("0x") or len(s[2:])%64:raise ValueError("Invalid ABI result")
 return [int(s[i:i+64],16) for i in range(2,len(s),64)]
def view(to,func,args,block,name):
 data=selector(func)+"".join(w(v) for v in args)
 return abiwords(rpc("eth_call",[{"to":to,"data":data},hex(block)],name))
def uint(to,func,args,block,name):
 ws=view(to,func,args,block,name)
 if len(ws)!=1:raise ValueError("Expected scalar ABI")
 return ws[0]
def address(raw):
 if raw<=0 or raw>=2**160:raise ValueError("Invalid address")
 return "0x"+format(raw,"040x")
def odos(qty):
 payload={"chainId":1,"compact":False,"simple":False,"disableRFQs":True,
 "inputTokens":[{"tokenAddress":USDC,"amount":str(qty)}],
 "outputTokens":[{"tokenAddress":EXPECTED_USDA,"proportion":1}],
 "userAddr":QUOTE_RECEIVER,"slippageLimitPercent":0.5,
 "referralCode":0}
 obj=call("odos_readonly_quote",ODOS,payload)
 if not isinstance(obj,dict) or not isinstance(obj.get("outAmounts"),list) or len(obj["outAmounts"])!=1:
  raise ValueError("Unusable Odos quote response")
 if not isinstance(obj.get("inAmounts"),list) or int(obj["inAmounts"][0])!=qty:
  raise ValueError("Input amount mismatch from Odos")
 return obj
def main():
 report={"scope":"Acquire USDA from public multi-venue quote then burn to spendable USDC during Angle wind-down",
 "basis":"Angle official redemption notice deadline 2027-03-01; actual onchain burn quote",
 "research_only":True,"full_transaction_executed":False,
 "no_wallet_or_order_posting":True,"RFQ_private_flow_disabled":True,
 "cases":[],"complete":False,
 "warnings":["Odos quote is not an executable guaranteed fill or onchain cash profit",
   "Even with a good price, route cannot be aggregated with its own Transmuter burn without accounting for state and arbitrage loops",
   "No output from a blocked API is evidence of 0 arbitrage",
   "Sunset/redemption rights and current governance changes must be respected",
   "Any quote is invalid after its timestamp, fees and gas, and requires full eligible execution"]}
 save("REPORT.json",report)
 try:
  if int(rpc("eth_chainId",[],"chainid"),16)!=1:raise ValueError("Wrong chain")
  latest=int(rpc("eth_blockNumber",[],"initial_tip"),16)-2
  head=rpc("eth_getBlockByNumber",[hex(latest),False],"anchor")
  report["anchor_block"]=latest;report["anchor_hash"]=head["hash"]
  tok=address(uint(TRANS,"agToken()",[],latest,"usda_token_from_transmuter"))
  if tok!=EXPECTED_USDA:raise ValueError("Unexpected stablecoin address")
  report["usda_address_verified"]=tok
  if uint(tok,"decimals()",[],latest,"usda_decimals")!=18:raise ValueError("Unexpected decimals")
  report["paused_burn"]=bool(uint(TRANS,"isPaused(address,uint8)",[int(USDC,16),1],latest,"burn_paused"))
  report["usdc_whitelisted_only"]=bool(uint(TRANS,"isWhitelistedCollateral(address)",[int(USDC,16)],latest,"usdc_whitelist"))
  report["usdc_reserves_raw"]=str(uint(USDC,"balanceOf(address)",[int(TRANS,16)],latest,"usdc_reserves"))
  if report["paused_burn"] or report["usdc_whitelisted_only"]:
   report["economics"]="NOT_PERMISSIONLESS_REDIRECT";report["complete"]=True
  else:
   for size in SIZES:
    row={"spend_usdc":size,"status":"UNRESOLVED"}
    report["cases"].append(row);save("REPORT.json",report)
    try:
     quote=odos(size*10**6)
     out=int(quote["outAmounts"][0])
     if out<=0:raise ValueError("Odos gave zero USDA")
     row.update(odos_USDA_raw=str(out),path_id_received=bool(quote.get("pathId")),
                route_hint=quote.get("pathViz"),
                api_in_usdc_raw=str(quote["inAmounts"][0]))
     cash=uint(TRANS,"quoteIn(uint256,address,address)",[out,int(tok,16),int(USDC,16)],latest,
                 "true_transmuter_burn")
     gross=cash-size*10**6
     row.update(transmuter_USDC_cash_raw=str(cash),cash_gross_raw=str(gross),
         positive_gross_quote=bool(gross>0),
         economically_usable_reserve_capacity=int(report["usdc_reserves_raw"])>=cash,
         status="QUOTED_NOT_EXECUTED")
    except Exception as e:row.update(status="NO_USABLE_QUOTE",error=repr(e))
    save("REPORT.json",report)
    if DENIED:raise RuntimeError("STOP on provider denied "+str(DENIED))
   report["complete"]=True
  chk=rpc("eth_getBlockByNumber",[hex(latest),False],"anchor_recheck")
  if chk["hash"]!=head["hash"]:raise ValueError("Anchor reorg")
 except Exception as e:report["error"]=repr(e);report["traceback"]=traceback.format_exc()
 report["requests"]=COUNT;report["denied_hosts"]=sorted(DENIED)
 save("REPORT.json",report)
 print(json.dumps({"complete":report["complete"],"requests":COUNT,
   "error":report.get("error"),"pause":report.get("paused_burn"),"records":report["cases"]},indent=2,default=str),flush=True)
 if not report["complete"]:raise SystemExit("Partial market research, do not claim zero opportunities")
if __name__=="__main__":main()
