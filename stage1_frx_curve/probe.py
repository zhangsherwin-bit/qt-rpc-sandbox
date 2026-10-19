"""Stage 1 frxUSD public Curve acquisition -> exact issuer USDC redemption route.
Three-leg genuine USDC-funded quote, no nominal stablecoin-par shortcut, no trades.
"""
import json, time, hashlib, urllib.request, urllib.error, sys, traceback
from pathlib import Path
from Crypto.Hash import keccak
from datetime import datetime,timezone
OUT=Path("frx_curve_evidence");OUT.mkdir(exist_ok=True)
RPC="https://rpc-eth.blockmachine.io"
THREE="0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"
FRXPOOL="0xD6937eA8D33B0C21348F36F7895FdE3054bA4927"
CUST="0x4F95C5bA0C7c69FB2f9340E190cCeE890B3bd87c"
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT="0xdac17f958d2ee523a2206206994597c13d831ec7"
FRX="0xcacd6fd266af91b8aed52accc382b4e165586e29"
SIZE_USDC=[100,1000,5000,25000]
BLOCK_OFFSETS=[4,7004,27004,77004]
RPT={"date":datetime.now(timezone.utc).isoformat(),"title":"Curve frxUSD secondary acquisition plus issuer primary USDC redemption",
     "economic_path":"USDC -> USDT Curve3pool -> frxUSD Curve NG -> USDC frxUSD Custodian",
     "contracts":{"threepool":THREE,"frxusdt_curve_ng":FRXPOOL,"frx_usdc_custodian":CUST},
     "cost_accounting":"Start with exactly nominal USDC amount actually spent in 3pool. Use true finite USDT and frxUSD outputs, previewRedeem fee-adjusted USDC. No assumption USDT=USDC or frxUSD at par.",
     "frozen_design":{"block_offsets":BLOCK_OFFSETS,"input_sizes_usdc":SIZE_USDC,"read_only":True},
     "rows":[],"failures":[],"rpc_count":0,"complete":False,
     "permissionless_claim_not_verified":True,"full_atomic_cash_execution_verified":False,
     "own_captured_profit":False,"no_trades_signed_or_sent":True}
DENIED=False
def save(): (OUT/"REPORT.json").write_text(json.dumps(RPT,indent=2,sort_keys=True,default=str)+"\n")
def sig(s):
 k=keccak.new(digest_bits=256);k.update(s.encode());return "0x"+k.hexdigest()[:8]
def word(v):return format(v,"064x")
def addr(v):return "0x"+v[-40:].lower()
def rpc(method,params):
 global DENIED
 if DENIED:raise RuntimeError("earlier HTTP denial; stopping")
 if RPT["rpc_count"]>=100:raise RuntimeError("fixed read-only RPC count cap")
 RPT["rpc_count"]+=1
 name=f'{RPT["rpc_count"]:03d}'
 body=json.dumps({"jsonrpc":"2.0","id":RPT["rpc_count"],"method":method,"params":params},sort_keys=True).encode()
 out=b"";status=-1
 try:
  time.sleep(.45)
  req=urllib.request.Request(RPC,data=body,headers={"Content-Type":"application/json","User-Agent":"QT-Stage1-ReadOnly"},method="POST")
  with urllib.request.urlopen(req,timeout=30) as f:
   status=f.status;out=f.read(1200000)
 except urllib.error.HTTPError as e:status=e.code;out=e.read(120000)
 finally:
  d=OUT/"raw";d.mkdir(exist_ok=True)
  (d/(name+".request.json")).write_bytes(body)
  (d/(name+".response.json")).write_bytes(out)
  (d/(name+".sha256")).write_text(hashlib.sha256(out).hexdigest()+"\n")
  save()
 if status in (401,403,429):DENIED=True;raise RuntimeError(f"provider HTTP {status}: stopped")
 if status!=200:raise RuntimeError(f"provider HTTP {status}")
 obj=json.loads(out)
 if "error" in obj:raise RuntimeError(str(obj["error"])[:350])
 if "result" not in obj:raise RuntimeError("missing RPC result")
 return obj["result"]
def ethcall(to,data,b):
 out=rpc("eth_call",[{"to":to,"data":data},hex(b)])
 if not isinstance(out,str) or not out.startswith("0x") or len(out)<66:raise ValueError("empty ABI return")
 return out
def unsigned(to,selector,values,b):
 out=ethcall(to,sig(selector)+"".join(word(x) for x in values),b)
 if len(out)!=66:raise ValueError("not one uint256 ABI return")
 return int(out,16)
def coins(pool,i,b):
 try:out=ethcall(pool,sig("coins(uint256)")+word(i),b)
 except Exception:out=ethcall(pool,sig("coins(int128)")+word(i),b)
 if len(out)!=66:raise ValueError("coins invalid result")
 return addr(out)
def snapshot(b):
 blk=rpc("eth_getBlockByNumber",[hex(b),False])
 if blk is None:raise ValueError("missing canonical header")
 return {"block":b,"hash":blk["hash"],"timestamp":int(blk["timestamp"],16)}
def main():
 save()
 try:
  if int(rpc("eth_chainId",[]),16)!=1:raise RuntimeError("Ethereum chain mismatch")
  tip=int(rpc("eth_blockNumber",[]),16)
  for offset in BLOCK_OFFSETS:
   b=tip-offset
   row={"anchor":snapshot(b),"candidate_checks":[],"route_supported":False}
   RPT["rows"].append(row)
   try:
    for contract in [THREE,FRXPOOL,CUST]:
     if rpc("eth_getCode",[contract,hex(b)])=="0x":raise RuntimeError(f"undeployed pool or custodian at {b}")
    c=[coins(THREE,1,b),coins(THREE,2,b),coins(FRXPOOL,0,b),coins(FRXPOOL,1,b)]
    row["coin_addresses"]=c
    if c!=[USDC.lower(),USDT.lower(),FRX.lower(),USDT.lower()]:
     raise RuntimeError("pool coin indexes failed on-chain verification")
    row["route_supported"]=True
    total=unsigned(CUST,"totalAssets()",[],b)
    reserve=unsigned(USDC,"balanceOf(address)",[int(CUST,16)],b)
    row["custodian_totalAssets_usdc_raw"]=total
    row["custodian_usdc_balance_raw"]=reserve
    for size in SIZE_USDC:
     case={"usdc_start":size,"usdc_start_raw":size*10**6,"raw_same_block_quotes_not_execution":True}
     row["candidate_checks"].append(case)
     try:
      usdt=unsigned(THREE,"get_dy(int128,int128,uint256)",[1,2,size*10**6],b)
      frx=unsigned(FRXPOOL,"get_dy(int128,int128,uint256)",[1,0,usdt],b)
      usdcout=unsigned(CUST,"previewRedeem(uint256)",[frx],b)
      case.update({"usdt_after_3pool_raw":usdt,"frx_after_curve_raw":frx,
             "usdc_if_redeemed_raw":usdcout,
             "usdc_gross_integer_raw":usdcout-size*10**6,
             "gross_usdc":(usdcout-size*10**6)/1e6,
             "issuer_usdc_balance_exceeds_preview":reserve>=usdcout,
             "cash_cap_and_rights_unproven":True,
             "gas_approvals_flash_cost_and_competition_unmeasured":True})
     except Exception as e:case["error"]=str(e)[:300]
     save()
   except Exception as e:row["state_error"]=str(e)[:350]
   save()
  # Recheck all observed pin hashes.
  for row in RPT["rows"]:
   again=rpc("eth_getBlockByNumber",[hex(row["anchor"]["block"]),False])
   row["anchor_rechecked"]=again["hash"]==row["anchor"]["hash"]
  RPT["complete"]=len(RPT["rows"])==len(BLOCK_OFFSETS) and all(r.get("anchor_rechecked") for r in RPT["rows"])
 except Exception as e:
  RPT["failures"].append({"error":str(e),"trace":traceback.format_exc(limit=3)})
 save()
 successes=[r["gross_usdc"] for state in RPT["rows"] for r in state["candidate_checks"] if "gross_usdc" in r]
 print(json.dumps({"complete":RPT["complete"],"observed_cash_quote_count":len(successes),
   "positive_gross_quotes":len([x for x in successes if x>0]),"max_gross_quote":max(successes) if successes else None,
   "failures":RPT["failures"],"calls":RPT["rpc_count"]}))
 if not RPT["complete"]:sys.exit(1)
if __name__=="__main__":main()
