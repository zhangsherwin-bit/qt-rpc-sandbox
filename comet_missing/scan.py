"""Finish the five Ethereum Comet markets omitted by previous provider 429.
Independent public Ethereum RPC, pinned latest block; read-only, no trading.
"""
import sys,json,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"comet_current"))
import screen as D
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"stage1_followup"))
import study as S
OUT=Path("comet_missing_evidence");OUT.mkdir(exist_ok=True)
S.RPC[1]="https://ethereum-rpc.publicnode.com"
MARKETS={key:val for key,val in D.SPOKES[1].items() if key!="USDC"}
assert len(MARKETS)==5

def save(r):S.write(OUT,"REPORT.json",r)

def main():
    r={"scope":"Five previously omitted Ethereum Compound III markets; alternative legitimate public RPC",
     "read_only":True,"no_execution_or_profit":True,"addresses":MARKETS,"markets":[],
     "complete":False,"limitations":["This is a different latest block from earlier Ethereum USDC observation",
      "All quotes are gross and cannot be added as independent profits",
      "Alternative public endpoint availability does not establish cash-close or capture"]}
    c=S.Client(OUT);save(r)
    try:
      if int(c.rpc(1,"network_id","eth_chainId",[]),16)!=1:raise ValueError("Wrong chain")
      h=c.rpc(1,"pinned_block","eth_getBlockByNumber",["latest",False])
      r["block"]=int(h["number"],16);r["hash"]=h["hash"]
      for label,addr in MARKETS.items():
          row=D.market(c,1,label,addr,r["block"])
          r["markets"].append(row);save(r)
          if 1 in c.denied:raise RuntimeError("Provider denied; stop no retry")
      check=c.rpc(1,"hash_recheck","eth_getBlockByNumber",[h["number"],False])
      if check["hash"]!=h["hash"]:raise ValueError("Pinned block changed")
      r["complete"]=len(r["markets"])==len(MARKETS) and all(x["complete"] for x in r["markets"])
    except Exception as e:r["error"]=repr(e);r["traceback"]=traceback.format_exc()
    r["rpc_requests"]=c.n;r["provider_denied"]=sorted(c.denied)
    r["positive_gross_quotes"]=sum(x.get("gross_positive_quote_cases",0) for x in r["markets"])
    save(r)
    print(json.dumps({"complete":r["complete"],"markets":len(r["markets"]),
      "positive_gross_quotes":r["positive_gross_quotes"],"rpc_requests":c.n,
      "error":r.get("error")},indent=2),flush=True)
    if not r["complete"]:raise SystemExit("Five-market historical evidence incomplete, artifact still retained")
if __name__=="__main__":main()
