"""Comet native-WETH direct producer compensation challenge.
Read-only full historical prefix in eth_simulateV1; alternate cash settlement.
Does NOT broadcast, sign, alter production contracts or claim personal inclusion.
"""
import hashlib,json,time,traceback
from pathlib import Path
from collections import Counter
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"comet_flash"))
import replay as F
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"comet_follow"))
import run as Follow
from logic import as_call,receipt_matches
OUT=Path("native_bid_evidence");OUT.mkdir(exist_ok=True)
F.OUT=OUT;Follow.OUT=OUT
Follow.START=time.monotonic()
MAX_HEAVY=8
BID=174449845338543024
EVENT="0x"+F.k("Settled(uint256,uint256,uint256,uint256,uint256,uint256)")
BASE_FEE_VARIANTS=(100,500,3000,10000)

def save(path,obj):
    target=OUT/path;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(obj,indent=2)+"\n")

def compile_probe():
    import solcx
    source=Path("comet_native/CometNativeBidProbe.sol").read_text()
    build_in={"language":"Solidity","sources":{"CometNativeBidProbe.sol":{"content":source}},
     "settings":{"optimizer":{"enabled":True,"runs":200},"viaIR":True,"evmVersion":"cancun",
     "outputSelection":{"*":{"*":["abi","evm.deployedBytecode.object"]}}}}
    save("compiler_input.json",build_in)
    solcx.install_solc("0.8.24")
    comp=solcx.compile_standard(build_in,solc_version="0.8.24")
    save("compiler_output.json",comp)
    obj=comp["contracts"]["CometNativeBidProbe.sol"]["CometNativeBidProbe"]
    code="0x"+obj["evm"]["deployedBytecode"]["object"]
    funcs={f["name"] for f in obj["abi"] if f.get("type")=="function"}
    assert {"run","env","executeOperation"}<=funcs
    assert (len(code)-2)//2<=24576
    save("BUILD.json",{"source_sha256":hashlib.sha256(source.encode()).hexdigest(),
         "runtime_sha256":hashlib.sha256(bytes.fromhex(code[2:])).hexdigest(),
         "deployed_bytes":(len(code)-2)//2,
         "untrusted_deployment":False,"research_code_override_only":True})
    return code

def env_words(call):
    if call.get("status")!="0x1":raise ValueError("Synthetic context getter reverted")
    values=F.words(call["returnData"])
    if len(values)!=11:raise ValueError("Wrong context ABI length")
    return values

def check_success(trade,before,after,matched,gasbase):
    vals=F.words(trade["returnData"])
    if len(vals)!=1:raise ValueError("Unexpected return values")
    payout=vals[0];coinbase=after[10]-before[10]
    assert after[9]-before[9]==payout
    assert all(after[i]==0 for i in (4,5,6))
    assert after[7:9]==before[7:9]
    assert payout>0
    assert coinbase==(BID if matched else 0)
    ev=[x for x in trade.get("logs",[]) if x["address"].lower()==F.PROBE and x["topics"][0].lower()==EVENT]
    if len(ev)!=1:raise ValueError("No single settlement event")
    value=F.words(ev[0]["data"])
    if len(value)!=6:raise ValueError("Wrong settlement event ABI")
    loan,premium,seized,spent,producer,paid=value
    if loan!=F.AMOUNT or seized<spent or seized==0 or producer!=coinbase or paid!=payout:
        raise ValueError("Token/cash settlement inconsistency")
    repayment=loan+premium
    transfer=F.TRANSFER
    repaid=sum(int(log["data"],16) for log in trade.get("logs",[])
      if log["address"].lower()==F.USDC and len(log.get("topics",[]))==3
      and log["topics"][0].lower()==transfer
      and log["topics"][1][-40:].lower()==F.PROBE[2:]
      and log["topics"][2][-40:].lower()==F.AAVE[2:])
    if repaid!=repayment:raise ValueError("Aave actual repayment token transfer not established")
    return {"native_to_beneficiary_wei":str(payout),"producer_native_paid_wei":str(coinbase),
      "loan_usdc_raw":str(loan),"premium_usdc_raw":str(premium),
      "weth_received_wei":str(seized),"weth_spent_for_exact_USDC_wei":str(spent),
      "aave_usdc_repaid_raw":str(repaid),"producer_equal_observed":matched,
      "gas_basefee_wei":str(gasbase),
      "net_native_after_basefee_wei":str(payout-gasbase),
      "terminal_cash_closed":True}

def run_case(r,h,prefix,receipts,code,fee,matched):
    def call(dat,gas):
        return {"from":F.BENEF,"to":F.PROBE,"input":dat,
            "gas":hex(gas),"gasPrice":"0x0"}
    env=call(F.method("env()"),200000)
    action=call(F.method("run(uint256,uint24,bool)",F.AMOUNT,fee,int(matched)),6000000)
    headroom=int(h["gasLimit"],16)-sum(int(z["gasUsed"],16) for z in receipts)
    if headroom<6400000:raise ValueError("Historical block has insufficient execution headroom")
    label=f"native_fee_{fee}_bid_{int(matched)}"
    calls=Follow.simulate(r,label,h,prefix+[env,action,env],code)
    if len(calls)!=len(prefix)+3:raise ValueError("Missing calls")
    if not all(receipt_matches(x,y) for x,y in zip(calls[:len(prefix)],receipts)):
        raise ValueError("Canonical preceding transactions did not reproduce receipts")
    before,trade,after=calls[-3:]
    b,a=env_words(before),env_words(after)
    exact=[1,int(h["number"],16),int(h["timestamp"],16),int(h["baseFeePerGas"],16)]
    if b[:4]!=exact or a[:4]!=exact:raise ValueError("Noncanonical execution environment")
    if any(b[i] for i in range(4,10)):raise ValueError("Probe or beneficiary initially funded")
    if a[7:9]!=b[7:9]:raise ValueError("Unpriced token left with beneficiary")
    used=int(trade["gasUsed"],16)
    fee_wei=used*b[3]
    record={"label":label,"fee_tier":fee,"observed_bid_attempted":matched,
        "status":trade.get("status"),"prefix_exact":True,
        "historical_environment_exact":True,"gas_used":used,
        "block_gas_remaining":headroom,
        "basefee_cost_wei":str(fee_wei)}
    if trade.get("status")=="0x1":
        record.update(check_success(trade,b,a,matched,fee_wei))
    else:
        if a[4:]!=b[4:]:raise ValueError("Failed call modified cash/beneficiary/coinbase")
        record.update(error=trade.get("error"),rollback_verified=True,
          no_profit_observed=True)
    save("cases/"+label+".json",{"header":h,"calls":calls,"record":record})
    return record

def main():
    report={"scope":"ONE frozen Comet historical winner: direct WETH producer payment against best DEX exact-output collateral unwind",
      "research_only":True,"historical_case":F.ORIGINAL_TX,
      "not_new_opportunity_frequency_evidence":True,
      "previous_405_338373_USDC_cash_pre_bid":True,
      "observed_total_visible_producer_payment_wei":str(BID),
      "no_wallet_signing_trades_or_live_deployment":True,
      "outcomes":[],"complete":False}
    save("REPORT.json",report);r=Follow.Reader()
    try:
        assert r.call("chain","eth_chainId",[])=="0x1"
        F.pending_codes(r)
        h=Follow.header(r,F.BLOCK,True)
        orig=r.call("winner_receipt","eth_getTransactionReceipt",[F.ORIGINAL_TX])
        idx=int(orig["transactionIndex"],16)
        if idx!=2 or h["transactions"][idx]["hash"]!=F.ORIGINAL_TX:
            raise ValueError("Wrong original winner")
        prefix=[as_call(x) for x in h["transactions"][:idx]]
        receipts=[r.call("prefix_receipt","eth_getTransactionReceipt",[x["hash"]]) for x in h["transactions"][:idx]]
        code=compile_probe()
        for fee in BASE_FEE_VARIANTS:
            for matched in (False,True):
                try:case=run_case(r,h,prefix,receipts,code,fee,matched)
                except Exception as exc:case={"label":f"native_fee_{fee}_bid_{int(matched)}","exception":repr(exc)}
                report["outcomes"].append(case);save("REPORT.json",report)
                if r.denied:raise RuntimeError("Provider denied; stop")
        report["complete"]=len(report["outcomes"])==8 and all("status" in x for x in report["outcomes"])
    except Exception as e:
        report["error"]=repr(e);report["traceback"]=traceback.format_exc()
    report["requests"]=r.n;report["heavy_calls"]=r.heavy;report["provider_denied"]=r.denied
    report["cash_positive_equal_bid_cases"]=sum(
      x.get("terminal_cash_closed") is True and x.get("producer_equal_observed") is True
      and int(x.get("net_native_after_basefee_wei","0"))>0 for x in report["outcomes"])
    save("REPORT.json",report)
    print(json.dumps({"complete":report["complete"],"requests":r.n,"heavy_calls":r.heavy,
      "results":[{"label":x.get("label"),"status":x.get("status"),
       "net_native_after_basefee_wei":x.get("net_native_after_basefee_wei"),
       "error":x.get("error"),"exception":x.get("exception")} for x in report["outcomes"]]},indent=2),flush=True)
    if not report["complete"]:raise SystemExit("Historical test incomplete, preserve failures")
if __name__=="__main__":main()
