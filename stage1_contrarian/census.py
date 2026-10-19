"""QT Stage1 Contrarian economics: reward aggregation & bonded-truth challenges.
Official deployments and ABI frozen before log outcomes. Read-only, no wallets.
Original third-party cash is NEVER our predicted profitable recurring stream.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json, os
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC, AuthenticatedBudget, WeightedLimiter, read_key_status, RPCFailure

OUT=Path("contrarian_cash_evidence")
CONVEX_BOOSTER="0xf403c135812408bfbe8713b5a23a04b3d48aae31"
CRV="0xd533a949740bb3306d119cc777fa900ba034cd52"
WETH="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
UNISWAP_QUOTER_V1="0xb27308f9f90d607463bb33ea1bebb41c27ce5ab6"
UMA_OOV3={
 1:"0xfb55f43fb9f48f63f9269db7dde3bbbe1ebdc0de",
 8453:"0x2abf1bd76655de80edb3086114315eec75af500c"
}
WINDOW=7000
OFFSETS=[200,25000,90000,280000]
MAX_CONVEX_RECEIPTS=12
MAX_UMA_SETTLEMENTS_PER_CHAIN=8
INCREMENTAL_SWAP_GAS=170000
MAX_AUTH_RU=430
RU_MONTHLY_FLOOR=1500
SESSIONS={}
BUDGET=None;RATE=None;AUTH=None
def sigh(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
TRANSFER=sigh("Transfer(address,address,uint256)")
DISPUTED=sigh("AssertionDisputed(bytes32,address,address)")
SETTLED=sigh("AssertionSettled(bytes32,address,bool,bool,address)")
EARMARK_SELECTOR=sigh("earmarkRewards(uint256)")[:10]
GET_ASSERTION_SELECTOR=sigh("getAssertion(bytes32)")[:10]
BURN_SELECTOR=sigh("burnedBondPercentage()")[:10]
QUOTER_SELECTOR=sigh("quoteExactInputSingle(address,address,uint24,uint256,uint160)")[:10]
assert all(len(x)==66 for x in (TRANSFER,DISPUTED,SETTLED))
assert len(CONVEX_BOOSTER)==42
assert all(len(x)==42 for x in UMA_OOV3.values())
RPT={"programme":"QT Programme III Stage1",
 "utc":datetime.now(timezone.utc).isoformat(),
 "economic_mechanisms":{
   "C_BONDED_TRUTH":"Disprove a bonded optimistic-oracle assertion and receive slashed bond after multi-day adjudication. NOT flash-loan financed.",
   "C_REWARD_AGGREGATION":"Bundle Convex caller-paid CRV claims and cash-convert rewards into WETH. Can several negative-in-isolation jobs become positive together?"},
 "origin_source":"UMAprotocol/protocol official core networks JSON and OptimisticOracleV3Interface.sol; convex-eth/platform Booster.sol; Curve CRV contract.",
 "frozen_design":{"window_blocks":WINDOW,"lookback_end_offsets":OFFSETS,
  "UMA_targets":UMA_OOV3,"convex_booster":CONVEX_BOOSTER,"convex_reward_token":CRV,
  "quoter":UNISWAP_QUOTER_V1,"max_convex_receipts":MAX_CONVEX_RECEIPTS,
  "max_uma_settlements_per_chain":MAX_UMA_SETTLEMENTS_PER_CHAIN,
  "ru_cap":MAX_AUTH_RU,"reserve_floor":RU_MONTHLY_FLOOR,
  "receipt_selection":"Earliest separate transactions by block/log index, prior to profitability inspection.",
  "receipt_quote_timing":"At predecessor block. In hindsight; not a prewinner available reward forecast."},
 "chains":{},"errors":[],"complete":False,"trades":0,"transactions_signed":0,
 "stage2_ready":False,"expected_profit_per_month":None}
def save():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(RPT,indent=2,sort_keys=True,default=str)+"\n")
def hexuint(s):
 if not isinstance(s,str) or not s.startswith("0x"):raise ValueError("invalid 0x integer")
 return int(s,16)
def word(n):
 return format(int(n),"064x")
def addrword(a):return word(int(a,16))
def addr_from_word(s):
 if not isinstance(s,str) or len(s)!=64:raise ValueError("invalid ABI address")
 return "0x"+s[-40:].lower()
def addr_topic(s):
 if not isinstance(s,str) or len(s)!=66:return None
 return "0x"+s[-40:].lower()
def read(ch,method,params):
 global AUTH,RATE,BUDGET
 if ch not in SESSIONS:
  if os.environ.get("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES":
   raise RPCFailure("ACCOUNT_USE_RIGHTS_UNCONFIRMED")
  if os.environ.get("QT_ALLOW_AUTHENTICATED_RPC")!="YES":
   raise RPCFailure("AUTHENTICATED_DATA_USE_NOT_APPROVED")
  key=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
  if not key:raise RPCFailure("NO_AUTHENTICATED_SECRET")
  if AUTH is None:
   AUTH=read_key_status(key)
   if AUTH.get("auth")!="authenticated":raise RPCFailure("NOT_AUTHENTICATED")
   if AUTH.get("ru_remaining",0)<RU_MONTHLY_FLOOR+MAX_AUTH_RU:
    raise RPCFailure("INSUFFICIENT_RU_RESERVE_FOR_FROZEN_RUN")
   BUDGET=AuthenticatedBudget(AUTH,reserve_floor=RU_MONTHLY_FLOOR,
        max_run_ru=MAX_AUTH_RU,approved=True)
   RATE=WeightedLimiter(cap_ru=max(5,int(AUTH["rate_limit_rpm"]*.55)))
   RPT["ru_before"]=AUTH["ru_remaining"]
   RPT["reported_rpm"]=AUTH["rate_limit_rpm"]
   save()
  SESSIONS[ch]=ReadOnlyRPC(ch,OUT/("eth" if ch==1 else "base")/"rpc_raw",
       api_key=key,status=AUTH,budget=BUDGET,limiter=RATE,max_requests=115,max_attempts=2)
 return SESSIONS[ch].rpc(method,params)
def call(ch,contract,selector,data,block):
 return read(ch,"eth_call",[{"to":contract,"data":selector+data},hex(block)])
def header(ch,block):
 b=read(ch,"eth_getBlockByNumber",[hex(block),False])
 if not b or hexuint(b["number"])!=block:raise ValueError("missing pinned header")
 return {"number":block,"hash":b["hash"],"timestamp":hexuint(b["timestamp"])}
def windows(head):
 return [{"start":head-x-WINDOW+1,"end":head-x,"offset":x} for x in OFFSETS]
def parse_settled(l):
 t=l.get("topics",[])
 if len(t)!=3 or t[0].lower()!=SETTLED:raise ValueError("Settlement ABI topic mismatch")
 raw=l.get("data","")
 if len(raw)!=2+64*3:raise ValueError("Settlement ABI data mismatch")
 v=[int(raw[2+i*64:2+(i+1)*64],16) for i in range(3)]
 if v[0] not in (0,1) or v[1] not in (0,1):raise ValueError("Bad bool ABI")
 return {"kind":"settled","id":t[1],"bondRecipient":addr_topic(t[2]),"disputed":bool(v[0]),
         "settlementResolution":bool(v[1]),"settleCaller":"0x"+format(v[2],"040x"),
         "tx":l["transactionHash"],"block":hexuint(l["blockNumber"]),
         "log_index":hexuint(l["logIndex"]),"oracle":l["address"].lower()}
def parse_disputed(l):
 t=l.get("topics",[])
 if len(t)!=4 or t[0].lower()!=DISPUTED:raise ValueError("Disputed ABI mismatch")
 return {"kind":"disputed","id":t[1],"caller":addr_topic(t[2]),
         "disputer":addr_topic(t[3]),"tx":l["transactionHash"],
         "block":hexuint(l["blockNumber"]),"log_index":hexuint(l["logIndex"])}
def parse_crv_transfer(l):
 t=l.get("topics",[])
 if len(t)!=3 or t[0].lower()!=TRANSFER or addr_topic(t[1])!=CONVEX_BOOSTER:
  raise ValueError("wrong outbound CRV transfer")
 if l["address"].lower()!=CRV or len(l.get("data",""))!=66:raise ValueError("invalid token transfer ABI")
 return {"kind":"transfer","to":addr_topic(t[2]),"from":CONVEX_BOOSTER,
         "amount_wei":hexuint(l["data"]),"tx":l["transactionHash"],
         "block":hexuint(l["blockNumber"]),"log_index":hexuint(l["logIndex"])}
def fee(receipt):
 base=hexuint(receipt["gasUsed"])*hexuint(receipt["effectiveGasPrice"])
 l1=hexuint(receipt["l1Fee"]) if isinstance(receipt.get("l1Fee"),str) else None
 return {"tx_gas_wei":base,"l1_fee_wei":l1,
         "reported_total_fee_wei":base+(l1 or 0),
         "l1_completeness":"PRESENT" if l1 is not None else "NOT_REPORTED"}
def token_transfers(receipt,token,from_addr,to_addr):
 acc=0
 for l in receipt.get("logs",[]):
  t=l.get("topics",[])
  if l.get("address","").lower()!=token.lower() or len(t)!=3 or t[0].lower()!=TRANSFER:continue
  if addr_topic(t[1])==from_addr.lower() and addr_topic(t[2])==to_addr.lower():
   acc+=hexuint(l["data"])
 return acc
def decode_assertion(raw):
 if not isinstance(raw,str) or len(raw)<2+16*64:raise ValueError("getAssertion not 16 words")
 v=[raw[2+i*64:2+(i+1)*64] for i in range(16)]
 return {"asserter":addr_from_word(v[5]),"currency":addr_from_word(v[8]),
         "disputer":addr_from_word(v[15]),"assertionTime":int(v[6],16),
         "expirationTime":int(v[9],16),"bond_raw":int(v[13],16),
         "settled":bool(int(v[7],16)),"settlementResolution":bool(int(v[10],16)),
         "validateDisputers":bool(int(v[2],16)),
         "escalationManager":addr_from_word(v[4])}
def inspect_settlement(ch,event,disputes):
 out={"id":event["id"],"block":event["block"],"recipient":event["bondRecipient"],
      "disputed":event["disputed"],"resolution":event["settlementResolution"],
      "status":"UNRESOLVED"}
 try:
  oracle=UMA_OOV3[ch]
  assertion=decode_assertion(call(ch,oracle,GET_ASSERTION_SELECTOR,event["id"][2:],event["block"]))
  burned=hexuint(call(ch,oracle,BURN_SELECTOR,"",event["block"]))
  tx=read(ch,"eth_getTransactionByHash",[event["tx"]])
  receipt=read(ch,"eth_getTransactionReceipt",[event["tx"]])
  if not tx or not receipt or hexuint(receipt["status"])!=1:raise ValueError("bad settlement receipt")
  if assertion["disputer"]=="0x"+"0"*40:raise ValueError("settled with no dispute despite disputed flag")
  if not event["disputed"]:raise ValueError("non-dispute settlement excluded from forfeiture economics")
  if burned>10**18:raise ValueError("invalid burnedBondPercentage")
  bond=assertion["bond_raw"]
  predicted=(bond*2)-(bond*burned//10**18)
  paid=token_transfers(receipt,assertion["currency"],oracle,event["bondRecipient"])
  resolutionRecipient=assertion["asserter"] if event["settlementResolution"] else assertion["disputer"]
  winner=(event["bondRecipient"]==resolutionRecipient)
  matched=(paid==predicted and paid>0 and winner)
  out.update({"assertion":assertion,"burned_fraction_x1e18":burned,
       "recipient_measured_token_transfer_raw":paid,
       "expected_bond_payout_raw":predicted,
       "winner_transfer_matches_source_code":matched,
       "winner_profit_in_bond_token_before_gas_and_lockup_raw":paid-bond if matched else None,
       "winning_side":"disputer" if event["bondRecipient"]==assertion["disputer"] else "asserter",
       "settlement_tx_from":tx["from"].lower(),"settlement_fee":fee(receipt),
       "historic_disputer_event_found_in_frozen_log_windows":event["id"] in disputes,
       "disputer_capital_unfundable_atomically":True,
       "cash_status":"HISTORIC_WINNER_BOND_PAYOUT_CONFIRMED" if matched else "UNRESOLVED_PAYOUT",
       "status":"RECEIPT_CHECKED"})
 except Exception as ex:out["error_type"]=type(ex).__name__
 save()
 return out
def settle_chain(ch):
 label="ethereum" if ch==1 else "base"
 entry={"windows":[],"events":[],"by_type":{},"receipts":[],"complete":False}
 RPT["chains"].setdefault(label,{})["uma"]=entry
 if hexuint(read(ch,"eth_chainId",[]))!=ch:raise ValueError("wrong chain")
 head=hexuint(read(ch,"eth_blockNumber",[]))-8
 pin=header(ch,head)
 entry["pin"]=pin
 oracle=UMA_OOV3[ch]
 if read(ch,"eth_getCode",[oracle,hex(head)])=="0x":raise ValueError("oracle contract absent")
 selected=[]
 for win in windows(head):
  rec={**win,"status":"UNRESOLVED","count":None}
  entry["windows"].append(rec)
  try:
   logs=read(ch,"eth_getLogs",[{"address":oracle,"topics":[[DISPUTED,SETTLED]],
                   "fromBlock":hex(win["start"]),"toBlock":hex(win["end"])}])
   rec["status"]="OK";rec["count"]=len(logs)
   for l in logs:
    ev=parse_disputed(l) if l["topics"][0].lower()==DISPUTED else parse_settled(l)
    selected.append(ev)
   entry["events"]=selected[:500]
  except Exception as ex:
   rec["error_type"]=type(ex).__name__
   if isinstance(ex,RPCFailure):
    rec["failure_kind"]=ex.kind
    if SESSIONS[ch].aborted:break
  save()
 cnt=Counter(x["kind"] for x in selected)
 entry["by_type"]=dict(cnt)
 disputes={x["id"]:x for x in selected if x["kind"]=="disputed"}
 settlements=[x for x in selected if x["kind"]=="settled" and x["disputed"]]
 entry["disputed_settlements"]=len(settlements)
 for event in sorted(settlements,key=lambda x:(x["block"],x["log_index"]))[:MAX_UMA_SETTLEMENTS_PER_CHAIN]:
  entry["receipts"].append(inspect_settlement(ch,event,disputes))
 entry["pin_rechecked"]=header(ch,head)["hash"]==pin["hash"]
 entry["complete"]=entry["pin_rechecked"] and all(x["status"]=="OK" for x in entry["windows"])
 save()
def quoter(ch,amount,predecessor):
 # Legacy Uniswap V3 Quoter ETH mainnet fee3000 direct CRV->WETH.
 calldata=addrword(CRV)+addrword(WETH)+word(3000)+word(amount)+word(0)
 raw=call(ch,UNISWAP_QUOTER_V1,QUOTER_SELECTOR,calldata,predecessor)
 if len(raw)!=66:raise ValueError("quoter unexpected output")
 return hexuint(raw)
def convex_run():
 ch=1;label="ethereum"
 entry={"windows":[],"sample_transfers":[],"tested_transactions":[],"complete":False}
 RPT["chains"].setdefault(label,{})["convex"]=entry
 if hexuint(read(ch,"eth_chainId",[]))!=1:raise ValueError("wrong chain")
 head=hexuint(read(ch,"eth_blockNumber",[]))-8
 pin=header(ch,head);entry["pin"]=pin
 for addr in [CONVEX_BOOSTER,CRV,UNISWAP_QUOTER_V1]:
  if read(ch,"eth_getCode",[addr,hex(head)])=="0x":raise ValueError("contract not deployed")
 all_logs=[]
 for win in windows(head):
  w={**win,"status":"UNRESOLVED"}
  entry["windows"].append(w)
  try:
   logs=read(ch,"eth_getLogs",[{"address":CRV,
         "topics":[TRANSFER,"0x"+addrword(CONVEX_BOOSTER)],
         "fromBlock":hex(win["start"]),"toBlock":hex(win["end"])}])
   w["count"]=len(logs);w["status"]="OK"
   for log in logs:all_logs.append(parse_crv_transfer(log))
  except Exception as ex:
   w["error_type"]=type(ex).__name__
   if isinstance(ex,RPCFailure):w["failure_kind"]=ex.kind
   if SESSIONS[ch].aborted:break
  save()
 entry["total_CRV_transfers_outgoing"]=len(all_logs)
 entry["distinct_txs"]=len(set(x["tx"] for x in all_logs))
 entry["sample_transfers"]=all_logs[:300]
 cnt=Counter(x["to"] for x in all_logs)
 entry["unique_recipients"]=len(cnt)
 entry["top_recipient_event_share"]=max(cnt.values())/len(all_logs) if all_logs else None
 earliest={}
 for l in sorted(all_logs,key=lambda a:(a["block"],a["log_index"])):
  earliest.setdefault(l["tx"],l)
 for trans in list(earliest.values())[:MAX_CONVEX_RECEIPTS]:
  row={"tx":trans["tx"],"block":trans["block"],"status":"UNRESOLVED"}
  entry["tested_transactions"].append(row)
  try:
   tx=read(ch,"eth_getTransactionByHash",[trans["tx"]])
   rec=read(ch,"eth_getTransactionReceipt",[trans["tx"]])
   if not tx or not rec or hexuint(rec["status"])!=1:raise ValueError("bad harvest receipt")
   actor=tx["from"].lower();target=str(tx.get("to","")).lower()
   paid=token_transfers(rec,CRV,CONVEX_BOOSTER,actor)
   row.update({"tx_to":target,"tx_sender":actor,"tx_selector":str(tx.get("input",""))[:10].lower(),
     "receipt":fee(rec),"CRV_direct_transfer_to_sender_raw":paid,
     "observed_booster_transfer_count":len([x for x in rec["logs"]
                   if x.get("address","").lower()==CRV and x.get("topics",[]) and
                    x["topics"][0].lower()==TRANSFER])})
   direct=target==CONVEX_BOOSTER and row["tx_selector"]==EARMARK_SELECTOR and paid>0
   row["source_direct_earmark_sender_cash"]=direct
   row["booster_crv_transferred_to_tx_sender"]=paid>0
   if direct:
    try:
     weth=quoter(ch,paid,trans["block"]-1)
     row["historic_CRV_sale_to_WETH_predecessor_quote_wei"]=weth
     row["conditional_net_WETH_wei_after_170k_swap_gas"]=weth-row["receipt"]["reported_total_fee_wei"]-INCREMENTAL_SWAP_GAS*hexuint(rec["effectiveGasPrice"])
     row["quote_is_counterfactual_not_onchain_swap"]=True
    except Exception as ex:row["quote_error"]=type(ex).__name__
   row["status"]=("DIRECT_EARMARK_SENDER_REWARD" if direct
                 else "BOOSTER_REWARD_TO_TX_SENDER_NOT_DIRECT_CALL" if paid>0
                 else "NO_BOOSTER_REWARD_TO_TX_SENDER")
  except Exception as ex:row["error_type"]=type(ex).__name__
  save()
 # Batch temporal necessity: distinct transactions in <=6 consecutive blocks.
 eligible=[x for x in entry["tested_transactions"] if x["status"]=="DIRECT_SENDER_REWARD_CONFIRMED"]
 clusters=[]
 for x in eligible:
  others=[z for z in eligible if z["tx"]!=x["tx"] and 0<=z["block"]-x["block"]<=6]
  if others:clusters.append({"first":x["tx"],"nearby_count":len(others)+1,
              "IMPORTANT":"nearby incumbent transactions alone do not prove simultaneous prewinner availability"})
 entry["nearby_harvest_clusters"]=clusters[:12]
 entry["pin_rechecked"]=header(ch,head)["hash"]==pin["hash"]
 entry["complete"]=entry["pin_rechecked"] and all(w["status"]=="OK" for w in entry["windows"])
 save()
def main():
 save()
 for ch,fn in [(1,convex_run),(1,lambda:settle_chain(1)),(8453,lambda:settle_chain(8453))]:
  try:fn()
  except Exception as ex:
   kind=ex.kind if isinstance(ex,RPCFailure) else type(ex).__name__
   RPT["errors"].append({"chain":ch,"kind":kind})
   if isinstance(ex,RPCFailure) and kind in ("AUTHENTICATED_RUN_RU_CAP_REACHED","RU_BUDGET_EXHAUSTED","AUTH_OR_ACCESS_DENIED","FIXED_HTTP_ATTEMPT_LIMIT"):
    break
  save()
 RPT["estimated_ru_used_conservative"]=BUDGET.attempted_ru if BUDGET else 0
 RPT["rpc_calls"]={("eth" if k==1 else "base"):v.attempted for k,v in SESSIONS.items()}
 RPT["complete"]=(len(RPT["chains"])==2 and
                  RPT["chains"]["ethereum"].get("convex",{}).get("complete",False) and
                  all(x.get("uma",{}).get("complete",False) for x in RPT["chains"].values()))
 RPT["stage2_ready"]=False
 save()
 print(json.dumps({"complete":RPT["complete"],"ru_attempts":RPT["estimated_ru_used_conservative"],
  "rpc_calls":RPT["rpc_calls"],"convex_txs":RPT["chains"].get("ethereum",{}).get("convex",{}).get("distinct_txs"),
  "uma_disputed_settlements":{ch:v.get("uma",{}).get("disputed_settlements") for ch,v in RPT["chains"].items()},
  "errors":RPT["errors"],"no_trades":True},sort_keys=True))
 return bool(RPT["complete"])
if __name__=="__main__":
 import sys
 sys.exit(0 if main() else 2)
