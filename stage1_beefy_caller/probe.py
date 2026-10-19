"""QT Programme III Stage 1: independent Beefy harvester-caller cash experiment.
PUBLIC READ-ONLY ETH_CALL/ETH_GETLOGS/RECEIPTS. No signing or transactions.
Frozen metadata-only selection and fixed disjoint block windows; quote ≠ profit.
"""
import json, time, re, hashlib, urllib.request, urllib.error, traceback, sys, os
from pathlib import Path
from datetime import datetime, timezone
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC, WeightedLimiter, read_key_status

OUT=Path("beefy_caller_evidence");OUT.mkdir(exist_ok=True)
API="https://api.beefy.finance"
CHAINS={
 "ethereum":{"rpc":"https://rpc-eth.blockmachine.io","id":1,
             "weth":"0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"},
 "base":{"rpc":"https://rpc-base.blockmachine.io","id":8453,
         "weth":"0x4200000000000000000000000000000000000006"}
}
ADDRESS=re.compile(r"^0x[a-fA-F0-9]{40}$")
CALLER="0x000000000000000000000000000000000000dEaD"
PER_CHAIN_QUOTA=6
WINDOW_END_OFFSETS=[100,9100,18100,36100,72100]
WINDOW_BLOCKS=950
MAX_RPCS_PER_CHAIN=75
def k256(sig):
 h=keccak.new(digest_bits=256);h.update(sig.encode());return "0x"+h.hexdigest()
FEE_TOPIC=k256("ChargedFees(uint256,uint256,uint256)")
TRANSFER=k256("Transfer(address,address,uint256)")
SELECTORS={x:k256(x)[:10] for x in ["callReward()","paused()","native()","lastHarvest()","harvest()"]}
count={x:0 for x in CHAINS}
blocked=set()
rpt={"programme":"Programme III Stage1","as_of_utc":datetime.now(timezone.utc).isoformat(),
     "hypothesis":"permissionless harvesting service reward to caller, independent of liquidation or directional trading",
     "rules":{"public_read_only":True,"frozen_selection":"top three TVL plus top three TVL*positive APY*caller_fee, derived solely from public metadata, per chain",
              "chains":list(CHAINS),"window_end_offsets":WINDOW_END_OFFSETS,
              "window_blocks":WINDOW_BLOCKS,"max_rpc_per_chain":MAX_RPCS_PER_CHAIN,
              "historical_outcomes_not_used_for_selection":True},
     "providers":{},"vaults":[],"chains":{},"errors":[],"complete":False,
     "authorised_to_trade":False,"trades_sent":0,"stage2_cash_portfolio_validated":False}
def save():
 (OUT/"REPORT.json").write_text(json.dumps(rpt,sort_keys=True,indent=2,default=str)+"\n")
def archive(label,request_body,response_body,http):
 (OUT/"raw").mkdir(exist_ok=True)
 (OUT/"raw"/(label+".req")).write_bytes(request_body)
 (OUT/"raw"/(label+".response")).write_bytes(response_body)
 return {"request_sha256":hashlib.sha256(request_body).hexdigest(),
         "response_sha256":hashlib.sha256(response_body).hexdigest(),
         "http_status":http}
def fetch_json(url,label,maxsize=15000000,post=None):
 host=url.split("/")[2]
 if host in blocked: raise RuntimeError("provider previously denied, stopped: "+host)
 time.sleep(.35)
 body=post if post is not None else b""
 req=urllib.request.Request(url,data=post,headers={"User-Agent":"QT-Stage1-ReadOnly-Research/1","Content-Type":"application/json"},method="POST" if post is not None else "GET")
 status=-1;raw=b""
 try:
  with urllib.request.urlopen(req,timeout=32) as response:
   status=response.status
   raw=response.read(maxsize+1)
 except urllib.error.HTTPError as e:
  status=e.code; raw=e.read(min(maxsize,65536))
 finally:
  info=archive(label,body if post is not None else ("GET "+url).encode(),raw,status)
  rpt["providers"][label]=info
  save()
 if status in (401,403,429):
  blocked.add(host);raise RuntimeError(f"provider {host} denied HTTP {status}; not retried")
 if status!=200:raise RuntimeError(f"{host} HTTP {status}")
 if len(raw)>maxsize:raise RuntimeError("response exceeded fixed cap")
 return json.loads(raw)
RPC_SESSIONS={}
SHARED_STATUS=None
SHARED_QUOTA=None
def rpc(chain,method,params):
 global SHARED_STATUS,SHARED_QUOTA
 if SHARED_STATUS is None:
  SHARED_STATUS=read_key_status(os.environ.get("BLOCKMACHINE_API_KEY","").strip())
  ru=(SHARED_STATUS["rate_limit_rpm"] if SHARED_STATUS["auth"]=="authenticated" else 60)
  SHARED_QUOTA=WeightedLimiter(cap_ru=max(5,int(ru*.55)))
  rpt["rpc_auth_mode"]=SHARED_STATUS["auth"]
  rpt["rpc_ru_limit_reported"]=SHARED_STATUS["rate_limit_rpm"]
  rpt["rpc_ru_remaining_at_start"]=SHARED_STATUS["ru_remaining"]
 if chain not in RPC_SESSIONS:
  RPC_SESSIONS[chain]=ReadOnlyRPC(CHAINS[chain]["id"],OUT/"rpc_attempts"/chain,
     limiter=SHARED_QUOTA,max_requests=85,status=SHARED_STATUS)
 try:
  return RPC_SESSIONS[chain].rpc(method,params)
 finally:
  count[chain]=RPC_SESSIONS[chain].attempted
  save()
def as_uint(h):
 if not isinstance(h,str) or not h.startswith("0x") or len(h)<3:raise ValueError("empty/invalid word")
 return int(h,16)
def addr_word(h):
 if not isinstance(h,str) or len(h)!=66:raise ValueError("not address ABI word")
 return "0x"+h[-40:]
def find_value(d,vid,chain):
 if isinstance(d,dict):
  if vid in d and isinstance(d[vid],(int,float)):return float(d[vid])
  nested=d.get(chain)
  if isinstance(nested,dict) and vid in nested:return float(nested[vid])
  chain_id=str(CHAINS[chain]["id"])
  nested=d.get(chain_id)
  if isinstance(nested,dict) and vid in nested:return float(nested[vid])
 return 0.0
def select():
 vaults=fetch_json(API+"/vaults","API_vaults")
 tvl=fetch_json(API+"/tvl","API_tvl")
 apy=fetch_json(API+"/apy","API_apy")
 fees=fetch_json(API+"/fees","API_fees")
 if isinstance(vaults,dict):vaults=vaults.get("vaults",vaults.get("data",[]))
 if not isinstance(vaults,list):raise ValueError("vault metadata not list")
 rpt["api_catalog_count"]=len(vaults)
 for ch in CHAINS:
  pool=[]
  for v in vaults:
   if not isinstance(v,dict):continue
   if str(v.get("chain",v.get("network",""))).lower()!=ch:continue
   if v.get("eol") is True or v.get("status") in ("eol","retired","paused"):continue
   strategy=v.get("strategy")
   if not isinstance(strategy,str) or not ADDRESS.match(strategy):continue
   vid=str(v.get("id",""))
   size=find_value(tvl,vid,ch)
   rate=find_value(apy,vid,ch)
   fee=fees.get(vid,{}) if isinstance(fees,dict) else {}
   caller=((fee.get("performance") or {}).get("call",0) if isinstance(fee,dict) else 0)
   try:caller=float(caller)
   except Exception:caller=0
   if not 0<=caller<=1:caller=0
   if size<=10000:continue
   pool.append({"id":vid,"chain":ch,"strategy":strategy,"vault":v.get("earnContractAddress"),
                "tvl_usd_reported":size,"apy_reported":rate,"caller_fee_fraction_reported":caller,
                "metadata_lastHarvest":v.get("lastHarvest"),
                "ranking_estimate_not_cash":size*max(rate,0)*caller})
  pool=sorted(pool,key=lambda x:(-x["tvl_usd_reported"],x["id"]))
  selected=pool[:3]
  for v in sorted(pool,key=lambda x:(-x["ranking_estimate_not_cash"],x["id"])):
   if v["strategy"].lower() not in {x["strategy"].lower() for x in selected}:selected.append(v)
   if len(selected)>=PER_CHAIN_QUOTA:break
  rpt["chains"][ch]={"eligible_metadata_count":len(pool),"selected_count":len(selected),
                     "selection_rule_applied_prior_to_chain_profit_test":True,"observations":[],
                     "log_windows":[],"historical_cash":[]}
  rpt["vaults"]+=selected
 save()
def call(ch,to,data,block):
 return rpc(ch,"eth_call",[{"to":to,"data":data},hex(block)])
def evaluate(ch):
 st=rpt["chains"][ch];selected=[v for v in rpt["vaults"] if v["chain"]==ch]
 if not selected:return
 if as_uint(rpc(ch,"eth_chainId",[]))!=CHAINS[ch]["id"]:raise RuntimeError("wrong chain ID")
 tip=as_uint(rpc(ch,"eth_blockNumber",[]))
 anchor=tip-4
 head=rpc(ch,"eth_getBlockByNumber",[hex(anchor),False])
 st["anchor"]={"block":anchor,"hash":head["hash"],"timestamp":as_uint(head["timestamp"]),
               "baseFeePerGas_wei":as_uint(head["baseFeePerGas"]) if "baseFeePerGas" in head else None}
 weth=CHAINS[ch]["weth"].lower()
 addrs=[v["strategy"].lower() for v in selected]
 for v in selected:
  ob={"id":v["id"],"strategy":v["strategy"],"snapshot_block":anchor}
  st["observations"].append(ob)
  try:
   c=as_uint(call(ch,v["strategy"],SELECTORS["callReward()"],anchor))
   ob["callReward_native_raw"]=c
   ob["callReward_native_18dec"]=c/1e18
  except Exception as e:ob["callReward_error"]=str(e)[:260]
  for fn in ["paused()","native()","lastHarvest()"]:
   try:
    raw=call(ch,v["strategy"],SELECTORS[fn],anchor)
    if fn=="native()": ob["strategy_native"]=addr_word(raw)
    else:ob[fn[:-2]]=as_uint(raw)
   except Exception as e:ob[fn+"_error"]=str(e)[:260]
  if ob.get("callReward_native_raw",0)>0 and ob.get("strategy_native","").lower()==weth:
   try:
    gas=as_uint(rpc(ch,"eth_estimateGas",[{"to":v["strategy"],"from":CALLER,"data":SELECTORS["harvest()"]}]))
    ob["gas_estimate_readonly"]=gas
    basefee=st["anchor"].get("baseFeePerGas_wei")
    if basefee is not None:
     ob["gas_basefee_only_eth"]=gas*basefee/1e18
     ob["indicative_reward_less_basefee_only_eth"]=ob["callReward_native_18dec"]-ob["gas_basefee_only_eth"]
     ob["NOT_NET_PROFIT"]="excludes priority fee, any L1 data charge, potential update between quote and inclusion, successful execution and competition"
   except Exception as e:ob["harvest_gas_estimate_error"]=str(e)[:280]
  save()
 for o in WINDOW_END_OFFSETS:
  hi=anchor-o;lo=hi-WINDOW_BLOCKS+1
  w={"from":lo,"to":hi,"count":None}
  st["log_windows"].append(w)
  try:
   logs=rpc(ch,"eth_getLogs",[{"address":addrs,"topics":[FEE_TOPIC],
                               "fromBlock":hex(lo),"toBlock":hex(hi)}])
   w["count"]=len(logs);w["status"]="OK"
   for log in logs:
    if log["address"].lower() not in addrs:raise ValueError("unexpected log contract")
    dat=log["data"][2:]
    if len(dat)!=192:raise ValueError("ChargedFees data not three words")
    amounts=[int(dat[i:i+64],16) for i in range(0,192,64)]
    st["historical_cash"].append({"strategy":log["address"],"tx":log["transactionHash"],
         "block":as_uint(log["blockNumber"]),"log_index":as_uint(log["logIndex"]),
         "call_fee_raw":amounts[0],"beefy_fee_raw":amounts[1],"strategist_fee_raw":amounts[2],
         "original_caller_cash_status":"PENDING_RECEIPT"})
  except Exception as e:w["status"]="UNRESOLVED";w["error"]=str(e)[:270]
  save()
  if ch in RPC_SESSIONS and RPC_SESSIONS[ch].aborted:break
 rows=sorted(st["historical_cash"],key=lambda r:(r["block"],r["log_index"]))
 for event in rows[:8]:
  try:
   tx=rpc(ch,"eth_getTransactionByHash",[event["tx"]])
   receipt=rpc(ch,"eth_getTransactionReceipt",[event["tx"]])
   if tx is None or receipt is None:raise RuntimeError("tx/receipt missing")
   paid=as_uint(receipt["gasUsed"])*as_uint(receipt["effectiveGasPrice"])
   l1=as_uint(receipt["l1Fee"]) if "l1Fee" in receipt else None
   recipient=tx["from"].lower()
   transfers=[]
   for l in receipt.get("logs",[]):
    topics=l.get("topics",[])
    if l["address"].lower()!=weth or len(topics)!=3 or topics[0].lower()!=TRANSFER.lower():continue
    if len(l["data"])!=66:continue
    transfers.append({"from":"0x"+topics[1][-40:],"to":"0x"+topics[2][-40:],
      "amount_raw":as_uint(l["data"])})
   cand=[t for t in transfers if t["to"].lower()==recipient and t["amount_raw"]==event["call_fee_raw"]
         and t["from"].lower()==event["strategy"].lower()]
   event["tx_from"]=recipient
   event["recipient_weth_transfer_matched"]=len(cand)>0
   event["transaction_selector"]=tx.get("input","")[:10]
   event["status"]=as_uint(receipt["status"])
   event["tx_gas_paid_wei"]=paid
   event["l1_fee_wei"]=l1
   if len(cand)==1 and event["status"]==1:
    event["actual_caller_weth_reward_wei"]=event["call_fee_raw"]
    event["net_weth_vs_gas_wei_before_builder_side_payments"]=event["call_fee_raw"]-paid-(l1 or 0)
    event["cash_classification"]="THIRD_PARTY_SETTLED_COMPARABLE_WETH_TO_ETH"
    if ch=="base" and l1 is None:event["cash_classification"]="INCOMPLETE_MISSING_L1_FEE"
   else:
    event["cash_classification"]="UNATTRIBUTED_FEE_EVENT_NOT_CALLER_NET"
   save()
  except Exception as e:event["original_caller_cash_status"]="UNRESOLVED";event["error"]=str(e)[:300];save()
 # Canonical anchor check, not a promise of modern executability.
 again=rpc(ch,"eth_getBlockByNumber",[hex(anchor),False])
 st["anchor_rechecked"]=again["hash"]==head["hash"]
 save()
def main():
 save()
 try: select()
 except Exception as e:
  rpt["errors"].append({"phase":"API_METADATA","error":str(e)[:340]})
  save();print(json.dumps({"API_FAILED":rpt["errors"],"requests":count}));sys.exit(2)
 for ch in CHAINS:
  try:evaluate(ch)
  except Exception as e:
   rpt["chains"][ch]["error"]=str(e)[:350]
   rpt["errors"].append({"phase":ch,"error":str(e)[:350]})
  save()
 rpt["rpc_counts"]=count
 rpt["provider_denial_hosts"]=list(sorted(blocked))
 rpt["complete"]=all(x.get("anchor_rechecked") is True and all(w.get("status")=="OK" for w in x["log_windows"])
                      for x in rpt["chains"].values() if x["selected_count"]>0)
 save()
 print(json.dumps({"complete":rpt["complete"],"count":count,"selected":len(rpt["vaults"]),
   "events":{ch:len(x["historical_cash"]) for ch,x in rpt["chains"].items()},
   "errors":rpt["errors"]},default=str))
if __name__=="__main__":main()
