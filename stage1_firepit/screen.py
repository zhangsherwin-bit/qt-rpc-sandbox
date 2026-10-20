"""QT Stage 1: Uniswap UNI-burn-to-collect-fee-assets is a NEW cash entitlement.

Source: official Uniswap/protocol-fees ExchangeReleaser, ResourceManager,
TokenJar and verified mainnet deployments (Oct 2026).
Read-only historical contract/event & eligible-asset check. NOT an earnings claim.
No wallet, approvals, burn, signed tx, orders or value transfers.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from Crypto.Hash import keccak
import json,os
from qt_rpc.client import ReadOnlyRPC,AuthenticatedBudget,read_key_status,RPCFailure
OUT=Path("stage1_firepit_evidence")
FIREPIT="0x0d5cd355e2abeb8fb1552f56c965b867346d6721"
JAR="0xf38521f130fccf29db1961597bc5d2b60f995f85"
UNI="0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"
DEAD="0x000000000000000000000000000000000000dead"
# Bounded observation set: major tokens and source-known Uniswap v2 LP shares.
# These are a PARTIAL set: never assume total jar value from this inventory.
ASSETS={
 "WETH":"0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
 "USDC":"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
 "USDT":"0xdac17f958d2ee523a2206206994597c13d831ec7",
 "DAI":"0x6b175474e89094c44da98b954eedeac495271d0f",
 "UNI":UNI,
 "WBTC":"0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
 "V2_USDC_WETH":"0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc",
 "V2_USDT_WETH":"0x0d4a11d5eeaac28e3f61d100daF4d40471f1852",
 "V2_DAI_WETH":"0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
 "V2_USDC_USDT":"0x3041cbd36888becc7bbcBc0045e3b1f144466f5f"
}
V2_PREFIX="V2_"
WINDOW=6000
OFFSETS=[200,26000,115000,440000]
MAX_EVENTS_PER_RECEIPT_FAMILY=5
MAX_RU=170
RESERVE_RU=1500
def sig(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
RELEASED=sig("Released(uint256,address,address[])")
TRANSFER=sig("Transfer(address,address,uint256)")
def sel(s):return sig(s)[:10]
SEL_THRESHOLD=sel("threshold()")
SEL_NONCE=sel("nonce()")
SEL_RESOURCE=sel("RESOURCE()")
SEL_TOKENJAR=sel("TOKEN_JAR()")
SEL_MAX_ASSETS=sel("MAX_RELEASE_LENGTH()")
SEL_RELEASER=sel("releaser()")
SEL_BALANCE=sel("balanceOf(address)")
SEL_TOKEN0=sel("token0()")
SEL_TOKEN1=sel("token1()")
SEL_SUPPLY=sel("totalSupply()")
SEL_RESERVES=sel("getReserves()")
def n(v):
 if isinstance(v,int) and v>=0:return v
 if isinstance(v,str) and v.startswith("0x"):return int(v,16)
 raise ValueError("invalid uint")
def word(v):return format(int(v),"064x")
def address_word(v):
 if not isinstance(v,str) or len(v)!=66:raise ValueError("invalid ABI address")
 return "0x"+v[-40:].lower()
def decode_released(e):
 t=e.get("topics",[]);d=e.get("data","")
 if len(t)!=3 or t[0].lower()!=RELEASED or not d.startswith("0x"):
  raise ValueError("Not official Released event")
 if len(d)<130 or (len(d)-2)%64!=0:raise ValueError("Bad release data")
 words=[d[2+i:2+i+64] for i in range(0,len(d)-2,64)]
 offset=int(words[0],16)//32
 if offset>=len(words):raise ValueError("Array offset out of bounds")
 count=int(words[offset],16)
 if count>20 or offset+1+count>len(words):raise ValueError("Malformed asset list")
 assets=["0x"+words[offset+1+i][-40:].lower() for i in range(count)]
 if len(assets)!=len(set(assets)):raise ValueError("Duplicate release asset entries")
 return {"tx":e["transactionHash"],"block":n(e["blockNumber"]),
         "log_index":n(e["logIndex"]),"nonce":n(t[1]),
         "recipient":address_word(t[2]),"assets":assets,
         "asset_count":count}
def tokentransfers(rc,from_addr,to_addr):
 out=defaultdict(int)
 for l in rc.get("logs",[]):
  ts=l.get("topics",[])
  if len(ts)!=3 or ts[0].lower()!=TRANSFER:continue
  try:src=address_word(ts[1]);dst=address_word(ts[2])
  except ValueError:continue
  if src==from_addr and dst==to_addr and len(l.get("data",""))==66:
   out[l["address"].lower()]+=n(l["data"])
 return {k:str(v) for k,v in sorted(out.items())}
def call(rpc,contract,selector,args,block):
 raw=rpc.rpc("eth_call",[{"to":contract,"data":selector+args},hex(block)])
 if not isinstance(raw,str) or not raw.startswith("0x"):raise ValueError("bad ABI result")
 return raw
def scalar(rpc,contract,selector,block):
 raw=call(rpc,contract,selector,"",block)
 if len(raw)!=66:raise ValueError("ABI scalar result unexpected")
 return n(raw)
def asset_balance(rpc,asset,block):
 raw=call(rpc,asset,SEL_BALANCE,word(int(JAR,16)),block)
 if len(raw)!=66:raise ValueError("nonstandard ERC20 balance")
 return n(raw)
def process(release,rc,tx):
 if n(rc["status"])!=1 or n(rc["blockNumber"])!=release["block"] or tx["hash"].lower()!=release["tx"].lower():raise ValueError("wrong failed tx")
 if rc["transactionHash"].lower()!=release["tx"].lower():raise ValueError("wrong receipt")
 burn=tokentransfers(rc,tx["from"].lower(),DEAD).get(UNI)
 any_burn={}
 for l in rc.get("logs",[]):
  ts=l.get("topics",[])
  if l.get("address","").lower()!=UNI or len(ts)!=3 or ts[0].lower()!=TRANSFER:continue
  if address_word(ts[2])==DEAD:
   payer=address_word(ts[1]);any_burn[payer]=any_burn.get(payer,0)+n(l["data"])
 beneficiary=release["recipient"]
 fromjar=tokentransfers(rc,JAR,beneficiary)
 gas=n(rc["gasUsed"])*n(rc["effectiveGasPrice"])
 return {"tx":release["tx"],"nonce":release["nonce"],"block":release["block"],
    "recipient":beneficiary,"selected_assets":release["assets"],
    "payer_from_ERC20_burn_events_wei":{k:str(v) for k,v in any_burn.items()},
    "UNI_burned_by_tx_sender_raw":burn,
    "received_from_jar_ERC20_raw":fromjar,
    "native_ETH_received_unverified_without_trace":True,
    "tx_sender":tx["from"].lower(),"tx_destination":str(tx.get("to") or "").lower(),
    "actual_transaction_gas_wei":str(gas),
    "cash_profit_after_bid_unknown":True}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 rpt={"timestamp_utc":datetime.now(timezone.utc).isoformat(),
  "hypothesis":"permissionless fixed UNI burn in return for selectable protocol fee asset basket, including Uniswap V2 LP inventory",
  "official_source":"Uniswap/protocol-fees mainnet README, ExchangeReleaser.sol, Firepit.sol, TokenJar.sol",
  "contracts":{"firepit":FIREPIT,"jar":JAR},"state":"UNRESOLVED",
  "frozen_windows":{"offsets":OFFSETS,"blocks":WINDOW},
  "frozen_assets":ASSETS,"assets_are_partial_not_full_jar_inventory":True,
  "economic_warnings":["current asset balances are NOT executable net proceeds",
    "LP tokens have underlying principal claims and market slippage",
    "current UNI threshold is not guaranteed historical threshold",
    "ERC20 logs do not reveal native ETH or private builder payments",
    "a competing nonce race and inclusion bid can consume the surplus",
    "historic incumbent release is not our attainable profit"],
  "success_not_imply_profit":True,"live_trades":0,"wallet_actions":0,
  "value_USD_inferred":None,"windows":[],"fees_historical":[],"balances":{}}
 rpc=None;budget=None
 try:
  if os.getenv("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES" or os.getenv("QT_ALLOW_AUTHENTICATED_RPC")!="YES":
   raise RPCFailure("APPROVAL_NOT_CONFIRMED")
  key=os.getenv("BLOCKMACHINE_API_KEY","").strip()
  if not key:raise RPCFailure("GITHUB_SECRET_MISSING")
  status=read_key_status(key)
  if status.get("auth")!="authenticated" or status.get("ru_remaining",0)<RESERVE_RU+MAX_RU:
   raise RPCFailure("AUTHENTICATED_STATUS_OR_RESERVE_UNAVAILABLE")
  budget=AuthenticatedBudget(status,reserve_floor=RESERVE_RU,max_run_ru=MAX_RU,approved=True)
  rpc=ReadOnlyRPC(1,OUT/"raw",status=status,api_key=key,budget=budget,
      max_attempts=1,max_requests=72)
  rpt["starting_ru_snapshot"]=status.get("ru_remaining")
  rpt["reported_ru_rate_per_min"]=status.get("rate_limit_rpm")
  if n(rpc.rpc("eth_chainId",[]))!=1:raise ValueError("wrong chain")
  head=n(rpc.rpc("eth_blockNumber",[]))-12
  b=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  if n(b["number"])!=head:raise ValueError("wrong head")
  rpt["anchor"]={"number":head,"hash":b["hash"],"timestamp":n(b["timestamp"])}
  for contract in [FIREPIT,JAR]:
   if rpc.rpc("eth_getCode",[contract,hex(head)]) in (None,"0x"):raise ValueError("Deployed contract missing")
  rpt["threshold_uni_raw"]=str(scalar(rpc,FIREPIT,SEL_THRESHOLD,head))
  rpt["nonce"]=scalar(rpc,FIREPIT,SEL_NONCE,head)
  rpt["max_release_assets"]=scalar(rpc,FIREPIT,SEL_MAX_ASSETS,head)
  rpt["resource_address"]=hex(scalar(rpc,FIREPIT,SEL_RESOURCE,head))
  rpt["tokenjar_from_firepit"]="0x"+format(scalar(rpc,FIREPIT,SEL_TOKENJAR,head),"040x")
  rpt["jar_releaser"]="0x"+format(scalar(rpc,JAR,SEL_RELEASER,head),"040x")
  if rpt["max_release_assets"]!=20 or rpt["tokenjar_from_firepit"]!=JAR or rpt["jar_releaser"]!=FIREPIT:
   raise ValueError("Source/deployment access mismatch")
  if int(rpt["resource_address"],16)!=int(UNI,16):raise ValueError("Wrong burn resource")
  rpt["jar_native_ETH_raw"]=str(n(rpc.rpc("eth_getBalance",[JAR,hex(head)])))
  for name,token in ASSETS.items():
   record={"address":token,"state":"UNRESOLVED"}
   rpt["balances"][name]=record
   try:
    amt=asset_balance(rpc,token,head)
    record.update({"state":"OK","jar_held_raw":str(amt),"has_balance":amt>0})
    if name.startswith(V2_PREFIX) and amt>0:
     record["pair_token0"]="0x"+format(scalar(rpc,token,SEL_TOKEN0,head),"040x")
     record["pair_token1"]="0x"+format(scalar(rpc,token,SEL_TOKEN1,head),"040x")
     record["pair_total_supply_raw"]=str(scalar(rpc,token,SEL_SUPPLY,head))
     reserves=call(rpc,token,SEL_RESERVES,"",head)
     if len(reserves)<2+3*64:raise ValueError("nonstandard reserves")
     record["reserve0_raw"]=str(int(reserves[2:66],16))
     record["reserve1_raw"]=str(int(reserves[66:130],16))
   except Exception as e:
    record["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
   (OUT/"REPORT.json").write_text(json.dumps(rpt,indent=2,sort_keys=True)+"\n")
  found=[]
  for off in OFFSETS:
   end=head-off;start=end-WINDOW+1
   rec={"start":start,"end":end,"offset":off,"state":"UNRESOLVED"}
   rpt["windows"].append(rec)
   try:
    logs=rpc.rpc("eth_getLogs",[{"address":FIREPIT,
      "fromBlock":hex(start),"toBlock":hex(end),"topics":[RELEASED]}])
    if not isinstance(logs,list):raise ValueError("no logs")
    for e in logs:found.append(decode_released(e))
    rec.update({"state":"OK","releases":len(logs)})
   except Exception as e:
    rec["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
    if rpc.aborted:break
   (OUT/"REPORT.json").write_text(json.dumps(rpt,indent=2,sort_keys=True)+"\n")
  rpt["release_event_count"]=len(found)
  rpt["unique_release_transactions"]=len({r["tx"] for r in found})
  rpt["selected_event_samples"]=sorted(found,key=lambda r:(r["block"],r["log_index"]))[:8]
  seen=set()
  for event in sorted(found,key=lambda r:(r["block"],r["log_index"])):
   if event["tx"] in seen:continue
   seen.add(event["tx"])
   if len(rpt["fees_historical"])>=MAX_EVENTS_PER_RECEIPT_FAMILY:break
   row={"tx":event["tx"],"state":"UNRESOLVED"}
   rpt["fees_historical"].append(row)
   try:
    tx=rpc.rpc("eth_getTransactionByHash",[event["tx"]])
    rc=rpc.rpc("eth_getTransactionReceipt",[event["tx"]])
    row.update(process(event,rc,tx))
    row["state"]="HISTORICAL_INCUMBENT_RELEASE_OBSERVED_UNPRICED"
   except Exception as e:row["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
  head2=rpc.rpc("eth_getBlockByNumber",[hex(head),False])
  rpt["canonical_anchor_rechecked"]=head2["hash"]==b["hash"]
  rpt["state"]="COMPLETE_ACTIVITY_SCREEN" if (rpt["canonical_anchor_rechecked"] and
    len(rpt["windows"])==len(OFFSETS) and all(x["state"]=="OK" for x in rpt["windows"]) and
    all(x["state"]=="OK" for x in rpt["balances"].values()) and
    all(x["state"]=="HISTORICAL_INCUMBENT_RELEASE_OBSERVED_UNPRICED" for x in rpt["fees_historical"])) else "INCOMPLETE"
 except Exception as e:
  rpt["error_kind"]=e.kind if isinstance(e,RPCFailure) else type(e).__name__
 rpt["estimated_ru_attempts"]=budget.attempted_ru if budget else 0
 rpt["rpc_requests_sent"]=rpc.attempted if rpc else 0
 (OUT/"REPORT.json").write_text(json.dumps(rpt,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:rpt.get(k) for k in ("state","release_event_count","unique_release_transactions","threshold_uni_raw","nonce","estimated_ru_attempts","rpc_requests_sent","error_kind")},sort_keys=True))
 return 0 if rpt["state"]=="COMPLETE_ACTIVITY_SCREEN" else 2
if __name__=="__main__":raise SystemExit(main())
