"""Programme III Stage1: ONE previously frozen historic Convex winner, no trading.

Target selected from archived earliest-twelve receipt investigation on 2026-10-19,
NOT a blind best-event search or prospective profit prediction. Only read-only
Blockmachine calls, 14 RU maximum; preserve 1500 RU monthly reserve.
"""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os
from Crypto.Hash import keccak
from qt_rpc.client import ReadOnlyRPC,AuthenticatedBudget,read_key_status,RPCFailure

TX="0x211f62115ec9c55f349b6fdd100f6e0c7bd6a45baad70f5e9340f8f64150db4f"
BLOCK=25941501
ACTOR="0x229965b0ee9ed33450317e6725edec3909dcd340"
BOOSTER="0xf403c135812408bfbe8713b5a23a04b3d48aae31"
CRV="0xd533a949740bb3306d119cc777fa900ba034cd52"
WETH="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
QUOTE="0xb27308f9f90d607463bb33ea1bebb41c27ce5ab6"
EXPECTED_CRV=78011436090499686987
EXPECTED_WETH=11379084255985277
EXPECTED_GAS=52618514415240
MAX_RU=14
FLOOR=1500
OUT=Path("convex_frozen_evidence")
def k(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
TRANSFER=k("Transfer(address,address,uint256)")
WITHDRAW=k("Withdrawal(address,uint256)")
FEE_CALL=k("earmarkIncentive()")[:10]
QUOTE_CALL=k("quoteExactInputSingle(address,address,uint24,uint256,uint160)")[:10]

def addr_topic(t):
 if not isinstance(t,str) or len(t)!=66:raise ValueError("bad indexed address")
 return "0x"+t[-40:].lower()
def as_uint(h):
 if not isinstance(h,str) or not h.startswith("0x"):raise ValueError("bad uint")
 return int(h,16)
def word(x):return format(int(x),"064x")
def verify_tx(tx,rc):
 if tx.get("hash","").lower()!=TX or rc.get("transactionHash","").lower()!=TX:
  raise ValueError("wrong frozen transaction hash")
 if as_uint(tx["blockNumber"])!=BLOCK or as_uint(rc["blockNumber"])!=BLOCK:
  raise ValueError("wrong fixed block")
 if tx["from"].lower()!=ACTOR or (tx.get("to") or "").lower()!=ACTOR:
  raise ValueError("actor mismatch")
 if as_uint(rc["status"])!=1:raise ValueError("transaction not successful")
 if as_uint(tx["transactionIndex"])!=0:raise ValueError("not first tx in block")
 crv_in=crv_out=weth_in=weth_out=0
 crv_from_booster=0
 for l in rc["logs"]:
  t=l.get("topics",[]);token=l.get("address","").lower()
  if token==CRV and len(t)==3 and t[0].lower()==TRANSFER:
   amount=as_uint(l["data"])
   src=addr_topic(t[1]);dst=addr_topic(t[2])
   if src==ACTOR:crv_out+=amount
   if dst==ACTOR:
    crv_in+=amount
    if src==BOOSTER:crv_from_booster+=amount
  if token==WETH and len(t)==3 and t[0].lower()==TRANSFER:
   src=addr_topic(t[1]);dst=addr_topic(t[2]);amount=as_uint(l["data"])
   if dst==ACTOR:weth_in+=amount
   if src==ACTOR:weth_out+=amount
  if token==WETH and len(t)==2 and t[0].lower()==WITHDRAW:
   if addr_topic(t[1])==ACTOR:weth_out+=as_uint(l["data"])
 gas=as_uint(rc["gasUsed"])*as_uint(rc["effectiveGasPrice"])
 return {"crv_booster_to_actor_wei":crv_from_booster,
         "crv_total_in_wei":crv_in,"crv_total_out_wei":crv_out,
         "weth_in_to_actor_wei":weth_in,"weth_out_including_unwrap_wei":weth_out,
         "gas_wei":gas,
         "receipt_earned_eth_minus_gas_wei":weth_out-gas,
         "closed_token_accounting":crv_in==crv_out==EXPECTED_CRV and weth_in==weth_out==EXPECTED_WETH,
         "original_receipt_matches_archive":crv_from_booster==EXPECTED_CRV and weth_out==EXPECTED_WETH and gas==EXPECTED_GAS,
         "receipt_gas_used":as_uint(rc["gasUsed"]),
         "receipt_effective_gas_price_wei":as_uint(rc["effectiveGasPrice"])}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 report={"hypothesis":"frozen winner really retained native ETH after reward conversion",
  "as_of":datetime.now(timezone.utc).isoformat(),
  "sample_selection":"the already selected 10th of 12 original Convex transactions; exploratory not holdout",
  "target":TX,"block":BLOCK,"chain":"ethereum",
  "max_authorized_ru":MAX_RU,"monthly_protected_floor":FLOOR,
  "status":"UNRESOLVED","capital_deployed_by_QT":0,"trades":0,
  "profit_repeatability_proved":False,"independent_capturability_proved":False}
 try:
  if os.environ.get("QT_ALLOW_AUTHENTICATED_RPC")!="YES" or os.environ.get("QT_PROVIDER_ACCOUNT_RIGHTS_CONFIRMED")!="YES":
   raise RPCFailure("AUTH_OR_ACCOUNT_USE_PERMISSION_MISSING")
  key=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
  if not key:raise RPCFailure("MISSING_SECRET")
  status=read_key_status(key)
  if status.get("ru_remaining",0)<FLOOR+MAX_RU:
   raise RPCFailure("INSUFFICIENT_REMAINING_RU_FOR_SMALL_AUDIT")
  budget=AuthenticatedBudget(status,reserve_floor=FLOOR,max_run_ru=MAX_RU,approved=True)
  rpc=ReadOnlyRPC(1,OUT/"rpc",api_key=key,status=status,budget=budget,
                   max_requests=13,max_attempts=1)
  report["ru_balance_before"]=status["ru_remaining"]
  report["ru_rate_limit"]=status["rate_limit_rpm"]
  if as_uint(rpc.rpc("eth_chainId",[]))!=1:raise ValueError("wrong chain")
  before=rpc.rpc("eth_getBlockByNumber",[hex(BLOCK-1),False])
  after=rpc.rpc("eth_getBlockByNumber",[hex(BLOCK),False])
  if as_uint(before["number"])!=BLOCK-1 or as_uint(after["number"])!=BLOCK:raise ValueError("wrong headers")
  report["canonical_parent_hash"]=before["hash"]
  report["canonical_block_hash"]=after["hash"]
  tx=rpc.rpc("eth_getTransactionByHash",[TX])
  receipt=rpc.rpc("eth_getTransactionReceipt",[TX])
  observed=verify_tx(tx,receipt)
  report.update(observed)
  code=rpc.rpc("eth_getCode",[ACTOR,hex(BLOCK-1)])
  report["historic_actor_code_hex_prefix"]=code[:54]
  report["historic_actor_code_byte_length"]=(len(code)-2)//2
  bal_parent=as_uint(rpc.rpc("eth_getBalance",[ACTOR,hex(BLOCK-1)]))
  bal_end=as_uint(rpc.rpc("eth_getBalance",[ACTOR,hex(BLOCK)]))
  delta=bal_end-bal_parent
  report["native_balance_delta_wei"]=delta
  report["native_balance_change_equals_reward_less_gas"]=(delta==observed["receipt_earned_eth_minus_gas_wei"])
  # Historical price checks for simple finite source quote and caller fee ratio.
  fee=rpc.rpc("eth_call",[{"to":BOOSTER,"data":FEE_CALL},hex(BLOCK-1)])
  report["historic_caller_fee_bps"]=as_uint(fee)
  inp=QUOTE_CALL+word(int(CRV,16))+word(int(WETH,16))+word(3000)+word(EXPECTED_CRV)+word(0)
  try:
   q=rpc.rpc("eth_call",[{"to":QUOTE,"data":inp},hex(BLOCK-1)])
   report["predecessor_crv_to_weth_quote_wei"]=as_uint(q)
   report["predecessor_quote_not_actual_trade"]=True
  except RPCFailure as exc:
   report["predecessor_quote_error_kind"]=exc.kind
  # Header recheck validates canonical pin for the immutable target block.
  again=rpc.rpc("eth_getBlockByNumber",[hex(BLOCK),False])
  report["canonical_header_rechecked"]=again["hash"]==after["hash"]
  report["conservative_ru_attempted"]=budget.attempted_ru
  report["requests_sent"]=rpc.attempted
  report["status"]=("CASH_RECONCILED" if observed["closed_token_accounting"] and
                   observed["original_receipt_matches_archive"] and
                   report["native_balance_change_equals_reward_less_gas"] and
                   report["canonical_header_rechecked"]
                   else "INCOMPLETE_OR_UNRECONCILED")
 except Exception as exc:
  report["status"]="UNRESOLVED"
  report["error_kind"]=exc.kind if isinstance(exc,RPCFailure) else type(exc).__name__
 (OUT/"REPORT.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
 safe={k:report.get(k) for k in ("status","native_balance_delta_wei","receipt_earned_eth_minus_gas_wei",
                                "native_balance_change_equals_reward_less_gas","conservative_ru_attempted",
                                "requests_sent","error_kind")}
 print(json.dumps(safe,sort_keys=True))
 return 0 if report["status"]=="CASH_RECONCILED" else 2
if __name__=="__main__":raise SystemExit(main())
