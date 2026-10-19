"""Frozen historical winner's actual seized collateral and exact debt obligation:
compare real Uniswap V3 direct and two-hop counterfactual cash quotes. READ ONLY.

Must NOT call a winner's resulting price quote independent capture or live profit.
"""
import json,traceback,time,datetime,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fluid_stage1 import screen as S

OUT=Path("fluid_multihop_evidence");OUT.mkdir(exist_ok=True)
WETH="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT="0xdac17f958d2ee523a2206206994597c13d831ec7"
WBTC="0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
GHO="0x40d16fc0246ad3160ccc09b8d0d3a2cd28ae6c2f"
ETH_ALIAS="0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
# Distinct genuine original winners. Frozen from full 21 Fluid LogLiquidate census.
CASES=[
 {"name":"USDT_ETH","vault":"0xe16a6f5359abb1f61ce71e25dd0932e3e00b00eb",
  "tx":"0xc14dfce64a6951236742ea7807bedbb54b703c21c09495f1366836cfed056eff","block":26193309,
  "debt":6082140927,"collateral":2556269438992378210},
 {"name":"USDT_AssetD","vault":"0x92643e964ca4b2c165a95ca919b0a819aca6d5f1",
  "tx":"0x620d083d030d5826e2c19d64e2b5f8327598ced7b7f6a78d811f1ab58dfbff54","block":26194906,
  "debt":272033908,"collateral":106823970197468997},
 {"name":"cbBTC_wstETH","vault":"0x6e0cdb09eb33cd3894c905e0dff9289b95a86fff",
  "tx":"0x5e503dad7122fe296acf61ef865347fe28228470d79cc7e6cc981b6367255424","block":26194919,
  "debt":77740,"collateral":21820762053493686}
]
# Actual first event per eligible vault. A/B were multi-asset, not a fungible ERC20-to-debt path.
# Their original events are retained in QT_Fluid_Events_20261019 and QT_Fluid_Five_Cash_20261019.
FEES=[100,500,3000]
BRIDGES=[WETH,USDC,WBTC]
def save(obj): (OUT/"REPORT.json").write_text(json.dumps(obj,indent=2)+"\n")
def norm(tok):return WETH if tok==ETH_ALIAS else tok
def dynamic_path(assets,fees):
 if len(assets)!=len(fees)+1 or len(fees)!=2:raise ValueError("Two-hop only")
 if any(int(x,16)==0 or len(x)!=42 for x in assets):raise ValueError("Malformed token")
 if any(x not in FEES for x in fees):raise ValueError("Unapproved fee")
 path=bytes.fromhex(assets[0][2:])
 for fee,token in zip(fees,assets[1:]):path+=fee.to_bytes(3,"big")+bytes.fromhex(token[2:])
 return path
def quote_path(path,qty,block,basefee):
 # QuoterV2.quoteExactInput(bytes,uint256), bytes @ offset 64
 pad_len=32*((len(path)+31)//32)
 calldata=S.sig("quoteExactInput(bytes,uint256)")+S.u(64)+S.u(qty)+S.u(len(path))+path.hex().ljust(pad_len*2,'0')
 resp=S.ethcall(1,S.QUOTER[1],calldata,block,basefee,"quoted_multi_hop_cash_exit")
 vals=S.decode_words(resp)
 if not vals or vals[0]<0:raise ValueError("Invalid multi-hop return")
 return vals[0]
def original_liquidation(receipt,e):
 if not receipt or receipt.get("status")!="0x1" or int(receipt["blockNumber"],16)!=e["block"]:
  raise ValueError("Wrong original receipt")
 # canonical event log has full keccak topic, NOT the 4-byte function selector
 from Crypto.Hash import keccak
 h=keccak.new(digest_bits=256);h.update(b"LogLiquidate(address,uint256,uint256,address)")
 topic="0x"+h.hexdigest()
 matches=[l for l in receipt["logs"] if l["address"].lower()==e["vault"] and l["topics"] and l["topics"][0].lower()==topic]
 if len(matches)!=1:raise ValueError("Ambiguous original liquidation event")
 w=S.decode_words(matches[0]["data"])
 if len(w)!=4 or w[1]!=e["collateral"] or w[2]!=e["debt"]:
  raise ValueError("Source numbers do not match canonical chain event")
 return {"sender":receipt["from"].lower(),"gas_wei":str(int(receipt["gasUsed"],16)*int(receipt["effectiveGasPrice"],16)),
  "gas_used":int(receipt["gasUsed"],16),"tx":e["tx"],"block":e["block"],"collateral_raw":str(w[1]),"debt_raw":str(w[2])}
def main():
 report={"research_only":True,"scope":"Three real original Fluid liquidation collateral inventories converted into debt asset, direct and two-hop V3",
   "case_selection":"First genuine first-by-vault winner among single-token quoteable vaults, frozen independently before routes",
   "gross_quoted_profit_not_earned":True,"actual_cash_execution":False,
   "no_wallet_signing_or_broadcast":True,"cases":[],"finished":False,
   "warnings":["Counterfactual quote at full block immediately AFTER winner may include winner's swaps",
     "Quote at predecessor block may predate triggering transaction/oracle",
     "Original gas and builder bid cannot be carried over as expected alternative cost",
     "Input token can be ETH native requiring a wrap gas and real liquidity for execution",
     "A route with positive quote must be replayed with real token inventory, repayments, and producer compensation",
     "No synthetic balance/funding overrides, all attempts read canonical production state"]}
 save(report)
 try:
  if int(S.request(1,"eth_chainId",[],"chain_id"),16)!=1:raise ValueError("Not Ethereum")
  for entry in CASES:
   row=dict(entry);row["quote_samples"]=[];report["cases"].append(row);save(report)
   receipt=S.request(1,"eth_getTransactionReceipt",[entry["tx"]],"winner_receipt")
   row["original_winner"]=original_liquidation(receipt,entry)
   for block in (entry["block"]-1,entry["block"]):
    state={"block":block,"when":"predecessor" if block<entry["block"] else "winning_block_post_state",
      "route_quotes":[]}
    row["quote_samples"].append(state);save(report)
    try:
     hdr=S.request(1,"eth_getBlockByNumber",[hex(block),False],"historical_header")
     basefee=int(hdr["baseFeePerGas"],16);state["hash"]=hdr["hash"]
     liq=S.liquidate_view(1,row["vault"],0,block,basefee)
     state["resolver_debt_token"]=liq["token0_in"]
     state["resolver_collateral_token"]=liq["token0_out"]
     if any(int(liq[key],16) for key in ("token1_in","token1_out")):
      state["case_invalid"]="NOT_SIMPLE_SINGLE_TOKEN";continue
     debt=liq["token0_in"]
     collateral=liq["token0_out"]
     if not debt or not collateral:raise ValueError("Missing token identities")
     for tier in FEES:
      q={"type":"direct","fee":tier};state["route_quotes"].append(q)
      try:
       out=S.quote(1,norm(collateral),norm(debt),entry["collateral"],tier,block,basefee)
       q.update(out_debt_raw=str(out),gross_debt_raw=str(out-entry["debt"]),positive_before_cost=bool(out>entry["debt"]))
      except Exception as ex:q["error"]=repr(ex)
      save(report)
      if 1 in S.DENIED:raise RuntimeError("Stop on provider denial")
     for bridge in BRIDGES:
      if bridge in (norm(collateral),norm(debt)):continue
      for fees in ((500,500),(3000,500),(500,3000)):
       q={"type":"two_hop","bridge":bridge,"fees":list(fees)}
       state["route_quotes"].append(q)
       try:
        path=dynamic_path([norm(collateral),bridge,norm(debt)],fees)
        out=quote_path(path,entry["collateral"],block,basefee)
        q.update(out_debt_raw=str(out),gross_debt_raw=str(out-entry["debt"]),
          positive_before_cost=bool(out>entry["debt"]))
       except Exception as ex:q["error"]=repr(ex)
       save(report)
       if 1 in S.DENIED:raise RuntimeError("Stop on provider denial")
    except Exception as ex:state["error"]=repr(ex)
    save(report)
    if 1 in S.DENIED:raise RuntimeError("Stop after rate-limit or access denial")
  report["finished"]=True
 except Exception as ex:report["error"]=repr(ex);report["traceback"]=traceback.format_exc()
 report["requests"]=S.COUNT;report["denied_chains"]=sorted(S.DENIED);save(report)
 print(json.dumps({"finished":report["finished"],"requests":report["requests"],
  "cases":[{"name":c["name"],"states":[{"when":s["when"],"status":s.get("case_invalid"),
    "quote_count":len(s["route_quotes"]),"positive_quote":sum(bool(q.get("positive_before_cost")) for q in s["route_quotes"])} for s in c["quote_samples"]]} for c in report["cases"]],"error":report.get("error")},indent=2),flush=True)
 if not report["finished"]:raise SystemExit("Incomplete read-only market quote screen")
if __name__=="__main__":main()
