"""QT Stage1: Cash from claiming OTHER PEOPLE'S prizes, not owning prize tickets.

Source addresses/ABIs officially pinned before looking at cash outcomes.
Claims create PrizePool INTERNAL reward credit. Only withdrawal plus matching
ERC20 transfer is terminal token cash. No wallets, claims, sales or tx signed.
"""
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timezone
from Crypto.Hash import keccak as keccak_module
from qt_rpc.client import ReadOnlyRPC, AuthenticatedBudget, WeightedLimiter, read_key_status, RPCFailure
import json,os

OUT=Path("prize_cash_evidence")
DEPLOYED={
 1:{"chain":"ethereum",
  "pool":"0x7865d01da4c9ba2f69b7879e6d2483ab6b354d95",
  "claimer":"0x54aa02cbc223fc834949fb1fd8c855e4da126c7d"},
 8453:{"chain":"base",
  "pool":"0x45b2010d8a4f08b53c9fa7544c51dfd9733732cb",
  "claimer":"0xcdce635b774de77cdf791647601dba64a75547ba"}
}
WINDOW_LENGTH=4000
OFFSETS=[150,11000,37000,100000,270000]
MAX_TX_PER_CHAIN=7
MAX_FEE_QUOTE_ORIGINAL_TX=2
BATCH_SIZES=[1,2,4,8]
RU_BUDGET=365
RESERVE=1500
BUDGET=None;RATE=None;STATUS=None;RPC={}
def keccak(s):
 h=keccak_module.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
CLAIM=keccak("ClaimedPrize(address,address,address,uint24,uint8,uint32,uint152,uint96,address)")
WITHDRAW=keccak("WithdrawRewards(address,address,uint256,uint256)")
TRANSFER=keccak("Transfer(address,address,uint256)")
PRIZE_TOKEN=keccak("prizeToken()")[:10]
CLAIM_FEES=keccak("computeTotalFees(uint8,uint256)")[:10]
REPORT={
 "date_utc":datetime.now(timezone.utc).isoformat(),
 "hypothesis":"External caller may earn a portion of someone else's expiring prize by fulfilling the claiming service",
 "cash_source":"PoolTogether V5 Claimer + PrizePool internal fee-credit settlement",
 "frozen_design":{
  "addresses":DEPLOYED,"windows_blocks":WINDOW_LENGTH,"end_offsets":OFFSETS,
  "max_unique_transactions_audited_per_chain":MAX_TX_PER_CHAIN,
  "fee_quote_from_first_successful_events":MAX_FEE_QUOTE_ORIGINAL_TX,
  "quote_batch_sizes":BATCH_SIZES,"max_conservative_RU":RU_BUDGET,
  "monthly_reserved_RU":RESERVE},
 "scope":{
  "not_opportunity_profit":"Receipt success or credit to reward account is NOT token cash in hand.",
  "no_live_claiming":True,"no_accounts":True,"no_wallets_or_signatures":True,
  "no_price_parity_assumption":True,"max_8bit_tiers":False,
  "read_only":True},
 "chain_results":{},"errors":[],"complete":False,
 "trades":0,"stage2_ready":False}
def save():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(REPORT,sort_keys=True,indent=2,default=str)+"\n")
def u(v):
 if not isinstance(v,str) or not v.startswith("0x"):raise ValueError("invalid uint hex")
 return int(v,16)
def word(n):return format(int(n),"064x")
def addr(s):
 if not isinstance(s,str) or len(s)!=66:raise ValueError("invalid topic address")
 return "0x"+s[-40:].lower()
def check_logs(l):
 raw=l.get("data","")
 return isinstance(raw,str) and raw.startswith("0x") and len(raw)%64==2
def read(ch,method,args):
 global STATUS,RATE,BUDGET
 if ch not in RPC:
  if os.environ.get("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES":
   raise RPCFailure("PROVIDER_ACCOUNT_USE_NOT_CONFIRMED")
  if os.environ.get("QT_ALLOW_AUTHENTICATED_RPC")!="YES":
   raise RPCFailure("AUTHENTICATED_RU_NOT_APPROVED")
  key=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
  if not key:raise RPCFailure("NO_BEARER_TOKEN_SECRET")
  if STATUS is None:
   STATUS=read_key_status(key)
   if STATUS["auth"]!="authenticated" or STATUS.get("ru_remaining",0)<RESERVE+RU_BUDGET:
    raise RPCFailure("STATUS_OR_RU_RESERVE_BLOCKER")
   RATE=WeightedLimiter(cap_ru=max(5,int(STATUS["rate_limit_rpm"]*.55)))
   BUDGET=AuthenticatedBudget(STATUS,reserve_floor=RESERVE,max_run_ru=RU_BUDGET,approved=True)
   REPORT["starting_RU_status"]={k:STATUS.get(k) for k in ["ru_remaining","ru_budget","rate_limit_rpm"]}
   save()
  RPC[ch]=ReadOnlyRPC(ch,OUT/DEPLOYED[ch]["chain"]/"raw_RPC",
          status=STATUS,api_key=key,budget=BUDGET,limiter=RATE,max_attempts=2,max_requests=125)
 return RPC[ch].rpc(method,args)
def pin(ch,b):
 res=read(ch,"eth_getBlockByNumber",[hex(b),False])
 if not isinstance(res,dict) or u(res.get("number","0x0"))!=b:raise ValueError("missing pinned header")
 return {"number":b,"hash":res["hash"],"timestamp":u(res["timestamp"])}
def decode_claim(l):
 t=l.get("topics",[])
 if len(t)!=4 or t[0].lower()!=CLAIM or not check_logs(l) or len(l["data"])!=2+6*64:
  raise ValueError("ClaimedPrize exact ABI mismatch")
 vals=[int(l["data"][2+i*64:2+(i+1)*64],16) for i in range(6)]
 return {"type":"claim","tx":l["transactionHash"],"block":u(l["blockNumber"]),
    "log_index":u(l["logIndex"]),"vault":addr(t[1]),"winner":addr(t[2]),
    "recipient":addr(t[3]),"drawId":vals[0],"tier":vals[1],
    "prizeIndex":vals[2],"payout_raw":vals[3],
    "claim_fee_credit_raw":vals[4],
    "claim_fee_recipient":"0x"+format(vals[5],"040x")}
def decode_withdraw(l):
 t=l.get("topics",[])
 if len(t)!=3 or t[0].lower()!=WITHDRAW or len(l.get("data",""))!=2+2*64:
  raise ValueError("WithdrawRewards exact ABI mismatch")
 raw=l["data"]
 return {"type":"withdraw","tx":l["transactionHash"],"block":u(l["blockNumber"]),
  "log_index":u(l["logIndex"]),"account":addr(t[1]),"to":addr(t[2]),
  "amount_raw":int(raw[2:66],16),"available_before_raw":int(raw[66:130],16)}
def check_transfer(rec,prize_token,pool,beneficiary):
 paid=0
 for ev in rec.get("logs",[]):
  t=ev.get("topics",[])
  if ev.get("address","").lower()!=prize_token or len(t)!=3 or t[0].lower()!=TRANSFER:continue
  if addr(t[1])==pool and addr(t[2])==beneficiary:
   paid+=u(ev["data"])
 return paid
def gas(rec):
 used=u(rec["gasUsed"]);price=u(rec["effectiveGasPrice"])
 return {"gas_used":used,"effective_gas_price_wei":price,"gas_wei":used*price,
         "l1_fee_wei":u(rec["l1Fee"]) if isinstance(rec.get("l1Fee"),str) else None}
def fee_table(ch,claimer,tier,block):
 out=[]
 for n in BATCH_SIZES:
  raw=read(ch,"eth_call",[{"to":claimer,"data":CLAIM_FEES+word(tier)+word(n)},hex(block)])
  if len(raw)!=66:raise ValueError("fee quote non-single uint")
  out.append({"n":n,"total_claim_fee_raw":u(raw),"average_fee_raw":u(raw)//n})
 return out
def chain_run(ch):
 meta=DEPLOYED[ch];pool=meta["pool"];claimer=meta["claimer"]
 item={"chain_id":ch,"windows":[],"claims_sample":[],"withdrawals_sample":[],
       "cash_receipts":[],"fee_slope_quotes":[],"complete":False}
 REPORT["chain_results"][meta["chain"]]=item
 if u(read(ch,"eth_chainId",[]))!=ch:raise ValueError("chain identity mismatch")
 head=u(read(ch,"eth_blockNumber",[]))-8
 state=pin(ch,head);item["anchor"]=state
 for contract in [pool,claimer]:
  if read(ch,"eth_getCode",[contract,hex(head)])=="0x":raise ValueError("missing deployed code")
 token_data=read(ch,"eth_call",[{"to":pool,"data":PRIZE_TOKEN},hex(head)])
 if len(token_data)!=66:raise ValueError("prizeToken() invalid")
 token="0x"+token_data[-40:].lower()
 item["prize_token_address"]=token
 if read(ch,"eth_getCode",[token,hex(head)])=="0x":raise ValueError("prize currency code missing")
 claims=[];withdrawals=[]
 for offset in OFFSETS:
  b=head-offset
  w={"start":b-WINDOW_LENGTH+1,"end":b,"offset":offset,"state":"UNRESOLVED"}
  item["windows"].append(w)
  if w["start"]<0:raise ValueError("window before genesis")
  try:
   logs=read(ch,"eth_getLogs",[{"address":pool,"topics":[[CLAIM,WITHDRAW]],
                 "fromBlock":hex(w["start"]),"toBlock":hex(w["end"])}])
   w["claim_count"]=0;w["withdraw_count"]=0
   for ev in logs:
    if ev["address"].lower()!=pool:raise ValueError("wrong contract emitting")
    if ev["topics"][0].lower()==CLAIM:
     claims.append(decode_claim(ev));w["claim_count"]+=1
    elif ev["topics"][0].lower()==WITHDRAW:
     withdrawals.append(decode_withdraw(ev));w["withdraw_count"]+=1
    else:raise ValueError("unexpected topic0")
   w["state"]="OK"
  except Exception as exc:
   w["error_type"]=type(exc).__name__
   if isinstance(exc,RPCFailure):
    w["error_kind"]=exc.kind
    if RPC[ch].aborted:break
  save()
 item["claim_count"]=len(claims);item["withdraw_count"]=len(withdrawals)
 item["positive_fee_claim_count"]=sum(x["claim_fee_credit_raw"]>0 for x in claims)
 item["total_claim_fee_credits_raw"]=sum(x["claim_fee_credit_raw"] for x in claims)
 item["unique_fee_recipients"]=len({x["claim_fee_recipient"] for x in claims if x["claim_fee_credit_raw"]>0})
 counts=Counter(x["claim_fee_recipient"] for x in claims if x["claim_fee_credit_raw"]>0)
 item["top_fee_recipient_share"]=max(counts.values())/sum(counts.values()) if counts else None
 item["claimed_credits_by_tier"]={str(t):sum(x["claim_fee_credit_raw"] for x in claims if x["tier"]==t) for t in sorted({x["tier"] for x in claims})}
 item["claims_sample"]=sorted(claims,key=lambda x:(x["block"],x["log_index"]))[:25]
 item["withdrawals_sample"]=sorted(withdrawals,key=lambda x:(x["block"],x["log_index"]))[:25]
 # The earliest unique transactions were chosen BEFORE looking at amounts.
 to_check=[];seen=set()
 for event in sorted(withdrawals,key=lambda x:(x["block"],x["log_index"])):
  if event["tx"].lower() in seen:continue
  seen.add(event["tx"].lower());to_check.append(event)
  if len(to_check)>=MAX_TX_PER_CHAIN:break
 for event in to_check:
  row={"tx":event["tx"],"status":"UNRESOLVED",
       "withdraw_event_amount_raw":event["amount_raw"],"to":event["to"],"account":event["account"]}
  item["cash_receipts"].append(row)
  try:
   rec=read(ch,"eth_getTransactionReceipt",[event["tx"]])
   tx=read(ch,"eth_getTransactionByHash",[event["tx"]])
   if not rec or not tx or u(rec["status"])!=1:raise ValueError("invalid receipt")
   paid=check_transfer(rec,token,pool,event["to"])
   row.update({"success":True,"tx_from":tx["from"].lower(),"gas":gas(rec),
               "token_from_pool_to_recipient_raw":paid,
               "matching_withdrawal_credit_realized":paid>=event["amount_raw"] and event["amount_raw"]>0,
               "sender_is_credited_account":tx["from"].lower()==event["account"],
               "zero_to_pool_no_transfer_by_design":event["to"]==pool})
   row["status"]="CASH_TOKEN_WITHDRAWAL_CONFIRMED" if row["matching_withdrawal_credit_realized"] else "NO_TERMINAL_TRANSFER_MATCH"
  except Exception as ex:row["error_type"]=type(ex).__name__
  save()
 # Historical fee quote at two selected winning-prize tx predecessor states;
 # independent of profit size and counts, not a claimable prewinner award inventory.
 claim_txs=[];seen=set()
 for event in sorted(claims,key=lambda x:(x["block"],x["log_index"])):
  if event["claim_fee_credit_raw"]<=0 or event["tx"] in seen:continue
  seen.add(event["tx"]);claim_txs.append(event)
  if len(claim_txs)>=MAX_FEE_QUOTE_ORIGINAL_TX:break
 for event in claim_txs:
  row={"tx":event["tx"],"tier":event["tier"],"block":event["block"],"state":"UNRESOLVED"}
  item["fee_slope_quotes"].append(row)
  try:
   row["quotes"]=fee_table(ch,claimer,event["tier"],event["block"]-1)
   row["state"]="HISTORIC_PREDECESSOR_QUOTES"
  except Exception as exc:row["error_type"]=type(exc).__name__
  save()
 item["anchor_recheck"]=pin(ch,head)["hash"]==state["hash"]
 item["complete"]=item["anchor_recheck"] and all(x["state"]=="OK" for x in item["windows"])
 save()
def main():
 save()
 for ch in DEPLOYED:
  try:chain_run(ch)
  except Exception as exc:
   kind=exc.kind if isinstance(exc,RPCFailure) else type(exc).__name__
   REPORT["errors"].append({"chain":ch,"kind":kind})
   if isinstance(exc,RPCFailure) and kind in ("AUTHENTICATED_RUN_RU_CAP_REACHED",
     "RU_BUDGET_EXHAUSTED","AUTH_OR_ACCESS_DENIED"):break
  save()
 REPORT["estimated_ru_used_attempts"]=BUDGET.attempted_ru if BUDGET else 0
 REPORT["rpc_calls"]={DEPLOYED[k]["chain"]:v.attempted for k,v in RPC.items()}
 REPORT["complete"]=len(REPORT["chain_results"])==len(DEPLOYED) and all(x["complete"] for x in REPORT["chain_results"].values())
 save()
 print(json.dumps({"complete":REPORT["complete"],"ru_attempts":REPORT["estimated_ru_used_attempts"],
  "calls":REPORT["rpc_calls"],"counts":{c:{"claims":v.get("claim_count"),"withdrawals":v.get("withdraw_count"),
   "confirmed_withdrawal_receipts":sum(z.get("status")=="CASH_TOKEN_WITHDRAWAL_CONFIRMED" for z in v["cash_receipts"])}
   for c,v in REPORT["chain_results"].items()},"errors":REPORT["errors"]},sort_keys=True))
if __name__=="__main__":main()
