"""Compound III Stage 1: multiple deployed storefront markets and real historic
buy/absorb inventory events. Read-only public RPC; no execution or funds.
Predefine chains, markets, dates and selection BEFORE reading cash quotes.
Gross DEX quote margins are NOT actual transaction profits or capture evidence.
"""
import datetime as dt,hashlib,json,time,urllib.request,urllib.error,collections,traceback
from pathlib import Path
from Crypto.Hash import keccak

OUT=Path("comet_evidence");OUT.mkdir(exist_ok=True)
CHAINS={
 "ethereum":{"chain":1,"rpc":"https://rpc-eth.blockmachine.io",
    "from":25943261,"to":26093737,
    "quoter":"0x61ffe014ba17989e743c5f6cb21bf9697530b21e",
    "markets":{"USDC":"0xc3d688b66703497daa19211eedff47f25384cdc3",
       "WETH":"0xa17581a9e3356d9a858b789d68b4d866e593ae94",
       "USDT":"0x3afdc9bca9213a35503b077a6072f3d0d5ab0840"}},
 "base":{"chain":8453,"rpc":"https://mainnet.base.org",
    "from":52510000,"to":52634077,
    "quoter":"0x3d4e44eb1374240ce5f1b871ab261cd16335b76a",
    "markets":{"USDC":"0xb125e6687d4313864e53df431d5425969c15eb2f",
       "WETH":"0x46e6b214b524310239732d51387075e0e70970bf",
       "USDbC":"0x9c4ec768c28520b50860ea7a15bd7213a9ff58bf",
       "USDS":"0x2c776041ccfe903071af44aa147368a9c8eea518",
       "AERO":"0x784efeb622244d2348d4f2522f8860b96fbece89"}}
}
ALLOWED={"eth_chainId","eth_getBlockByNumber","eth_getCode","eth_getLogs","eth_call","eth_getTransactionReceipt"}
def k(s):
 h=keccak.new(digest_bits=256);h.update(s.encode());return h.hexdigest()
BUY="0x"+k("BuyCollateral(address,address,uint256,uint256)")
ABSORB="0x"+k("AbsorbCollateral(address,address,address,uint256,uint256)")
QUOTE="0x"+k("quoteExactInputSingle((address,address,uint256,uint24,uint160))")[:8]
BASE_TOKEN="0x"+k("baseToken()")[:8]
def pad(v):return format(int(v),'064x')
def address(v):
 a=int(v,16) if isinstance(v,str) else int(v)
 if not 0<=a<2**160:raise ValueError("Invalid EVM address")
 return "0x"+format(a,'040x')
def words(s):
 if not isinstance(s,str) or not s.startswith("0x") or (len(s)-2)%64:raise ValueError("Malformed abi")
 return [int(s[i:i+64],16) for i in range(2,len(s),64)]
def ev(l):
 t=l["topics"];d=words(l["data"]);topic=t[0].lower()
 if topic==BUY:
  if len(t)!=3 or len(d)!=2:raise ValueError("buy event mismatch")
  return dict(kind="buy",market=l["address"].lower(),buyer=address(t[1]),asset=address(t[2]),
    base_raw=str(d[0]),coll_raw=str(d[1]),tx=l["transactionHash"].lower(),block=int(l["blockNumber"],16),
    log_index=int(l["logIndex"],16))
 if topic==ABSORB:
  if len(t)!=4 or len(d)!=2:raise ValueError("absorb event mismatch")
  return dict(kind="absorb",market=l["address"].lower(),absorber=address(t[1]),borrower=address(t[2]),
    asset=address(t[3]),coll_raw=str(d[0]),usd_value_raw=str(d[1]),tx=l["transactionHash"].lower(),
    block=int(l["blockNumber"],16),log_index=int(l["logIndex"],16))
 raise ValueError("Unexpected event")
def save(p,x):
 path=OUT/p;path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(x,indent=2,default=str)+"\n")
class Reader:
 def __init__(self):
  self.n=0;self.blocked=set();self.cache={};self.stopped=False;self.start=time.monotonic()
  self.lastlogs={}
 def rpc(self,chain,label,method,params):
  if method not in ALLOWED:raise ValueError("Not read-only RPC")
  if chain in self.blocked:raise RuntimeError("Previous provider denial")
  if method=="eth_getLogs":
   x=params[0];lo=int(x["fromBlock"],16);hi=int(x["toBlock"],16)
   if hi-lo+1>9500 or not x.get("address"):raise ValueError("Unbounded log request")
  key=json.dumps([chain,method,params],sort_keys=True)
  if key in self.cache:return self.cache[key]
  if self.n>=190 or time.monotonic()-self.start>2100:raise RuntimeError("Research request/time limit")
  pause=26 if chain=="ethereum" and method=="eth_getLogs" else (8 if method=="eth_getLogs" else 1)
  if method=="eth_getLogs":
   time.sleep(max(0,pause-(time.monotonic()-self.lastlogs.get(chain,-1e3))))
   self.lastlogs[chain]=time.monotonic()
  else:time.sleep(1)
  self.n+=1;body=b'';record=dict(id=self.n,chain=chain,label=label,method=method,
         timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(),params=params,status="UNAVAILABLE")
  try:
   request=urllib.request.Request(CHAINS[chain]["rpc"],data=json.dumps({"jsonrpc":"2.0","id":self.n,
       "method":method,"params":params}).encode(),headers={"Content-Type":"application/json",
             "User-Agent":"QT-Stage1-Research-PublicRPC/1"})
   with urllib.request.urlopen(request,timeout=45) as response:
    record["http_status"]=response.status;body=response.read(4_000_001)
   if len(body)>4_000_000:raise ValueError("Reply exceeds 4MB cap")
   x=json.loads(body)
   if x.get("error"):
    record["rpc_error"]=x["error"];msg=str(x["error"]).lower()
    if any(z in msg for z in ("rate limit","client adjustable limit","access denied","quota")):
     self.blocked.add(chain)
    raise RuntimeError(str(x["error"])[:350])
   if "result" not in x:raise ValueError("RPC result unavailable")
   self.cache[key]=x["result"];record["status"]="OK";return x["result"]
  except urllib.error.HTTPError as e:
   record.update(http_status=e.code,error=str(e));body=e.read(100000)
   if e.code in (401,403,429):self.blocked.add(chain)
   raise
  except Exception as e:record["error"]=repr(e);raise
  finally:
   record["sha256"]=hashlib.sha256(body).hexdigest();record["bytes"]=len(body)
   (OUT/"raw").mkdir(exist_ok=True)
   (OUT/f"raw/{self.n:04d}.body").write_bytes(body)
   save(f"raw/{self.n:04d}.json",record)
def base_token(reader,chain,market,block):
 raw=reader.rpc(chain,"baseToken","eth_call",[{"to":market,"data":BASE_TOKEN},hex(block)])
 w=words(raw)
 if len(w)!=1:raise ValueError("Invalid baseToken reply")
 return address(w[0])
def quote_data(a,b,amt,fee):
 return QUOTE+pad(int(a,16))+pad(int(b,16))+pad(amt)+pad(fee)+pad(0)
def choose(candidates,cap=18):
 # deterministic first, highest base spend and median in each market, subject to 18 total.
 by=collections.defaultdict(list)
 for x in candidates:by[(x["chain"],x["market"])].append(x)
 picks={}
 for group,items in sorted(by.items()):
  chronological=sorted(items,key=lambda z:(z["block"],z["log_index"]))
  largest=max(items,key=lambda z:int(z["base_raw"]))
  options=[chronological[0],chronological[len(chronological)//2],largest]
  for e in options:picks[(e["chain"],e["tx"],e["log_index"])]=e
 return list(picks.values())[:cap]
def main():
 report={"research":"Multi-market Compound III actual sale-inventory and cash-exit quote census",
   "read_only":True,"no_wallet_signing_or_transactions":True,"no_strategy_execution":True,
   "gross_quote_profit_is_not_cash_profit":True,
   "sourced_deployments":"compound-finance/comet pinned official deployment roots; documented Comet event signatures",
   "sample_type":"Fixed historical windows; not all networks, markets or dates",
   "selection_rule":"First, median, largest actual BuyCollateral per chain-market before reading DEX quotes; at most 18",
   "chains":{},"choices":[],"failures":[],"complete":False}
 save("REPORT.json",report);read=Reader();allbuys=[]
 try:
  for chain,conf in CHAINS.items():
   row={"markets":{},"pages":[],"events":[],"errors":[],"from_block":conf["from"],"to_block":conf["to"]}
   report["chains"][chain]=row;save("REPORT.json",report)
   try:
    network=read.rpc(chain,"chainId","eth_chainId",[])
    assert int(network,16)==conf["chain"]
    for label,block in [("from",conf["from"]),("to",conf["to"])]:
     header=read.rpc(chain,label+"_header","eth_getBlockByNumber",[hex(block),False])
     row[label+"_timestamp_utc"]=dt.datetime.fromtimestamp(int(header["timestamp"],16),dt.timezone.utc).isoformat()
     row[label+"_hash"]=header["hash"]
    for label,a in conf["markets"].items():
     try:
      code=read.rpc(chain,"comet_code","eth_getCode",[a,hex(conf["to"])])
      if len(code)<10:raise ValueError("Deployed Comet code missing")
      base=base_token(read,chain,a,conf["to"])
      row["markets"][a]={"label":label,"base_token":base,"onchain_runtime_verified":True}
     except Exception as exc:row["markets"][a]={"label":label,"error":repr(exc)}
    markets=[a for a,x in row["markets"].items() if x.get("onchain_runtime_verified")]
    if not markets:raise RuntimeError("No verified markets")
    for lo in range(conf["from"],conf["to"]+1,9500):
     hi=min(conf["to"],lo+9499)
     raw=read.rpc(chain,"sale_inventory","eth_getLogs",[{"address":markets,
        "fromBlock":hex(lo),"toBlock":hex(hi),"topics":[[BUY,ABSORB]]}])
     rr=[dict(ev(z),chain=chain) for z in raw]
     row["events"].extend(rr)
     buys=sum(z["kind"]=="buy" for z in rr)
     row["pages"].append({"lo":lo,"hi":hi,"events":len(rr),"buys":buys})
     save("REPORT.json",report)
    assert row["pages"][0]["lo"]==conf["from"] and row["pages"][-1]["hi"]==conf["to"]
    row["events_complete"]=True
    allbuys.extend(x for x in row["events"] if x["kind"]=="buy")
   except Exception as exc:
    row["errors"].append(repr(exc))
    save("REPORT.json",report)
    # Respect provider denial; a partial chain does not establish zero occurrences.
   if read.blocked:report["provider_denied"]=sorted(read.blocked)
  report["choices"]=choose(allbuys)
  save("REPORT.json",report)
  for c in report["choices"]:
   try:
    chain=c["chain"];cfg=report["chains"][chain];market=cfg["markets"].get(c["market"],{})
    base=market.get("base_token")
    if not base:raise ValueError("Market lacks verified base asset")
    receipt=read.rpc(chain,"buy_receipt","eth_getTransactionReceipt",[c["tx"]])
    if not receipt or receipt["status"]!="0x1" or int(receipt["blockNumber"],16)!=c["block"]:
     raise ValueError("Canonical buy receipt does not match")
    if not any(z.get("logIndex") and int(z["logIndex"],16)==c["log_index"] and
       z["address"].lower()==c["market"] and z["topics"][0].lower()==BUY for z in receipt["logs"]):
     raise ValueError("Buy event missing from canonical receipt")
    c["receipt_verified"]=True
    c["buyer_gas_wei_all_transaction"]=str(int(receipt["gasUsed"],16)*int(receipt["effectiveGasPrice"],16)+int(receipt.get("l1Fee","0x0"),16))
    c["all_tx_buy_events"]=sum(z["topics"][0].lower()==BUY for z in receipt["logs"])
    c["quote_cash_out"]=[]
    if c["asset"]==base:
     c["quote_cash_out"].append({"status":"same_token","gross_margin_raw":str(int(c["coll_raw"])-int(c["base_raw"]))})
    else:
     for fee in (100,500,3000,10000):
      q={"fee":fee,"basis":"actual buyCollateral emitted quantity; QuoterV2 at parent block; no transaction execution"}
      c["quote_cash_out"].append(q)
      try:
       raw=read.rpc(chain,"exact_asset_to_base_quote","eth_call",[{"to":CHAINS[chain]["quoter"],
          "data":quote_data(c["asset"],base,int(c["coll_raw"]),fee)},hex(c["block"]-1)])
       w=words(raw)
       if len(w)<1:raise ValueError("Missing amountOut")
       q["cash_out_base_raw"]=str(w[0])
       q["base_paid_raw"]=c["base_raw"]
       q["gross_margin_base_raw"]=str(w[0]-int(c["base_raw"]))
       q["positive_before_cost"]=w[0]>int(c["base_raw"])
      except Exception as exc:q["unavailable"]=repr(exc)
    save("REPORT.json",report)
   except Exception as exc:c["error"]=repr(exc);save("REPORT.json",report)
  report["complete"]=bool(report["chains"]) and all(row.get("events_complete",False) for row in report["chains"].values())
 except Exception as exc:report["fatal"]=repr(exc);report["traceback"]=traceback.format_exc()
 report["requests"]=read.n;report["provider_denied"]=sorted(read.blocked)
 report["counts"]={ch:{"buy":sum(e["kind"]=="buy" for e in v["events"]),
      "absorb":sum(e["kind"]=="absorb" for e in v["events"]),"pages":len(v["pages"]),
      "complete":v.get("events_complete",False)} for ch,v in report["chains"].items()}
 report["positive_gross_quote_rows"]=sum(q.get("positive_before_cost",False) for x in report["choices"] for q in x.get("quote_cash_out",[]))
 save("REPORT.json",report)
 print(json.dumps({"complete":report["complete"],"counts":report["counts"],"requests":read.n,
     "positive_quote_rows":report["positive_gross_quote_rows"],"choices":len(report["choices"]),
     "provider_denied":report["provider_denied"],"fatal":report.get("fatal")},indent=2),flush=True)
 if not report["complete"]:raise SystemExit("Partial event census. Missing provider data is NOT zero opportunities")
if __name__=="__main__":main()
