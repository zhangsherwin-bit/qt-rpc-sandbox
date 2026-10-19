"""Root-cause test of 0xfb8f41b2 in an actual historical GHO GSM cash route.
No balances, oracle, storage, or live chain overwritten. Only unused probe code.
Preapproval from ZERO-token test account is simulated before Morpho flash loan.
"""
import sys, json, hashlib, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"gho_cash"))
import execute as E

OUT=Path("gho_allowance_evidence");OUT.mkdir(exist_ok=True)

def save(x):
 (OUT/"REPORT.json").write_text(json.dumps(x,indent=2,default=str)+"\n")

def calldata(sig,*args):
 return E.khash(sig)+"".join(E.word(x) for x in args)

def sim_params(h,runtime,principal,fee):
 def tx(data,limit):
  return {"from":E.BEN,"to":E.PROBE,"input":data,"gas":hex(limit),"gasPrice":"0x0"}
 txs=[
  tx(calldata("env()"),180000),
  tx(calldata("approvalState()"),180000),
  tx(calldata("prepareAllowance(uint256)",principal),270000),
  tx(calldata("approvalState()"),180000),
  tx(calldata("run(uint256,uint24)",principal,fee),7000000),
  tx(calldata("approvalState()"),180000),
  tx(calldata("env()"),180000)]
 overrides={"number":h["number"],"time":h["timestamp"],"gasLimit":h["gasLimit"],
  "baseFeePerGas":h["baseFeePerGas"],"feeRecipient":h["miner"],"prevRandao":h["mixHash"]}
 return {"blockStateCalls":[{"blockOverrides":overrides,
  "stateOverrides":{E.PROBE:{"code":runtime}},"calls":txs}],
  "validation":False,"traceTransfers":False},hex(int(h["number"],16)-1)

def parse(resp,h,principal):
 if not isinstance(resp,list) or len(resp)!=1 or len(resp[0].get("calls",[]))!=7:
  raise ValueError("Expected 7 sequential state-contained EVM call receipts")
 cc=resp[0]["calls"]
 for i in (0,1,2,3,5,6):
  if cc[i]["status"]!="0x1":raise ValueError(f"Diagnostic call {i} did not succeed: {cc[i].get('error')}")
 env0=E.decode_words(cc[0]["returnData"],10)
 env1=E.decode_words(cc[6]["returnData"],10)
 app0=E.decode_words(cc[1]["returnData"],2)
 got=E.decode_words(cc[2]["returnData"],1)[0]
 app1=E.decode_words(cc[3]["returnData"],2)
 app2=E.decode_words(cc[5]["returnData"],2)
 ref=(1,int(h["number"],16),int(h["timestamp"],16),int(h["baseFeePerGas"],16))
 if tuple(env0[:4])!=ref or tuple(env1[:4])!=ref:raise ValueError("Bad canonical chain/time/gas")
 if any(env0[4:8]):raise ValueError("Initial test wallet funded (forbidden)")
 if app0[0] or app0[1]:raise ValueError("Preexisting allowance; cannot isolate")
 if got!=principal or app1[0]!=principal:raise ValueError("PREAPPROVAL DID NOT PERSIST")
 trade=cc[4]
 out={"canonical_environment":True,"initial_balances_zero":True,
      "preapproval_verified_wei":str(got),"allowance_before":list(map(str,app0)),
      "allowance_after_preapproval":list(map(str,app1)),
      "allowance_after_attempt":list(map(str,app2)),
      "status":trade["status"],"gas_used":int(trade.get("gasUsed","0x0"),16),
      "revert":trade.get("error"),"initial_gsm_usdc_raw":str(env0[8]),
      "beneficiary_usdc_change":str(env1[6]-env0[6])}
 if trade["status"]=="0x1":
  profit=E.decode_words(trade.get("returnData","0x"),1)[0]
  if profit<=0 or env1[6]-env0[6]!=profit or env1[4]!=0 or env1[5]!=0 or env1[7]!=0:
   raise ValueError("Cash payout or terminal inventory condition violated")
  out["cash_profit_raw"]=str(profit)
  out["loan_repaid_and_beneficiary_paid"]=True
 else:
  if env1[4:8]!=env0[4:8]:raise ValueError("Reverted transaction changed balances")
  out["rollback_verified"]=True
 return out

def main():
 report={"scope":"Fix GHO GSM cash-replay failure by preapproving real lender-financed zero-principal probe",
    "timestamp":"frozen canonical Oct17 block 26220131",
    "no_wallet_or_live_broadcast":True,"no_funded_oracle_or_storage_overrides":True,
    "cash_profit_not_inferred_from_quote":True,"real_capture_unproven":True,"complete":False}
 save(report)
 try:
  runtime=E.compile_probe()
  if int(E.rpc("chainid","eth_chainId",[]),16)!=1:raise ValueError("Wrong chain")
  h=E.rpc("canonical_header","eth_getBlockByNumber",[hex(26220131),False])
  parent=E.rpc("canonical_parent","eth_getBlockByNumber",[hex(26220130),False])
  if h["parentHash"]!=parent["hash"]:raise ValueError("Historical mismatch")
  for a in (E.GSM,E.MORPHO,E.USDC,E.GHO):
   if E.rpc("production_code","eth_getCode",[a,parent["number"]])=="0x":raise ValueError("Missing production code "+a)
  if E.rpc("unused_code","eth_getCode",[E.PROBE,parent["number"]])!="0x":raise ValueError("Probe deployed")
  params,previous=sim_params(h,runtime,100*10**6,500)
  rr=E.rpc("preapproved_historical_cash","eth_simulateV1",[params,previous])
  report["result"]=parse(rr,h,100*10**6)
  report["complete"]=True
 except Exception as ex:report["error"]=repr(ex);report["traceback"]=traceback.format_exc()
 report["rpc_requests"]=E.N;report["heavy_calls"]=E.HEAVY
 save(report)
 print(json.dumps({k:v for k,v in report.items() if k!="traceback"},indent=2),flush=True)
 if not report["complete"]:raise SystemExit("Cash diagnosis incomplete; retain raw errors")
if __name__=="__main__":main()
