"""Historical Fluid liquidation feasibility in five distinct REAL vaults.
Retrospective sample: first canonical event per unique vault in the 21-event census.
Read-only: no capital, transactions, code override, oracle or state mutation.
"""
import sys,json,datetime,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fluid_stage1 import screen as S
OUT=Path("fluid_five_evidence");OUT.mkdir(exist_ok=True)
ETH_ALIAS="0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
WETH="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
SOURCE=[
{"name":"vault_A","vault":"0x4095a3a8efe779d283102377669778900212d856","block":26171577,"tx":"0x8df6275317c089741feefc504da20e072a4b94a049f70a44c1d9215992fb724e","event_debt_raw":3515833067638873494},
{"name":"vault_B","vault":"0xe3cac7cc6b0eed28e16331f08be7948bbfcb5acc","block":26175052,"tx":"0x25bce41e379cd4ed4010186d7e0c496f4d86bad3ee0c209a0e71eb9a65359b8c","event_debt_raw":513319760647775193},
{"name":"vault_C","vault":"0xe16a6f5359abb1f61ce71e25dd0932e3e00b00eb","block":26193309,"tx":"0xc14dfce64a6951236742ea7807bedbb54b703c21c09495f1366836cfed056eff","event_debt_raw":6082140927},
{"name":"vault_D","vault":"0x92643e964ca4b2c165a95ca919b0a819aca6d5f1","block":26194906,"tx":"0x620d083d030d5826e2c19d64e2b5f8327598ced7b7f6a78d811f1ab58dfbff54","event_debt_raw":272033908},
{"name":"vault_E","vault":"0x6e0cdb09eb33cd3894c905e0dff9289b95a86fff","block":26194919,"tx":"0x5e503dad7122fe296acf61ef865347fe28228470d79cc7e6cc981b6367255424","event_debt_raw":77740}
]
 # Each tx remains receipt-verified before any economic inference.
def save(report): (OUT/"REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
def main():
 report={"scope":"Five distinct real Fluid Vault liquidation episodes from frozen source event census",
    "sampling":"Retrospective first event per vault, NOT confirmatory unseen holdout",
    "source_archive":"QT_Fluid_Events_20261019.zip original 21-event complete census",
    "read_only":True,"cash_profit_proven":False,
    "warning":["Predecessor block can be BEFORE triggering oracle transaction in same winner block",
      "Partial liquidation and price-impact are state-dependent, quotes not executed profit",
      "Gas, producer payment, collateral wrapping and flash financing still unverified",
      "ETH-native sentinel replaces WETH ONLY as offchain quote comparator",
      "Observed winner does not imply our own accessible execution"],
    "cases":[],"complete":False}
 save(report)
 try:
  if int(S.request(1,"eth_chainId",[],"check_chain"),16)!=1:raise ValueError("Wrong chain")
  for entry in SOURCE:
   r=dict(entry);report["cases"].append(r);r["states"]=[];save(report)
   receipt=S.request(1,"eth_getTransactionReceipt",[r["tx"]],"original_winner")
   if receipt is None or receipt["status"]!="0x1" or int(receipt["blockNumber"],16)!=r["block"]:
    r["invalid_source"]="TX_DOES_NOT_MATCH_CANONICAL_WINNER";save(report);continue
   # Must prove the selected vault really was liquidated in this transaction.
   if not any(x["address"].lower()==r["vault"] for x in receipt.get("logs",[])):
    r["invalid_source"]="VAULT_EVENT_NOT_IN_TX";save(report);continue
   r["original_winner"]={"gas_used":int(receipt["gasUsed"],16),
      "gas_cost_wei":str(int(receipt["gasUsed"],16)*int(receipt["effectiveGasPrice"],16)),
      "sender":receipt["from"].lower(),"transaction_complete":True}
   for block,kind in ((r["block"]-1,"predecessor"),(r["block"],"winner_block_post_state")):
    state={"block":block,"kind":kind};r["states"].append(state);save(report)
    try:
     h=S.request(1,"eth_getBlockByNumber",[hex(block),False],"canonical_header")
     bf=int(h["baseFeePerGas"],16);state["hash"]=h["hash"]
     got=S.liquidate_view(1,r["vault"],0,block,bf)
     state.update(got)
     if not got["liquidatable_now"]:
      state["reason"]="NOT_LIQUIDATABLE_IN_BLOCK_LEVEL_STATE";continue
     # A liquidator can select a smaller amount, but must query the true nonlinear mechanics.
     qlimit=min(r["event_debt_raw"],int(got["max_debt_in_raw"]))
     if not qlimit:continue
     bounded=S.liquidate_view(1,r["vault"],qlimit,block,bf)
     state["finite"]={"debt_raw":bounded["max_debt_in_raw"],
        "collateral_raw":bounded["max_collateral_out_raw"],"fee_quotes":[]}
     if int(bounded["max_debt_in_raw"])<=0 or int(bounded["max_collateral_out_raw"])<=0:continue
     if int(bounded["token1_in"],16) or int(bounded["token1_out"],16):
      state["cash_unknown"]="SMART/MULTI_ASSET_CLAIM";continue
     target_in=bounded["token0_in"];target_out=bounded["token0_out"]
     cost_token=WETH if target_in==ETH_ALIAS else target_in
     swap_asset=WETH if target_out==ETH_ALIAS else target_out
     state["native_conversion_assumption"]=bool(target_in==ETH_ALIAS or target_out==ETH_ALIAS)
     state["funding_token_decimals"]=18 if target_in==ETH_ALIAS else S.decimals(1,target_in,block,bf)
     for tier in (100,500,3000):
      q={"fee_tier":tier};state["finite"]["fee_quotes"].append(q)
      try:
       amt=S.quote(1,swap_asset,cost_token,int(bounded["max_collateral_out_raw"]),tier,block,bf)
       q["debt_asset_received_raw"]=str(amt)
       q["gross_margin_raw"]=str(amt-int(bounded["max_debt_in_raw"]))
       q["gross_positive_quote_only"]=bool(amt>int(bounded["max_debt_in_raw"]))
      except Exception as exc:q["error"]=repr(exc)
      save(report)
      if 1 in S.DENIED:raise RuntimeError("Stop after provider denial")
    except Exception as exc:state["error"]=repr(exc)
    save(report)
    if 1 in S.DENIED:raise RuntimeError("Stop after provider denial")
  report["complete"]=True
 except Exception as exc:report["error"]=repr(exc);report["traceback"]=traceback.format_exc()
 report["request_count"]=S.COUNT;report["denied_chains"]=sorted(S.DENIED);save(report)
 print(json.dumps({"complete":report["complete"],"requests":S.COUNT,
     "cases":[{"name":r["name"],"invalid":r.get("invalid_source"),
     "pre_liquidatable":r["states"][0].get("liquidatable_now") if r["states"] else None,
     "post_liquidatable":r["states"][1].get("liquidatable_now") if len(r["states"])>1 else None,
     "positive_gross":sum(int(q.get("gross_positive_quote_only",False)) for v in r["states"] for q in v.get("finite",{}).get("fee_quotes",[]))}
      for r in report["cases"]],"error":report.get("error")},indent=2),flush=True)
 if not report["complete"]:raise SystemExit("Incomplete research, preserve missing cases")
if __name__=="__main__":main()
