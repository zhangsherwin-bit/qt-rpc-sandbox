"""Two frozen observed UniswapX signed+filled orders: historical DEX acquisition quotes only.
A quote is not a filled transaction, an eligible filler right or an income claim.
No order signing, broadcasting, state override, wallet, credentials.
"""
import json,time,hashlib,datetime,traceback,urllib.request,urllib.error
from pathlib import Path
from Crypto.Hash import keccak

OUT=Path("uniswapx_evidence");OUT.mkdir(exist_ok=True)
RPC="https://rpc-eth.blockmachine.io";QUOTER="0x61ffe014ba17989e743c5f6cb21bf9697530b21e"
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48";WETH="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
ONE=dict(orderHash="0x4c23a896626cea2566b6a1d2499f2e0b3a6daeb03558aceaf807ae9e5c3c8472",
    fill="0x224c94d52947b7af20cae64ace5be721085c3ca1d15bd64a4f492017ef4af34b",
    block=26217505,tokenIn=USDC,tokenOut=WETH,amountOut=5*10**18,
    lowIn=12066110105,highIn=12126440655)
TWO=dict(orderHash="0x09ff621f8d553b38aa054038cb28505d28adbf968f1b4bbf0491c035b030ba4a",
    fill="0xa50e21f4d714c616f3302b1953ce4a47fc98f8f7433b01b69da21220524417dc",
    block=26217510,tokenIn="0x1b54e762aa34cf6e28e9c082f2848e28e45da6b8",
    tokenOut="0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7",
    amountIn=500000000000000000000000,lowOut=817600909766997410445,highOut=821709457052258703965)
COUNT=0;LOG=[];STOP=False
def save(name,x):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,default=str)+"\n")
def h(s):
    k=keccak.new(digest_bits=256);k.update(s.encode());return k.hexdigest()
def pad(n):return hex(n)[2:].zfill(64)
def addr(a):return a.lower().replace("0x","").zfill(64)
def encode(to,amount,fee):
    sel=h("quoteExactOutputSingle((address,address,uint256,uint24,uint160))")[:8]
    return "0x"+sel+addr(USDC)+addr(to)+pad(amount)+pad(fee)+pad(0)
def rpc(name,method,params):
    global COUNT,STOP
    if STOP:raise RuntimeError("Provider denied; stopped")
    if COUNT>=46:raise RuntimeError("Fixed 46 request cap")
    if method not in ("eth_call","eth_getTransactionReceipt","eth_getBlockByNumber","eth_chainId","eth_getCode"):raise ValueError("Read RPC only")
    COUNT+=1;ifsleep=1.0;time.sleep(ifsleep)
    body=b"";rec={"request":COUNT,"name":name,"method":method}
    try:
        payload=json.dumps({"jsonrpc":"2.0","id":COUNT,"method":method,"params":params}).encode()
        req=urllib.request.Request(RPC,data=payload,headers={"Content-Type":"application/json","User-Agent":"QT-Stage1-ReadOnly"})
        with urllib.request.urlopen(req,timeout=30) as resp:body=resp.read(2_000_001)
        if len(body)>2_000_000:raise ValueError("body too large")
        p=json.loads(body)
        if p.get("error"):
            rec["rpc_error"]=p["error"]
            msg=str(p["error"]).lower()
            if any(z in msg for z in ("rate limit","access denied","client adjustable limit","unauthorized")):STOP=True
            raise RuntimeError(str(p["error"])[:220])
        rec["status"]="OK"
        return p["result"]
    except urllib.error.HTTPError as e:
        body=e.read(100000);rec["error"]=str(e)
        if e.code in (401,403,429):STOP=True
        raise
    finally:
        rec["sha256"]=hashlib.sha256(body).hexdigest()
        save("requests/"+str(COUNT)+".json",rec)
        (OUT/"raw").mkdir(exist_ok=True)
        (OUT/f"raw/{COUNT}.body").write_bytes(body)
def quote(token_in,token_out,amount,fee,block):
    sel=h("quoteExactOutputSingle((address,address,uint256,uint24,uint160))")[:8]
    data="0x"+sel+addr(token_in)+addr(token_out)+pad(amount)+pad(fee)+pad(0)
    s=rpc("quoter_fee_"+str(fee)+"_block_"+str(block),"eth_call",[{"to":QUOTER,"data":data},hex(block)])
    if not isinstance(s,str) or len(s)<66:raise ValueError("invalid quote response")
    return int(s[2:66],16)
def meta(token,block):
    o={"token":token}
    for name,sel in [("decimals","0x313ce567"),("symbol","0x95d89b41")]:
        try:o[name]=rpc(name+"_"+token,"eth_call",[{"to":token,"data":sel},hex(block)])
        except Exception as e:o[name+"_error"]=str(e)[:150]
    return o
def main():
    rep={"scope":"Two exact observed historical UniswapX fills, order economics only","not_income":True,
        "not_execution_or_capture":True,"snapshots":[],"exceptions":[],"no_order_submission":True}
    try:
        assert rpc("eth_chainId","eth_chainId",[])=="0x1"
        assert len(rpc("quoter_deployed","eth_getCode",[QUOTER,hex(ONE["block"])]))>10
        for o in (ONE,TWO):
            x=dict(o);rep["snapshots"].append(x);save("REPORT.json",rep)
            rec=rpc("canonical_receipt","eth_getTransactionReceipt",[o["fill"]])
            assert rec and rec["status"]=="0x1" and int(rec["blockNumber"],16)==o["block"]
            x["receipt_canonical"]=True
            x["token_metadata"]=[meta(o["tokenIn"],o["block"]-1),meta(o["tokenOut"],o["block"]-1)]
            for block in (o["block"]-1,o["block"]):
                for fee in (100,500,3000,10000):
                    q={"block":block,"fee":fee}
                    x.setdefault("quotes",[]).append(q)
                    try:
                        amt=quote(o["tokenIn"],o["tokenOut"],o.get("amountOut",o.get("lowOut")),fee,block)
                        q["required_input_raw"]=str(amt)
                        if o is ONE:
                            q["spread_at_low_order_input_raw"]=str(o["lowIn"]-amt)
                            q["spread_at_high_order_input_raw"]=str(o["highIn"]-amt)
                            q["robust_positive_before_cost"]=amt<o["lowIn"]
                        else:
                            q["warning"]="Second order uses a Dutch output amount; quote needs exact fill phase and token metadata"
                    except Exception as e:q["error"]=str(e)[:260]
                    save("REPORT.json",rep)
                    if STOP:raise RuntimeError("Provider refused; terminate")
        rep["completed"]=True
    except Exception as e:rep["exception"]=repr(e);rep["exceptions"].append(traceback.format_exc())
    rep["requests"]=COUNT;rep["provider_stopped"]=STOP;save("REPORT.json",rep)
    print(json.dumps({"completed":rep.get("completed",False),"quote_counts":[len(x.get("quotes",[])) for x in rep["snapshots"]],
      "requests":COUNT,"exception":rep.get("exception")},indent=2),flush=True)
    if not rep.get("completed"):raise SystemExit("UniswapX research incomplete; partial evidence retained")
if __name__=="__main__":main()
