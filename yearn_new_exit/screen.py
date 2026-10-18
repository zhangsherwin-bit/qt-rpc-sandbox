"""Stage1 discovery: new genuine Yearn auction settlement inventory vs fully sized DEX exits.
Six fixed real historical RSUP/DOLA auctions, NOT selected by quote profit.
Read-only ERC20 transfer receipt + 2026 canonical predecessor-state QuoterV2 calls.
Positive quote is neither integrated cash close nor executable winner's income.
"""
import json,hashlib,time,traceback,urllib.request,urllib.error,datetime
from pathlib import Path
from Crypto.Hash import keccak

OUT=Path("yearn_exit_evidence");OUT.mkdir(exist_ok=True)
RPC="https://rpc-eth.blockmachine.io"
QUOTER="0x61ffe014ba17989e743c5f6cb21bf9697530b21e"
WETH="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
USDC="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
CRVUSD="0xf939e0a03fb07f59a73314e73794be0e57ac1b4e"
RSUP="0x419905009e4656fdc02418c7df35b1e61ed5f726"
DOLA="0x865377367054516e17014ccded1e7d814edc9ce4"
AUCTION="0xa00e6b35c23442fa9d5149cba5dd94623ffe6693"
SEL="0x3539af76bcb13fa381f2ec32e6d90b9c5e95055778ebdca0e7a192ba07755881"
KICK="0xb3831db58b36bd77258a9cc9589b88fab5d52f7a1814e6f17faec14b149fe084"
TRANSFER="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55e4df523b3ef"
# Correct canonical ERC-20 event topic verified in regression.
TRANSFER="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55e4df523b3ef".replace("55e4df","55a4df")
# Standard ERC20 Transfer keccak256 "Transfer(address,address,uint256)"
REQUESTS=0;START=time.monotonic();STOP=False;LAST=0
def save(name,v):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,default=str)+"\n")
def h(s):k=keccak.new(digest_bits=256);k.update(s.encode());return '0x'+k.hexdigest()
def enc(n):return format(n,'064x')
def pad_addr(a):return a.lower()[2:].zfill(64)
def rpc(method,params,label):
 global REQUESTS,STOP,LAST
 if STOP:raise RuntimeError("Provider denied, stop")
 if method not in {"eth_chainId","eth_getTransactionReceipt","eth_getBlockByNumber","eth_call","eth_getCode"}:
  raise ValueError("Only historical read methods permitted")
 if REQUESTS>=190 or time.monotonic()-START>1150:raise RuntimeError("Fixed bounded research budget reached")
 if LAST:time.sleep(max(0,1.7-(time.monotonic()-LAST)))
 LAST=time.monotonic();REQUESTS+=1;body=b""
 packet={"jsonrpc":"2.0","id":REQUESTS,"method":method,"params":params}
 rec={"label":label,"request":REQUESTS,"method":method,"params":params}
 try:
  req=urllib.request.Request(RPC,data=json.dumps(packet).encode(),
    headers={"Content-Type":"application/json","User-Agent":"QT-Stage1-ReadOnly-Research"})
  with urllib.request.urlopen(req,timeout=22) as response:body=response.read(4000001);rec["http_status"]=response.status
  if len(body)>4000000:raise ValueError("Oversized result")
  answer=json.loads(body)
  if answer.get("error"):
   msg=str(answer["error"]);rec["rpc_error"]=answer["error"]
   if any(w in msg.lower() for w in ("rate limit","access denied","client adjustable limit","unauthorized")):STOP=True
   raise RuntimeError(msg[:220])
  rec["status"]="SUCCESS"
  return answer["result"]
 except urllib.error.HTTPError as e:
  body=e.read(60000);rec.update(http_status=e.code,error=str(e))
  if e.code in (401,403,429):STOP=True
  raise
 except Exception as e:rec["error"]=str(e)[:300];raise
 finally:
  rec["raw_sha256"]=hashlib.sha256(body).hexdigest()
  (OUT/"raw").mkdir(exist_ok=True);(OUT/f"raw/{REQUESTS:04}.body").write_bytes(body)
  save(f"raw/{REQUESTS:04}.json",rec)

def select(census):
 logs=census['logs'];a=census['auctions']
 meta=next(x for x in a if x["auction"].lower()==AUCTION)
 if meta['want'].lower()!=CRVUSD:raise ValueError("Auction want changed")
 cases=[]
 for name,token in [("RSUP",RSUP),("DOLA",DOLA)]:
  settled=sorted((l for l in logs if l.get("address","").lower()==AUCTION and
      l["topics"][0].lower()==SEL and l["topics"][1][-40:].lower()==token[2:]),
      key=lambda x:(int(x['blockNumber'],16),int(x["transactionIndex"],16)))
  if len(set(x["transactionHash"] for x in settled))!=len(settled) or len(settled)<3:
   raise ValueError("Insufficient unique actual settlements")
  for rank,pos in enumerate([0,len(settled)//2,len(settled)-1]):
   row=settled[pos]
   kick=any(l.get("address","").lower()==AUCTION and l["topics"][0].lower()==KICK and
     l["topics"][1][-40:].lower()==token[2:] and int(l["blockNumber"],16)<int(row["blockNumber"],16)
     for l in logs)
   if not kick:raise ValueError("No preceding actual kicked auction")
   cases.append({"asset":name,"token":token,"tx":row["transactionHash"],"block":int(row["blockNumber"],16),
       "kicked_before":True,"date_rank":rank})
 if len({x["tx"] for x in cases})!=6:raise ValueError("Same economic tx chosen twice")
 return cases

def quote(a,b,amt,fee,block):
 if amt<=0:raise ValueError("Quote amount must be positive")
 sel=h("quoteExactInputSingle((address,address,uint256,uint24,uint160))")[2:10]
 call="0x"+sel+pad_addr(a)+pad_addr(b)+enc(amt)+enc(fee)+enc(0)
 data=rpc("eth_call",[{"to":QUOTER,"data":call},hex(block)],f"quote_{a[-5:]}_{b[-5:]}_fee_{fee}_at_{block}")
 if not isinstance(data,str) or not data.startswith("0x") or len(data)<2+4*64:
  raise ValueError("Unexpected Quoter output")
 return int(data[2:66],16)

def actual_receipt(row):
 r=rpc("eth_getTransactionReceipt",[row["tx"]],"canonical_auction_settlement")
 if not r or r["status"]!="0x1" or int(r["blockNumber"],16)!=row["block"]:
  raise ValueError("Historical settlement receipt mismatch")
 kicked=[x for x in r["logs"] if x.get("topics") and x["topics"][0].lower()==SEL
    and x["address"].lower()==AUCTION and x["topics"][1][-40:].lower()==row["token"][2:]]
 if not kicked:raise ValueError("No actual matching auction settlement event in receipt")
 moved=[];paid=[]
 for l in r["logs"]:
  if not l.get("topics") or l["topics"][0].lower()!=TRANSFER or len(l["topics"])!=3:continue
  token=l["address"].lower();frm="0x"+l["topics"][1][-40:].lower();to="0x"+l["topics"][2][-40:].lower()
  if token==row["token"] and frm==AUCTION:moved.append((int(l["data"],16),to))
  if token==CRVUSD and to!="0x"+'0'*40 and frm!=to:paid.append((int(l["data"],16),frm,to))
 if len(moved)!=1 or not paid:raise ValueError("Ambiguous auction sale or missing payment; no invented price")
 # The auction may be involved in a larger settlement; require the paid crvUSD transfer's
 # recipient to equal the auction's verified receiver from a contract view elsewhere,
 # so this quote remains a candidate until receiver is separately confirmed.
 w=rpc("eth_call",[{"to":AUCTION,"data":h("receiver()")[:10]},hex(row["block"]-1)],"auction_receiver")
 receiver="0x"+w[-40:].lower() if isinstance(w,str) and len(w)>=66 else ""
 matched=[p for p in paid if p[2]==receiver]
 if len(matched)!=1:raise ValueError("No uniquely attributable crvUSD payment to auction receiver")
 row["sold_raw"]=str(moved[0][0]);row["buyer"]=moved[0][1]
 row["payment_raw"]=str(matched[0][0]);row["payment_receiver"]=receiver
 row["gas_actual_wei"]=str(int(r["gasUsed"],16)*int(r["effectiveGasPrice"],16))
 row["receipt_checked"]=True

def explore(row):
 block=row["block"]-1
 direct=[]
 for fee in (100,500,3000,10000):
  try:
   v=quote(row["token"],CRVUSD,int(row["sold_raw"]),fee,block)
   direct.append({"path":["DIRECT",fee],"quoted_cash_out_crvusd_raw":str(v),
       "gross_margin_crvusd_raw":str(v-int(row["payment_raw"]))})
  except Exception as e:direct.append({"path":["DIRECT",fee],"error":repr(e)})
  if STOP:return direct
 for bridge in (USDC,WETH):
  for fee0 in (500,3000):
   try:
    a=quote(row["token"],bridge,int(row["sold_raw"]),fee0,block)
    if a<=0:raise ValueError("Zero first-hop output")
   except Exception as e:
    direct.append({"path":["BRIDGE",bridge,fee0],"error":repr(e)});continue
   for fee1 in (500,3000):
    try:
     b=quote(bridge,CRVUSD,a,fee1,block)
     direct.append({"path":["BRIDGE",bridge,fee0,fee1],
         "quoted_cash_out_crvusd_raw":str(b),"gross_margin_crvusd_raw":str(b-int(row["payment_raw"]))})
    except Exception as e:direct.append({"path":["BRIDGE",bridge,fee0,fee1],"error":repr(e)})
    if STOP:return direct
 return direct

def main():
 result={"scope":"Six real Yearn auction settlements selling RSUP/DOLA for crvUSD in 21-day fixed census",
 "selection":"First, median, last chronological settle per token; frozen before any exit quotations",
 "historical_canonical_receipts":True,"read_only":True,"no_trades_or_signatures":True,
 "not_complete_atomic_settlement":True,
 "warnings":["QuoterV2 results are indicative and may not spend all input if price-limited",
    "Historical predecessor-block quotes are not the same as prefix insertion state",
    "Settlement receipt transfers may be embedded in other bundled operations",
    "Positive gross quote never proves inclusion, permissions, borrowing or actual net cash"],
 "cases":[],"complete":False}
 save("REPORT.json",result)
 try:
  logs=json.loads(Path("input/ALL_LOGS.json").read_text())
  auctions=json.loads(Path("input/AUCTIONS.json").read_text())
  selection=select({"logs":logs,"auctions":auctions})
  result["selection"]=selection;save("REPORT.json",result)
  if rpc("eth_chainId",[],"verify_ethereum")!="0x1":raise ValueError("Wrong network")
  for x in selection:
   row=dict(x);row["quotes"]=[];result["cases"].append(row);save("REPORT.json",result)
   try:
    actual_receipt(row)
    row["quotes"]=explore(row)
    vals=[int(y["gross_margin_crvusd_raw"]) for y in row["quotes"] if "gross_margin_crvusd_raw" in y]
    row["best_quote_gross_crvusd_raw"]=str(max(vals)) if vals else None
    row["any_positive_gross_quote"]=any(v>0 for v in vals)
   except Exception as e:row["error"]=repr(e)
   save("REPORT.json",result)
   if STOP:raise RuntimeError("Provider denied; no retries")
  result["complete"]=True
 except Exception as e:
  result["fatal_error"]=repr(e);result["traceback"]=traceback.format_exc()
 result["requests"]=REQUESTS;result["provider_stopped"]=STOP
 save("REPORT.json",result)
 print(json.dumps({"complete":result["complete"],"requests":REQUESTS,
     "cases":[{"asset":x["asset"],"block":x["block"],
        "best_gross":x.get("best_quote_gross_crvusd_raw"),"error":x.get("error")} for x in result["cases"]]},
     indent=2),flush=True)
 if not result["complete"]:raise SystemExit("Historical auction research incomplete; save all errors")
if __name__=="__main__":main()
