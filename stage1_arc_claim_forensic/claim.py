"""QT Stage1 targeted Arc Uniswap buyback real executed transaction cash audit.

Source preselected from 2026-10-21 PR105 six-window public sample.
Uses ONLY public read-only Arc mainnet JSONRPC. No secret, signing, swaps,
balances transferred or key. Record native Arc USDC (NOT ETH) in wei units.
"""
from datetime import datetime,timezone
from pathlib import Path
from Crypto.Hash import keccak
import requests,json,hashlib,time,sys
RPC="https://rpc.mainnet.arc.io"
CHAIN=5042
BLOCK=27067230
TX="0xc62e40db737a4cc1ada1a357a1455e8b9531d84cd5baac48db17e26e83f6931d"
RELEASER="0x5cee9852d136833ae26c9e36a96fc02cdfc9c40c"
BURN_ASSET="0x7c7e04b8bc7e62ce801a84ad057dc7fa11794572"
TOKEN_ID=261639
BURN_AMOUNT=500000*10**18
OUT=Path("stage1_arc_burn_forensic")
REQUEST_CAP=14
def sig(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return "0x"+h.hexdigest()
BURN_TOPIC=sig("TokensBurned(uint256,address,uint256)")
CLAIM_TOPIC=sig("Claimed(uint256,uint256,uint256,(address,address,uint24,int24,address))")
TRANSFER_TOPIC=sig("Transfer(address,address,uint256)")
AMOUNT_SELECTOR=sig("amounts(uint256)")[:10]
BURN_SELECTOR=sig("minCurrency1BurnAmount()")[:10]
RPT={"as_of_utc":datetime.now(timezone.utc).isoformat(),
     "transaction":TX,"block":BLOCK,"chain":CHAIN,
     "selection":"First (and only) TokensBurned in predeclared PR105 Arc three-window sample",
     "source":"Uniswap/liquidity-launcher IClaimableRecipient + BaseClaimRecipientWithCallback + BuybackAndBurnClaimRecipient",
     "status":"UNRESOLVED","fee_currency":"Arc native USDC (18 decimals gas asset)",
     "no_transaction_submitted":True,"blockmachine_ru":0,
     "profit_found":False,
     "unpriced":["burn token liquidity at predecessor block","conversions and counterparties",
                 "buyer access, callback route and competitive inclusion",
                 "all native value transfers if callTracer unsupported"]}
def save():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(RPT,sort_keys=True,indent=2)+"\n")
def read(method,params):
 if RPT.get("request_count",0)>=REQUEST_CAP:raise RuntimeError("READ_ONLY_RPC_CAP")
 num=RPT.get("request_count",0)
 request={"jsonrpc":"2.0","id":num+1,"method":method,"params":params}
 body=json.dumps(request,separators=(",",":")).encode()
 RPT["request_count"]=num+1
 id=str(num).zfill(2)
 raw=b""
 try:
  response=requests.post(RPC,data=body,
    headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"QT-Stage1-PublicOnly/1"},
    timeout=(10,30),allow_redirects=False)
  raw=response.content
  if len(raw)>2_000_000:raise RuntimeError("OVERSIZE_RPC")
  (OUT/(id+".request")).write_bytes(body)
  (OUT/(id+".response")).write_bytes(raw)
  RPT.setdefault("request_hashes",[]).append({
   "method":method,"http":response.status_code,"req_sha256":hashlib.sha256(body).hexdigest(),
   "resp_sha256":hashlib.sha256(raw).hexdigest(),"utc":datetime.now(timezone.utc).isoformat()})
  save()
  if response.status_code in (401,403,429):raise RuntimeError("PUBLIC_ACCESS_"+str(response.status_code))
  if response.status_code!=200:raise RuntimeError("HTTP_"+str(response.status_code))
  payload=response.json()
  if not isinstance(payload,dict) or payload.get("error") or "result" not in payload:
   raise RuntimeError("RPC_JSON_ERROR")
  return payload["result"]
 finally:time.sleep(1.25)
def u(x):
 if isinstance(x,str) and x.startswith("0x"):return int(x,16)
 if isinstance(x,int) and x>=0:return x
 raise ValueError("BAD_HEX_UINT")
def ad(t):
 if not isinstance(t,str) or len(t)!=66:raise ValueError("BAD_TOPIC_ADDRESS")
 return "0x"+t[-40:].lower()
def parse_receipt(r):
 if u(r["status"])!=1 or r["transactionHash"].lower()!=TX or u(r["blockNumber"])!=BLOCK:
  raise ValueError("FROZEN_RECEIPT_MISMATCH")
 claimed=[];burns=[];erc20dead=[]
 for l in r.get("logs",[]):
  topics=l.get("topics",[]);p=l.get("data","")
  if not topics:continue
  if l.get("address","").lower()==RELEASER and topics[0].lower()==BURN_TOPIC:
   if len(topics)!=3 or len(p)!=66:raise ValueError("BURN_ABI_MISMATCH")
   burns.append({"token_id":u(topics[1]),"token":ad(topics[2]),"amount":u(p)})
  if l.get("address","").lower()==RELEASER and topics[0].lower()==CLAIM_TOPIC:
   if len(topics)!=2 or len(p)!=2+7*64:raise ValueError("CLAIM_ABI_MISMATCH")
   vals=[p[2+k*64:2+(k+1)*64] for k in range(7)]
   claimed.append({"token_id":u(topics[1]),"payout_native_USDC_wei":int(vals[0],16),
                   "other_token_payout_raw":int(vals[1],16),
                   "currency0":"0x"+vals[2][-40:],"currency1":"0x"+vals[3][-40:]})
  if l.get("address","").lower()==BURN_ASSET and topics[0].lower()==TRANSFER_TOPIC and len(topics)==3 and len(p)==66:
   if ad(topics[2])=="0x000000000000000000000000000000000000dead":
    erc20dead.append({"from":ad(topics[1]),"amount":u(p)})
 return {"burn_events":burns,"claims":claimed,"burn_asset_transfers_to_dead":erc20dead,
  "gas_native_USDC_wei":u(r["gasUsed"])*u(r["effectiveGasPrice"]),
  "gas_used":u(r["gasUsed"]),"effective_gas_price_native_wei":u(r["effectiveGasPrice"]),
  "l1_fee_native_wei":u(r["l1Fee"]) if isinstance(r.get("l1Fee"),str) else None}
def main():
 save()
 try:
  if u(read("eth_chainId",[]))!=CHAIN:raise RuntimeError("CHAIN_NOT_ARC")
  block=read("eth_getBlockByNumber",[hex(BLOCK),False])
  if u(block["number"])!=BLOCK:raise RuntimeError("WRONG_PIN")
  RPT["canonical_block_hash"]=block["hash"]
  RPT["block_fee_recipient"]=str(block.get("miner","")).lower()
  tx=read("eth_getTransactionByHash",[TX])
  receipt=read("eth_getTransactionReceipt",[TX])
  if not isinstance(tx,dict) or not isinstance(receipt,dict) or tx["hash"].lower()!=TX:
   raise RuntimeError("ORIGINAL_TX_NOT_RETURNED")
  RPT["transaction_sender"]=tx["from"].lower()
  RPT["transaction_destination"]=str(tx.get("to") or "").lower()
  RPT["tx_index"]=u(tx["transactionIndex"])
  RPT.update(parse_receipt(receipt))
  RPT["fixed_burn_event_matches_preselected"]=any(
   x["token_id"]==TOKEN_ID and x["token"]==BURN_ASSET and x["amount"]==BURN_AMOUNT
   for x in RPT["burn_events"])
  RPT["actual_transfer_to_dead_matches_event"]=any(x["amount"]==BURN_AMOUNT for x in RPT["burn_asset_transfers_to_dead"])
  RPT["claim_native_payout_attribution"]=[x for x in RPT["claims"] if x["token_id"]==TOKEN_ID]
  RPT["source_specific_native_currency_is_USDC"]=True
  # Supply preceding-state accrual as a diagnostic, not necessarily the
  # claim payout: the transaction itself may collect/release before claiming.
  last=read("eth_call",[{"to":RELEASER,"data":AMOUNT_SELECTOR+format(TOKEN_ID,"064x")},hex(BLOCK-1)])
  if isinstance(last,str) and len(last)==130:
   RPT["position_accrued_before_block_native_raw"]=str(int(last[2:66],16))
   RPT["position_accrued_before_block_token_raw"]=str(int(last[66:130],16))
  prev=read("eth_call",[{"to":RELEASER,"data":BURN_SELECTOR},hex(BLOCK-1)])
  RPT["historical_burn_threshold_raw"]=str(u(prev))
  RPT["burn_threshold_matches_event"]=u(prev)==BURN_AMOUNT
  # Check both external tx sender and executor contract because one may
  # control an account while the other receives assets.
  accounts=sorted(set((RPT["transaction_sender"],RPT["transaction_destination"])))
  for account in accounts:
   if not account.startswith("0x") or len(account)!=42:continue
   b=u(read("eth_getBalance",[account,hex(BLOCK-1)]))
   a=u(read("eth_getBalance",[account,hex(BLOCK)]))
   RPT.setdefault("account_block_native_delta_raw",{})[account]=str(a-b)
  # Short-cost trace may be unsupported on public Arc; avoid retries and
  # NEVER infer zero native payments from a missing trace.
  try:
   trace=read("debug_traceTransaction",[TX,{"tracer":"callTracer","timeout":"20s"}])
   if isinstance(trace,dict):
    RPT["trace_available"]=True
    RPT["trace_frame_type"]=trace.get("type")
    RPT["trace_top_value_raw"]=str(u(trace.get("value","0x0")))
   else:RPT["trace_available"]=False
  except Exception as e:
   RPT["trace_available"]=False
   RPT["trace_error_class"]=type(e).__name__
  RPT["status"]="BURN_AND_CLAIM_CASH_EVIDENCE" if (
    RPT["fixed_burn_event_matches_preselected"] and
    RPT["actual_transfer_to_dead_matches_event"] and
    len(RPT["claim_native_payout_attribution"])>=1
  ) else "UNRESOLVED_EVENT_CASH"
 except Exception as e:
  RPT["status"]="INCOMPLETE_RETRIEVAL"
  RPT["error_kind"]=str(e)[:75] if "PUBLIC_ACCESS" in str(e) else type(e).__name__
 save()
 print(json.dumps({"status":RPT["status"],"requests":RPT.get("request_count"),
  "claim":RPT.get("claim_native_payout_attribution"),
  "burn_transfer_verified":RPT.get("actual_transfer_to_dead_matches_event"),
  "sender_native_delta":RPT.get("account_block_native_delta_raw"),
  "trace_available":RPT.get("trace_available"),"error":RPT.get("error_kind"),
  "no_trades":True,"blockmachine_ru":0},sort_keys=True))
 return 0 if RPT["status"]=="BURN_AND_CLAIM_CASH_EVIDENCE" else 2
if __name__=="__main__":sys.exit(main())
