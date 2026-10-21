"""QT Stage1: independently price the token obligation in a real Arc pay-first claim.

Source-fixed historical Arc transaction BEFORE outcomes of this test:
block 27,067,230; Uniswap launchpad burn token 0x7c7e...; 500000e18 tokens;
10e18 native USDC cash claim; original gas 0.5214597 native USDC.
Direct v4 exact-output quotes from the *same associated position pool* at
parent block, not spot midpoint and not a trade. No key/wallet/signing/trading.
A positive quote-only margin does not prove an executable callback, priority,
or that the historical actor purchased anything via this route.
"""
import json,hashlib,sys,time
from pathlib import Path
from datetime import datetime,timezone
from Crypto.Hash import keccak
import requests

RPC="https://rpc.mainnet.arc.io"
CHAIN=5042
PARENT=27067229
TARGET=27067230
TOKEN_ID=261639
BURN_TOKEN="0x7c7e04b8bc7e62ce801a84ad057dc7fa11794572"
BURN_SIZE=500000*10**18
CASH=10**19
ORIGINAL_GAS=521459700000000000
QUOTER="0x8dc178efb8111bb0973dd9d722ebeff267c98f94"
POSITION_MANAGER="0x6049c9a0e26405c0985f9e3685c87d0ae917f82b"
OUTPUT_QUANTITIES=[5000*10**18,50000*10**18,BURN_SIZE]
MAX_REQUESTS=14
OUT=Path("arc_exactoutput_evidence")
REPORT={"as_of":datetime.now(timezone.utc).isoformat(),
 "mechanism":"Native-USDC claim cash released before fixed token burn on Arc",
 "selection":"One fixed PR107 historical tx, before looking at predecessor v4 liquidity and quotes",
 "target_tx":"0xc62e40db737a4cc1ada1a357a1455e8b9531d84cd5baac48db17e26e83f6931d",
 "fixed_block":TARGET,"predecessor_block":PARENT,
 "source":"Uniswap official deployments; v4 IPositionManager, IV4Quoter",
 "token_id":TOKEN_ID,"burn_token":BURN_TOKEN,"required_token_burn_raw":str(BURN_SIZE),
 "observed_claim_native_usdc_raw":str(CASH),"observed_gas_native_usdc_raw":str(ORIGINAL_GAS),
 "remaining_before_buy_and_priority_raw":str(CASH-ORIGINAL_GAS),
 "unmeasured":["actual original executor token purchase","approved callback inventory",
  "gas change for own execution","private inclusion/fee-recipient payment",
  "liquidity on other routes","full historic native account transfers",
  "whether our own executor can get this claim first"],
 "requests":0,"status":"UNRESOLVED","trades":0,"authenticated_blockmachine_ru":0,
 "no_keys_used":True,"profit_verified":False,"market_liquidity_measured":False}
def save():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"REPORT.json").write_text(json.dumps(REPORT,indent=2,sort_keys=True)+"\n")
def sig(text):
 h=keccak.new(digest_bits=256);h.update(text.encode());return "0x"+h.hexdigest()[:8]
def word(n):
 if n<0:n=(1<<256)+n
 if n<0 or n>=1<<256:raise ValueError("ABI word overflow")
 return format(n,"064x")
def unit(x):
 if not isinstance(x,str) or not x.startswith("0x"):raise ValueError("not hex quantity")
 return int(x,16)
def signed24(raw_word):
 v=int(raw_word,16)
 return v-(1<<256) if v>=1<<255 else v
def addr_word(raw_word):
 if len(raw_word)!=64 or int(raw_word[:24],16):raise ValueError("non canonical address")
 return "0x"+raw_word[-40:].lower()
def poolkey_decode(hex_value):
 if not isinstance(hex_value,str) or len(hex_value)<2+64*6:raise ValueError("pool key missing")
 parts=[hex_value[2+i*64:2+(i+1)*64]for i in range(6)]
 k={"currency0":addr_word(parts[0]),"currency1":addr_word(parts[1]),
    "fee":int(parts[2],16),"tickSpacing":signed24(parts[3]),"hooks":addr_word(parts[4]),
    "positionInfo_raw":parts[5]}
 if not 0<=k["fee"]<=1000000 or not -32768<=k["tickSpacing"]<=32767:
  raise ValueError("unreasonable pool parameters")
 return k
def encode_exact_output(pool,amount):
 # ABI: quoteExactOutputSingle(((address,address,uint24,int24,address),bool,uint128,bytes)).
 # Single dynamic tuple offset (0x20). Tuple head five pool-key words,
 # direction, uint128 amount, hookData offset (0x100); tail length=0.
 if amount>=1<<128 or amount<=0:raise ValueError("bad size")
 expected=pool["currency1"]==BURN_TOKEN and pool["currency0"]=="0x"+"0"*40
 if not expected:raise ValueError("not a native-USDC -> burn-token v4 pool")
 params=[int(pool["currency0"],16),int(pool["currency1"],16),pool["fee"],
         pool["tickSpacing"],int(pool["hooks"],16),1,amount,8*32]
 return sig("quoteExactOutputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))")+word(32)+"".join(word(x) for x in params)+word(0)
def parse_quote(v):
 if not isinstance(v,str) or len(v)!=2+128:raise ValueError("bad IV4Quoter output")
 raw=v[2:];price=int(raw[:64],16);gas=int(raw[64:],16)
 if price<=0:raise ValueError("quote not positive")
 return {"required_input_native_USDC_raw":str(price),
         "quoter_estimated_simulation_gas_not_execution_cost":gas,
         "usdc_per_token_for_this_quantity":str(price/(BURN_SIZE if price else 1))}
def rpc(method,args):
 if REPORT["requests"]>=MAX_REQUESTS:raise RuntimeError("PUBLIC_RPC_CAP")
 idx=REPORT["requests"];REPORT["requests"]+=1
 request={"jsonrpc":"2.0","id":idx+1,"method":method,"params":args}
 b=json.dumps(request,separators=(",",":")).encode()
 try:
  resp=requests.post(RPC,data=b,timeout=(10,28),allow_redirects=False,
                     headers={"Accept":"application/json","Content-Type":"application/json"})
  body=resp.content
  if len(body)>1400000:raise RuntimeError("RESPONSE_OVERSIZE")
  OUT.mkdir(exist_ok=True,parents=True)
  (OUT/(f"{idx:02}.request")).write_bytes(b)
  (OUT/(f"{idx:02}.response")).write_bytes(body)
  REPORT.setdefault("request_hashes",[]).append({
   "method":method,"http_status":resp.status_code,
   "request_sha256":hashlib.sha256(b).hexdigest(),
   "response_sha256":hashlib.sha256(body).hexdigest()})
  save()
  if resp.status_code in (401,403,429):raise RuntimeError("PUBLIC_ACCESS_"+str(resp.status_code))
  if resp.status_code!=200:raise RuntimeError("HTTP_"+str(resp.status_code))
  j=resp.json()
  if not isinstance(j,dict) or j.get("error") or "result" not in j:
   raise RuntimeError("RPC_JSON_ERROR_"+str(j.get("error",{}).get("code","na") if isinstance(j,dict) else "na"))
  return j["result"]
 finally:time.sleep(1.0)
def main():
 save()
 try:
  if unit(rpc("eth_chainId",[]))!=CHAIN:raise RuntimeError("CHAIN_MISMATCH")
  parent=rpc("eth_getBlockByNumber",[hex(PARENT),False])
  if not parent or unit(parent["number"])!=PARENT:raise RuntimeError("PARENT_MISSING")
  REPORT["parent_hash"]=parent["hash"]
  for a,tag in [(QUOTER,"quoter"),(POSITION_MANAGER,"position_manager")]:
   code=rpc("eth_getCode",[a,hex(PARENT)])
   if not isinstance(code,str) or code in ("0x","0x0"):
    raise RuntimeError(tag.upper()+"_NOT_DEPLOYED")
  p=rpc("eth_call",[{"to":POSITION_MANAGER,
     "data":sig("getPoolAndPositionInfo(uint256)")+word(TOKEN_ID)},hex(PARENT)])
  pool=poolkey_decode(p);REPORT["position_pool_key"]=pool
  REPORT["same_burn_token"]=pool["currency1"]==BURN_TOKEN
  REPORT["native_usdc_currency0"]=pool["currency0"]=="0x"+"0"*40
  if not REPORT["same_burn_token"] or not REPORT["native_usdc_currency0"]:
   raise RuntimeError("POOL_KEY_NOT_EXPECTED_NATIVE_BURN_PAIR")
  decimals=rpc("eth_call",[{"to":BURN_TOKEN,"data":sig("decimals()")},hex(PARENT)])
  REPORT["token_decimals"]=unit(decimals)
  if REPORT["token_decimals"]!=18:raise RuntimeError("BURN_TOKEN_DECIMALS_DIFFER")
  REPORT["quoted_sizes"]=[]
  for amount in OUTPUT_QUANTITIES:
   row={"requested_burn_token_raw":str(amount),
       "requested_tokens":str(amount//10**18),"state":"UNRESOLVED"}
   REPORT["quoted_sizes"].append(row)
   try:
    quote=rpc("eth_call",[{"to":QUOTER,"data":encode_exact_output(pool,amount)},hex(PARENT)])
    row.update(parse_quote(quote));row["state"]="QUOTE_RETRIEVED"
    row["budget_residual_after_original_gas_raw"]=str(CASH-ORIGINAL_GAS-int(row["required_input_native_USDC_raw"]))
    row["gross_after_original_gas_positive"]=int(row["budget_residual_after_original_gas_raw"])>0
   except Exception as e:
    row["error_kind"]=str(e)[:90] if "RPC_JSON_ERROR" in str(e) else type(e).__name__
    row["state"]="QUOTE_UNAVAILABLE"
   save()
  header=rpc("eth_getBlockByNumber",[hex(PARENT),False])
  REPORT["canonical_pin_rechecked"]=header["hash"]==parent["hash"]
  full=REPORT["quoted_sizes"][-1]
  REPORT["market_liquidity_measured"]=full["state"]=="QUOTE_RETRIEVED"
  REPORT["profit_verified"]=False
  REPORT["status"]="FINITE_500K_DIRECT_V4_QUOTE_OBSERVED" if full["state"]=="QUOTE_RETRIEVED" and REPORT["canonical_pin_rechecked"] else "FULL_BURN_ROUTE_UNRESOLVED"
 except Exception as e:
  REPORT["status"]="UNRESOLVED"
  REPORT["error_kind"]=str(e)[:100] if str(e).startswith("PUBLIC_ACCESS_") else type(e).__name__
 save()
 print(json.dumps({"status":REPORT["status"],"requests":REPORT["requests"],
   "burn_cost_quotes":REPORT.get("quoted_sizes"),
   "position_pool_key":REPORT.get("position_pool_key"),
   "error":REPORT.get("error_kind"),"no_trades":True,"blockmachine_ru":0},sort_keys=True))
 return 0 if REPORT["status"]=="FINITE_500K_DIRECT_V4_QUOTE_OBSERVED" else 2
if __name__=="__main__":sys.exit(main())