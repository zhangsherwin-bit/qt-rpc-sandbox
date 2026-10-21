"""QT Stage1 economics: Uniswap creator-fee buyback pays executor BEFORE burn.

One frozen, PUBLIC, read-only two-chain existence/activity check. No API key,
wallet or transaction. Official addresses documented by Uniswap in Oct 2026.
Eligibility/payout balances/finite burn token quotes require later evidence.
"""
from datetime import datetime,timezone
from pathlib import Path
from Crypto.Hash import keccak
import json,requests,hashlib,time,sys

SOURCES=[
 {"chain":"robinhood","chain_id":4663,"native":"ETH",
  "rpc":"https://rpc.mainnet.chain.robinhood.com",
  "burn_recipient":"0xa1ba4cc12654d2b188e3ba77dc86c75ca47f1a4e"},
 {"chain":"arc","chain_id":5042,"native":"USDC (native gas asset, not ETH)",
  "rpc":"https://rpc.mainnet.arc.io",
  "burn_recipient":"0x5cee9852d136833ae26c9e36a96fc02cdfc9c40c"}
]
OFFSETS=[250,15000,60000]
WIDTH=450
CAP_RPC_REQUESTS=19
OUT=Path("stage1_payfirst_evidence")
def topic(sig):
 h=keccak.new(digest_bits=256);h.update(sig.encode());return "0x"+h.hexdigest()
TOKENS_BURNED=topic("TokensBurned(uint256,address,uint256)")
THRESHOLD_SELECTOR=topic("minCurrency1BurnAmount()")[:10]
RPT={
 "as_of_utc":datetime.now(timezone.utc).isoformat(),
 "research":"Uniswap Liquidity Launchpad pay-first native asset -> callback -> fixed token burn",
 "source_contracts":[
   "Uniswap/liquidity-launcher src/periphery/BaseClaimRecipient.sol",
   "Uniswap/liquidity-launcher src/periphery/BaseClaimRecipientWithCallback.sol",
   "Uniswap/liquidity-launcher src/periphery/BuybackAndBurnClaimRecipient.sol",
   "https://developers.uniswap.org/docs/liquidity/liquidity-launchpad/deployments"],
 "source_economic_ordering":"BaseClaimRecipient pays assets to caller, then _afterClaim calls IClaimExecutor.onClaimed, then BuybackAndBurn pulls fixed token to burn",
 "chains":{},"rpc_attempts":0,"sample_complete":False,
 "wallets_or_orders_used":False,"blockmachine_authenticated_ru":0,
 "profitable_trade_found":False,
 "unmeasured":["actual claimable amounts per position","position tokenIds",
               "token buy route slippage","burn token decimals","callback execution gas",
               "builder payment and competition","access to finite DEX inventory"]}
def record():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(RPT,indent=2,sort_keys=True)+"\n")
def get(src,method,params):
 if RPT["rpc_attempts"]>=CAP_RPC_REQUESTS:raise RuntimeError("PUBLIC_RPC_REQUEST_CAP")
 tag=f"{src['chain']}_{RPT['rpc_attempts']:02}"
 req={"jsonrpc":"2.0","id":RPT["rpc_attempts"]+1,"method":method,"params":params}
 body=json.dumps(req,separators=(",",":")).encode()
 RPT["rpc_attempts"]+=1
 entry={"chain":src["chain"],"method":method,
   "timestamp":datetime.now(timezone.utc).isoformat(),
   "request_sha256":hashlib.sha256(body).hexdigest()}
 raw=b""
 try:
  resp=requests.post(src["rpc"],data=body,
    headers={"Content-Type":"application/json","Accept":"application/json",
             "User-Agent":"QT-readonly-research/1"},
    timeout=(10,24),allow_redirects=False)
  if len(resp.content)>1900000:raise RuntimeError("OVERSIZE_RPC_RESPONSE")
  raw=resp.content
  entry["http_status"]=resp.status_code
  entry["response_sha256"]=hashlib.sha256(raw).hexdigest()
  (OUT/(tag+".request")).write_bytes(body)
  (OUT/(tag+".response")).write_bytes(raw)
  RPT.setdefault("request_evidence",[]).append(entry)
  record()
  if resp.status_code in (401,403,429):
   raise RuntimeError("PUBLIC_PROVIDER_ACCESS_DENIED_"+str(resp.status_code))
  if resp.status_code!=200:raise RuntimeError("HTTP_"+str(resp.status_code))
  data=resp.json()
  if not isinstance(data,dict) or "error" in data or "result" not in data:
   raise RuntimeError("RPC_RESULT_UNAVAILABLE")
  return data["result"]
 finally:
  time.sleep(1.3)
def parse_burn_event(l):
 ts=l.get("topics",[]);d=l.get("data","")
 if len(ts)!=3 or ts[0].lower()!=TOKENS_BURNED or not isinstance(d,str) or len(d)!=66:
  raise ValueError("Unexpected TokensBurned ABI")
 return {"tx":l["transactionHash"],"block":int(l["blockNumber"],16),
    "token_id":str(int(ts[1],16)),"burned_token":"0x"+ts[2][-40:].lower(),
    "burn_amount_raw":str(int(d,16))}
def one(src):
 chain=src["chain"]
 e={"network":chain,"chainid_expected":src["chain_id"],"native_currency_for_contract_address_zero":src["native"],
    "burn_recipient":src["burn_recipient"],"windows":[],"status":"UNRESOLVED"}
 RPT["chains"][chain]=e;record()
 try:
  chainid=int(get(src,"eth_chainId",[]),16)
  if chainid!=src["chain_id"]:raise RuntimeError("WRONG_CHAIN")
  b=int(get(src,"eth_blockNumber",[]),16)-8
  h=get(src,"eth_getBlockByNumber",[hex(b),False])
  if not isinstance(h,dict) or int(h["number"],16)!=b:raise RuntimeError("BAD_CANONICAL_BLOCK")
  e["pinned_block"]={"number":b,"hash":h["hash"]}
  code=get(src,"eth_getCode",[src["burn_recipient"],hex(b)])
  e["contract_bytecode_present"]=isinstance(code,str) and code not in ("0x","0x0")
  if not e["contract_bytecode_present"]:
   e["status"]="NO_DEPLOYED_BYTECODE";return
  threshold=get(src,"eth_call",[{"to":src["burn_recipient"],
                  "data":THRESHOLD_SELECTOR},hex(b)])
  if not isinstance(threshold,str) or len(threshold)!=66:raise RuntimeError("BAD_BURN_THRESHOLD")
  e["min_currency1_burn_raw"]=str(int(threshold,16))
  e["threshold_nonzero"]=int(threshold,16)>0
  total=0;matches=[]
  for offset in OFFSETS:
   end=b-offset;start=end-WIDTH+1
   w={"offset":offset,"from":start,"to":end,"state":"UNRESOLVED"}
   e["windows"].append(w)
   try:
    logs=get(src,"eth_getLogs",[{"address":src["burn_recipient"],
           "fromBlock":hex(start),"toBlock":hex(end),"topics":[TOKENS_BURNED]}])
    if not isinstance(logs,list):raise RuntimeError("BAD_LOG_ARRAY")
    batch=[parse_burn_event(x) for x in logs]
    if any(x["burn_amount_raw"]!=e["min_currency1_burn_raw"] for x in batch):
     w["warning"]="Historical burn amount differs from current threshold; governance/version or source mismatch"
    w["events"]=len(batch);w["state"]="OK";total+=len(batch);matches.extend(batch[:7])
   except Exception as ex:
    w["error_class"]=type(ex).__name__;w["status_detail"]=str(ex)[:90]
    if "PUBLIC_PROVIDER_ACCESS_DENIED" in str(ex):break
   record()
  e["events_sample_count"]=total
  e["selected_sampled_burns"]=matches[:10]
  again=get(src,"eth_getBlockByNumber",[hex(b),False])
  e["same_anchor"]=again["hash"]==h["hash"]
  e["status"]="COMPLETE" if e["same_anchor"] and len(e["windows"])==len(OFFSETS) and all(x["state"]=="OK" for x in e["windows"]) else "INCOMPLETE"
 except Exception as ex:
  e["error_class"]=type(ex).__name__
  e["status_detail"]=str(ex)[:90]
  e["status"]="BLOCKED_OR_UNRESOLVED"
 finally:record()
def main():
 record()
 for item in SOURCES:one(item)
 RPT["sample_complete"]=all(x["status"]=="COMPLETE" for x in RPT["chains"].values()) and len(RPT["chains"])==len(SOURCES)
 record()
 print(json.dumps({"complete":RPT["sample_complete"],"requests":RPT["rpc_attempts"],
     "by_chain":{k:{"status":v["status"],"code":v.get("contract_bytecode_present"),
                   "threshold_raw":v.get("min_currency1_burn_raw"),
                   "events":v.get("events_sample_count"),"error":v.get("status_detail")}
                for k,v in RPT["chains"].items()},
     "blockmachine_ru":0,"no_transactions":True},sort_keys=True))
 return 0 if RPT["sample_complete"] else 2
if __name__=="__main__":sys.exit(main())
