"""Programme III Stage 1: bounded read-only independent cash-inventory screen.
Three distinct mechanisms: (A) secondary savings shares -> primary redemption;
(B) market-bought Curve 3pool LP -> direct one-coin withdrawal; (C) Angle USDA
wind-down market acquisition -> USDC issuer redemption.
None of the outputs is an executed trade, full gas-net or proof of capturability.
No addresses are used to sign, fund, call write methods, or bypass providers.
"""
import hashlib,json,time,traceback,urllib.request,urllib.error
from pathlib import Path
from Crypto.Hash import keccak

OUT=Path("stage1_innovation_evidence");OUT.mkdir(exist_ok=True)
RPC="https://rpc-eth.blockmachine.io"
QUOTER="0x61ffe014ba17989e743c5f6cb21bf9697530b21e"
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDS="0xdc035d45d973e3ec169d2276ddab16f1e407384f"
DAI="0x6b175474e89094c44da98b954eedeac495271d0f"
SUSDS="0xa3931d71877c0e7a3148cb7eb4463524fec27fbd"
SDAI="0x83f20f44975d03b1b09e64809b757c47f942beea"
THREE_POOL="0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7"
THREE_CRV="0x6c3f90f043a72fa612cbac8115ee7e52bde6e490"
USDA="0x0000206329b97db379d5e1bf586bbdb969c63274"
ANGLE="0x222222fd79264bbe280b4986f6fefbc3524d0137"
FEES=(100,500,3000); SIZES=(100,1000,10000)
MAX_CALLS=160; TIME_BUDGET=480
COUNT=0;START=time.monotonic();STOP=False

def save(path,object):
 p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(object,indent=2,sort_keys=True,default=str)+"\n")
def selector(sig):
 k=keccak.new(digest_bits=256);k.update(sig.encode());return k.hexdigest()[:8]
def word(x):return format(int(x),"064x")
def rawcall(to,signature,args,block,tag):
 payload="0x"+selector(signature)+"".join(word(x) for x in args)
 return rpc("eth_call",[{"to":to,"data":payload},hex(block)],tag)
def words(s):
 if not isinstance(s,str) or not s.startswith("0x") or len(s[2:])%64:
  raise ValueError("Invalid ABI words")
 return [int(s[i:i+64],16) for i in range(2,len(s),64)]
def value(to,signature,args,block,tag):
 result=words(rawcall(to,signature,args,block,tag))
 if len(result)!=1:raise ValueError("Unexpected output length for "+signature)
 return result[0]
def address(v):return "0x"+format(v,"040x")
def rpc(method,params,tag):
 global COUNT,STOP
 if STOP:raise RuntimeError("STOP: provider denied")
 if COUNT>=MAX_CALLS or time.monotonic()-START>TIME_BUDGET:raise RuntimeError("BOUNDED_BUDGET_EXHAUSTED")
 COUNT+=1; idx=COUNT; raw=b"";status={"n":idx,"method":method,"tag":tag}
 time.sleep(0.45)
 try:
  body=json.dumps({"jsonrpc":"2.0","id":idx,"method":method,"params":params},separators=(',',':')).encode()
  req=urllib.request.Request(RPC,body,{"Content-Type":"application/json","Accept":"application/json","User-Agent":"QT-Stage1-Independent-Economics"})
  with urllib.request.urlopen(req,timeout=20) as reply:
   status["http_status"]=reply.status;raw=reply.read(850000)
  obj=json.loads(raw)
  if obj.get("error"):raise ValueError("JSON_RPC_ERROR "+str(obj["error"])[:300])
  if "result" not in obj:raise ValueError("RPC_RESULT_MISSING")
  status["valid_result"]=True
  return obj["result"]
 except urllib.error.HTTPError as e:
  status["http_status"]=e.code;raw=e.read(30000)
  if e.code in (401,403,429):STOP=True;status["stop_provider"]=True
  status["error"]=repr(e)
  raise
 except Exception as e:status["error"]=repr(e);raise
 finally:
  status["sha256"]=hashlib.sha256(raw).hexdigest();status["bytes"]=len(raw)
  (OUT/"raw").mkdir(exist_ok=True);(OUT/"raw"/f"{idx:03d}.body").write_bytes(raw)
  save(f"requests/{idx:03d}.json",status)

def exact_quote(token_in,token_out,amount,fee,block):
 data=words(rawcall(QUOTER,"quoteExactInputSingle((address,address,uint256,uint24,uint160))",
   (int(token_in,16),int(token_out,16),amount,fee,0),block,"V3_full_amount_single_quote"))
 if len(data)<4:raise ValueError("QuoterV2 must return 4 words")
 if data[0]<=0:raise ValueError("Zero quote")
 return data[0]
def record(case,report):
 report["cases"].append(case);save("REPORT.json",report)
def savings(block,report):
 for name,share,base in [("sUSDS",SUSDS,USDS),("sDAI",SDAI,DAI)]:
  row={"family":"ERC4626_SECONDARY_VS_IMMEDIATE_REDEMPTION","symbol":name,
       "share":share,"base":base,"block":block,"quote_grid":[],"permission":"UNVERIFIED_SIMULATED_BENEFICIARY"}
  record(row,report)
  try:
   actual_asset=address(value(share,"asset()",(),block,"ERC4626_actual_asset"))
   row["asset_onchain"]=actual_asset
   if actual_asset!=base:raise ValueError("TOKEN_MISMATCH")
   share_dec=value(share,"decimals()",(),block,"ERC4626_share_decimals")
   base_dec=value(base,"decimals()",(),block,"underlying_decimals")
   row["decimals"]={"share":share_dec,"base":base_dec}
   if share_dec>24 or base_dec>24:raise ValueError("unreasonable decimals")
   row["total_assets_raw"]=str(value(share,"totalAssets()",(),block,"vault_total_assets"))
   for size in SIZES:
    for fee in FEES:
     q={"buy_base_units":size,"v3_fee":fee};row["quote_grid"].append(q)
     try:
      shares=exact_quote(base,share,size*10**base_dec,fee,block)
      redeemed=value(share,"previewRedeem(uint256)",(shares,),block,"ERC4626_fee_aware_redeem")
      q.update(quote_shares_raw=str(shares),preview_redeem_raw=str(redeemed),
         gross_base_raw=str(redeemed-size*10**base_dec),
         gross_base_units=(redeemed-size*10**base_dec)/10**base_dec,
         status="QUOTE_ONLY_NOT_EXECUTED")
     except Exception as ex:q.update(status="NO_FULL_SIZE_QUOTE",error=repr(ex))
     save("REPORT.json",report)
     if STOP:raise RuntimeError("Provider denial")
  except Exception as ex:row["error"]=repr(ex);save("REPORT.json",report)
  if STOP:raise RuntimeError("Provider denial")
def curve_lp(block,report):
 row={"family":"BUY_MARKET_LP_AND_REDEEM_UNDERLYING","lp":THREE_CRV,
      "pool":THREE_POOL,"block":block,"quote_grid":[]}
 record(row,report)
 for size in SIZES:
  for fee in FEES:
   q={"buy_usdc":size,"v3_fee":fee};row["quote_grid"].append(q)
   try:
    shares=exact_quote(USDC,THREE_CRV,size*10**6,fee,block)
    returned=value(THREE_POOL,"calc_withdraw_one_coin(uint256,int128)",(shares,1),
      block,"Curve_3pool_USDC_single_coin_cash")
    q.update(lp_shares_raw=str(shares),estimated_usdc_raw=str(returned),
      gross_usdc_raw=str(returned-size*10**6),
      gross_usdc=(returned-size*10**6)/1e6,status="QUOTE_ONLY_NOT_EXECUTED")
   except Exception as e:q.update(status="NO_FULL_SIZE_QUOTE",error=repr(e))
   save("REPORT.json",report)
   if STOP:raise RuntimeError("Provider denial")
def angle(block,report):
 row={"family":"USDA_WINDDOWN_ACQUIRE_THEN_REDEEM","block":block,"quote_grid":[],
  "issuer_contract":ANGLE,"asset":USDA,"redeem_to":USDC}
 record(row,report)
 try:
  if address(value(ANGLE,"agToken()",(),block,"verify_USDA_token"))!=USDA:raise ValueError("USDA_NOT_MATCH")
  row["burn_paused"]=bool(value(ANGLE,"isPaused(address,uint8)",(int(USDC,16),1),block,"burn_paused"))
  row["usdc_whitelisted_only"]=bool(value(ANGLE,"isWhitelistedCollateral(address)",(int(USDC,16),),block,"USDC_whitelist"))
  row["reserve_usdc_raw"]=str(value(USDC,"balanceOf(address)",(int(ANGLE,16),),block,"issuer_USDC_reserve"))
  if row["burn_paused"] or row["usdc_whitelisted_only"]:
   row["gate"]="ISSUER_REDEMPTION_NOT_OPEN";save("REPORT.json",report);return
  for size in (100,1000,5000):
   for fee in FEES:
    q={"spend_usdc":size,"v3_fee":fee};row["quote_grid"].append(q)
    try:
     acquired=exact_quote(USDC,USDA,size*10**6,fee,block)
     cash=value(ANGLE,"quoteIn(uint256,address,address)",(acquired,int(USDA,16),int(USDC,16)),
      block,"issuer_USDC_burn_cash_quote")
     q.update(acquired_USDA_raw=str(acquired),redeem_USDC_raw=str(cash),
        available_reserve=bool(cash<=int(row["reserve_usdc_raw"])),
        gross_usdc_raw=str(cash-size*10**6),
        gross_usdc=(cash-size*10**6)/1e6,
        status="QUOTE_ONLY_NOT_EXECUTED")
    except Exception as ex:q.update(status="NO_FULL_SIZE_QUOTE",error=repr(ex))
    save("REPORT.json",report)
    if STOP:raise RuntimeError("Provider denial")
 except Exception as ex:row["error"]=repr(ex);save("REPORT.json",report)
 if STOP:raise RuntimeError("Provider denial")
def main():
 report={"version":"S1_INNOVATION_READONLY_V1","asof_utc":"2026-10-19",
 "design":"Two frozen snapshots: latest safe block minus 2; earlier snapshot minus 9000; three independent primary cash inventories; 3 UniswapV3 fee tiers; size sweep 100/1k/10k (Angle 100/1k/5k).",
 "live_trades":False,"full_EVM_execution":False,"current_capturable_profit_proven":False,
 "warnings":["Every value a read-only static quote, NOT trade outcome",
  "Issuer/share payouts not proven by funded caller state and actual wallet receipt",
  "No flash funding, transaction payload, competition cost or gas accounted",
  "Unsupported V3 market or price limits may produce missing quote; do not call negative",
  "A quote near a snapshot is NOT available before the original transaction/pool adjustment",
  "Each protocol and sample requires current availability, fees, contract permissions and total producer cost",
  "Do not sum gross positive alternatives without grouping same pool/inventory/timestamp"],
 "snapshots":[],"cases":[],"complete":False,"requests":0}
 save("REPORT.json",report)
 try:
  if int(rpc("eth_chainId",[],"chain_identity"),16)!=1:raise ValueError("Not Ethereum mainnet")
  tip=int(rpc("eth_blockNumber",[],"bounded_safe_tip"),16)-2
  for block in (tip,tip-9000):
   header=rpc("eth_getBlockByNumber",[hex(block),False],"frozen_header")
   report["snapshots"].append({"block":block,"block_hash":header["hash"],"timestamp":int(header["timestamp"],16)})
   save("REPORT.json",report)
   savings(block,report)
   curve_lp(block,report)
   angle(block,report)
  report["complete"]=True
 except Exception as ex:report["error"]=repr(ex);report["traceback"]=traceback.format_exc()
 report["requests"]=COUNT;report["provider_denied"]=STOP;save("REPORT.json",report)
 print(json.dumps({"complete":report["complete"],"requests":COUNT,"snapshots":report["snapshots"],
    "cases":[{"family":c["family"],"symbol":c.get("symbol"),"block":c["block"],
      "quotes":sum(1 for x in c["quote_grid"] if x["status"].startswith("QUOTE")),
      "positive":sum(1 for x in c["quote_grid"] if x.get("gross_usdc_raw") and int(x["gross_usdc_raw"])>0 or x.get("gross_base_raw") and int(x["gross_base_raw"])>0),
      "error":c.get("error")} for c in report["cases"]],"error":report.get("error")},indent=2))
 if not report["complete"]:raise SystemExit("Bounded empirical screen incomplete; preserve and report blocker")
if __name__=="__main__":main()
