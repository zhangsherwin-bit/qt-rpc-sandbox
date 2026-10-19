"""Repair a price-unit error in GHO GSM quote research.
GSM_USDC is Gsm4626 with ERC4626 VAULT SHARE underlying, not raw USDC.
No EVM execution/trading. Requires same-block previewMint(actual shares) input cost.
"""
import sys,json,datetime,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gho_stage1 import quote as Q

OUT=Path("gho_share_evidence");OUT.mkdir(exist_ok=True)
GSM="0x3a3868898305f04bec7fea77becff04c13444112"
BLOCKS=[26090422,26220131]
SHARES=[100,1000]
DEX_FEES=[100,500]
def save(x): (OUT/"REPORT.json").write_text(json.dumps(x,indent=2,default=str)+"\n")
def num(raw):
 words=Q.words(raw)
 if len(words)!=1:raise ValueError("Unexpected scalar ABI response")
 return words[0]
def call_scalar(name,to,signature,args,block,basefee):
 data=Q.sig(signature)+"".join(Q.u(x) for x in args)
 response=Q.read(name,"eth_call",[{"to":to,"data":data,"gasPrice":hex(basefee)},hex(block)])
 return num(response)
def call_address(name,to,signature,block,basefee):
 v=call_scalar(name,to,signature,[],block,basefee)
 if v>=2**160 or not v:raise ValueError("Invalid address")
 return "0x"+format(v,"040x")
def gsm_quote(shares,block,basefee):
 data=Q.sig("getGhoAmountForSellAsset(uint256)")+Q.u(shares)
 raw=Q.read("fee_inclusive_primary_shares_to_gho","eth_call",
    [{"to":GSM,"data":data,"gasPrice":hex(basefee)},hex(block)])
 val=Q.words(raw)
 if len(val)!=4:raise ValueError("GSM return is not four fee-inclusive values")
 return val
def main():
 report={"research_only":True,
    "hypothesis":"Prior $18 positive cash quote priced 100 ERC4626 shares at 100 raw USDC, omitting share acquisition cost",
    "source":"Aave GhoEthereum GSM_USDC address plus Gsm4626.sol underlying asset semantics",
    "samples":[],"complete":False,
    "all_profit_claims_require_real_cash_execution":True,
    "warnings":["previewMint is current ERC4626 quote, not executed share acquisition",
      "Uniswap V3 quote not a sequential shared-state executed trade",
      "Fees, failed bids and producer payment not included; only positive gross candidate for future testing",
      "No upfront token assumptions; actual cash funding cost is included in the candidate quote",
      "A historical executed fill or user capture probability is not implied"]}
 save(report)
 try:
  if int(Q.read("chainid","eth_chainId",[]),16)!=1:raise ValueError("Not Ethereum")
  for block in BLOCKS:
   h=Q.read("pinned_header","eth_getBlockByNumber",[hex(block),False])
   bfee=int(h["baseFeePerGas"],16)
   row={"block":block,"timestamp":datetime.datetime.fromtimestamp(int(h["timestamp"],16),datetime.timezone.utc).isoformat(),
     "hash":h["hash"],"quotes":[],"errors":[]}
   report["samples"].append(row);save(report)
   raw_gsm=Q.read("GSM_code","eth_getCode",[GSM,hex(block)])
   if raw_gsm=="0x":raise ValueError("GSM is not deployed")
   share=call_address("actual_vault_underlying_asset","0x3a3868898305f04bec7fea77becff04c13444112",
      "UNDERLYING_ASSET()",block,bfee)
   row["gsm_underlying_share_token"]=share
   if share==Q.USDC:raise ValueError("Unexpected raw USDC module, not ERC4626 shares")
   token_asset=call_address("ERC4626_underlying_asset",share,"asset()",block,bfee)
   row["share_vault_asset"]=token_asset
   if token_asset!=Q.USDC:raise ValueError("ERC4626 underlying asset not USDC; cannot compare dollar units")
   share_decimals=call_scalar("share_decimals",share,"decimals()",[],block,bfee)
   asset_decimals=call_scalar("asset_decimals",Q.USDC,"decimals()",[],block,bfee)
   if share_decimals>24 or asset_decimals!=6:raise ValueError("Unsupported share/asset decimals")
   row["share_decimals"]=share_decimals
   row["USDC_decimals"]=asset_decimals
   row["available_share_supply_raw"]=str(call_scalar("GSM_unused_exposure",GSM,"getAvailableUnderlyingExposure()",[],block,bfee))
   row["can_swap"]=bool(call_scalar("GSM_canSwap",GSM,"canSwap()",[],block,bfee))
   for units in SHARES:
    amount=units*10**share_decimals
    case={"requested_shares":units,"shares_raw":str(amount),"dex":[]}
    row["quotes"].append(case);save(report)
    try:
     actual_shares,gho_received,gross,fee_amt=gsm_quote(amount,block,bfee)
     if actual_shares<=0 or gho_received<=0:raise ValueError("Invalid module quote")
     usdc_cost=call_scalar("ERC4626_previewMint_actual_shares",share,"previewMint(uint256)",[actual_shares],block,bfee)
     redeemed=call_scalar("ERC4626_convertToAssets",share,"convertToAssets(uint256)",[actual_shares],block,bfee)
     case.update(actual_shares_raw=str(actual_shares),actual_usdc_mint_cost_raw=str(usdc_cost),
       usdc_share_value_raw=str(redeemed),gho_to_sell_raw=str(gho_received),
       primary_fee_gho_raw=str(fee_amt),cost_preview_only=True)
     if actual_shares>int(row["available_share_supply_raw"]):
      case["capacity"]="ABOVE_GSM_EXPOSURE_LIMIT";continue
     if not row["can_swap"]:
      case["capacity"]="GSM_SWAP_DISABLED";continue
     for tier in DEX_FEES:
      q={"dex_fee_tier":tier};case["dex"].append(q)
      try:
       dest=Q.quote_exact_input(gho_received,tier,block,bfee)
       margin=dest-usdc_cost
       q.update(secondary_USDC_raw=str(dest),full_funding_quote_USDC_raw=str(usdc_cost),
         gross_USDC_margin_raw=str(margin),positive_quote_only=bool(margin>0))
      except Exception as e:q["error"]=repr(e)
      save(report)
      if Q.stopped:raise RuntimeError("Provider refusal")
    except Exception as e:case["error"]=repr(e)
    save(report)
    if Q.stopped:raise RuntimeError("Provider refusal")
   chk=Q.read("recheck_block","eth_getBlockByNumber",[hex(block),False])
   if chk["hash"]!=h["hash"]:raise ValueError("Block changed")
   save(report)
  report["complete"]=True
 except Exception as e:report["error"]=repr(e);report["traceback"]=traceback.format_exc()
 report["rpc_requests"]=Q.count;report["provider_stopped"]=Q.stopped
 save(report)
 print(json.dumps({"complete":report["complete"],"requests":Q.count,
   "states":[{"block":x["block"],"share":x.get("gsm_underlying_share_token"),
    "quotes":len(x["quotes"]),"positive":sum(sum(q.get("positive_quote_only",False) for q in y.get("dex",[])) for y in x["quotes"])} for x in report["samples"]],"error":report.get("error")},indent=2),flush=True)
 if not report["complete"]:raise SystemExit("Partial evidence preserved; cannot label missing quotes zero")
if __name__=="__main__":main()
