"""Stage1 exact-capacity checks on three newly discovered Morpho collateral markets.
Public read-only; a positive ERC4626 preview or API borrow does not imply instant redemption.
No liquidation attempt, signing, trading or state overrides.
"""
import datetime,decimal,hashlib,json,re,time,traceback,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from Crypto.Hash import keccak
OUT=Path("claim_eligibility_evidence");OUT.mkdir(exist_ok=True)
CORE="0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb"
RPC={8453:"https://mainnet.base.org",1:"https://ethereum-rpc.publicnode.com"}
API="https://api.morpho.org/graphql"
MARKETS=[
 {"name":"yoETH_WETH_Base","chain":8453,"id":"0x94f344f8db8c950faa45206c269dd0c2787a86ae3a7b988423e1e6e8173ae269",
  "vault":"0x3a43aec53490cb9fa922847385d82fe25d0e9de7","loan":"0x4200000000000000000000000000000000000006","lltv":915000000000000000,
  "observed_borrow_usd":"199684.44472221253","block_window_offsets":(900000,240000,20000)},
 {"name":"sUSDX_USDC_Base","chain":8453,"id":"0x4c8e1349aa58fb02b17347d2e2916ae84a2930744b0a062413d7851aa73cec35",
  "vault":"0xeb6d2c72422e17517d483097a2df29b753a5856c","loan":"0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
  "lltv":860000000000000000,"observed_borrow_usd":"24995700.83012798",
  "block_window_offsets":(900000,240000,20000)},
 {"name":"USD3_USDC_Ethereum","chain":1,"id":"0xe3df58f9d3011b7481ff36b939fa5f8da642f34ea5792d25d3958dbf1efa26d7",
  "vault":"0x056b269eb1f75477a8666ae8c7fe01b64dd55ecc","loan":"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
  "lltv":915000000000000000,"observed_borrow_usd":"18659176.741478562",
  "block_window_offsets":(170000,28000,4000)}]
MAX=115;NUM=0;START=time.monotonic();DENIED=set();CACHE={}
def save(name,obj):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,indent=2,sort_keys=True,default=str)+"\n")
def sig(s):
 k=keccak.new(digest_bits=256);k.update(s.encode())
 return '0x'+k.hexdigest()[:8]
def topic(s):
 k=keccak.new(digest_bits=256);k.update(s.encode())
 return '0x'+k.hexdigest()
def w(n):return format(int(n),"064x")
def a(x):return x.lower().replace("0x","").zfill(64)
def parse_uint(s):
 if not isinstance(s,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",s):raise ValueError("Bad ABI uint")
 return int(s,16)
def parse_address(s):
 if not isinstance(s,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",s) or int(s[2:26],16):raise ValueError("Bad ABI address")
 return "0x"+s[-40:].lower()
def request(name,url,payload,chain=None):
 global NUM
 host=urllib.parse.urlsplit(url).netloc
 if host not in {"api.morpho.org","mainnet.base.org","ethereum-rpc.publicnode.com"}:raise ValueError("unapproved provider")
 if host in DENIED:raise RuntimeError("Provider refused access; stopping host")
 key=json.dumps([url,payload],sort_keys=True)
 if key in CACHE:return CACHE[key]
 if NUM>=MAX or time.monotonic()-START>930:raise RuntimeError("Fixed budget exceeded")
 if NUM:time.sleep(0.8)
 NUM+=1;body=b'';info={"id":NUM,"name":name,"host":host,"chain":chain,"time_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={
   "Content-Type":"application/json","Accept":"application/json","User-Agent":"QT-Stage1-only-public-read/2"})
  with urllib.request.urlopen(req,timeout=24) as r:body=r.read(2_000_001);info["http_status"]=r.status
  if len(body)>2_000_000:raise ValueError("Response bytes cap")
  obj=json.loads(body)
  if obj.get("error") or obj.get("errors"):
   e=obj.get("error") or obj.get("errors");info["remote_error"]=e
   if any(x in str(e).lower() for x in ("rate limit","too many","unauthorized","client adjustable limit","access denied")):DENIED.add(host)
   raise ValueError("RPC/GraphQL unavailable "+str(e)[:200])
  CACHE[key]=obj;info["status"]="OK"
  save("responses/"+str(NUM).zfill(3)+".json",obj)
  return obj
 except urllib.error.HTTPError as e:
  body=e.read(100000);info["error"]=str(e);info["http_status"]=e.code
  if e.code in (401,403,429):DENIED.add(host)
  raise
 except Exception as e:info["error"]=repr(e);raise
 finally:
  info["sha256"]=hashlib.sha256(body).hexdigest();info["body_length"]=len(body)
  save("requests/"+str(NUM).zfill(3)+".json",info)
def rpc(chain,name,method,params):
 if method not in {"eth_chainId","eth_getCode","eth_getBlockByNumber","eth_call","eth_getLogs","eth_getTransactionReceipt"}:
  raise ValueError("Read only methods")
 resp=request(name,RPC[chain],{"jsonrpc":"2.0","id":NUM+1,"method":method,"params":params},chain)
 if "result" not in resp:raise ValueError("RPC missing result")
 return resp["result"]
def call(chain,name,to,data,block):
 return rpc(chain,name,"eth_call",[{"to":to,"data":data},hex(block)])
def gql_positions(m):
 chain=m["chain"];mid=m["id"]
 # Morpho's documented marketUniqueKey_in filter; incomplete first 100 borrower positions only.
 q='query { marketPositions(first: 100, orderBy: BorrowShares, orderDirection: Desc, where: { marketUniqueKey_in: ["%s"]}) { items { user {address} state { borrowAssetsUsd collateralUsd borrowAssets collateral borrowShares } } pageInfo { countTotal } } }'%mid
 try:
  got=request("borrower_positions_"+m["name"],API,{"query":q},chain)
  data=got["data"]["marketPositions"];items=data.get("items",[])
  rows=[]
  for x in items:
   st=x.get("state") or {}
   row={"user":(x.get("user") or {}).get("address"),"borrow_usd":st.get("borrowAssetsUsd"),
        "collateral_usd":st.get("collateralUsd"),"collateral":st.get("collateral"),
        "borrow_shares":st.get("borrowShares")}
   try:
    b=decimal.Decimal(str(row["borrow_usd"]));c=decimal.Decimal(str(row["collateral_usd"]))
    row["approx_unhealthy_by_api"]=c>0 and b>=c*decimal.Decimal(m["lltv"])/decimal.Decimal(10)**18
   except Exception:row["approx_unhealthy_by_api"]=None
   rows.append(row)
  return {"rows":rows,"api_position_rows":len(rows),"reported_total_positions":(data.get("pageInfo") or {}).get("countTotal"),
          "sample_only_and_api_health_is_not_onchain_eligibility":True}
 except Exception as e:return {"error":repr(e),"position_availability_unknown":True}
def diagnostic_views(m,block):
 chain=m["chain"];v=m["vault"];loan=m["loan"];r={"asset":None,"checks":[]}
 def check(name,contract,selector):
  x={"name":name};r["checks"].append(x)
  try:x["return"]=call(chain,name,contract,selector,block)
  except Exception as e:x["error"]=repr(e)
  return x
 check("vault_underlying",v,sig("asset()"))
 check("vault_share_decimals",v,sig("decimals()"))
 check("vault_preview_redeem_one_nominal_share",v,sig("previewRedeem(uint256)")+w(10**(6 if m["name"].startswith("USD3") or "sUSDX" in m["name"] else 18)))
 check("vault_total_assets",v,sig("totalAssets()"))
 check("loan_token_idle_balance_at_vault",loan,sig("balanceOf(address)")+a(v))
 check("vault_max_redeem_core",v,sig("maxRedeem(address)")+a(CORE))
 if m["name"].startswith("USD3"):
  check("USD3_available_withdraw_limit_core",v,sig("availableWithdrawLimit(address)")+a(CORE))
 if m["name"].startswith("yoETH"):
  check("YO_total_pending_assets",v,sig("totalPendingAssets()"))
 return r
def historical_events(m,block):
 signature=topic("Liquidate(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)")
 out=[]
 for offset in m["block_window_offsets"]:
  hi=block-offset;lo=max(0,hi-1999)
  row={"from":lo,"through":hi,"offset":offset,"status":"NOT_READ"}
  out.append(row)
  try:
   # public providers generally bound a query's block range.
   events=rpc(m["chain"],"liq_events_"+str(offset),"eth_getLogs",[{"address":CORE,
       "topics":[signature,m["id"]],"fromBlock":hex(lo),"toBlock":hex(hi)}])
   row["event_count"]=len(events);row["status"]="OK"
   row["events"]=[{"block":int(x["blockNumber"],16),"tx":x["transactionHash"],
       "caller":"0x"+x["topics"][2][-40:],"borrower":"0x"+x["topics"][3][-40:],
       "repaid_assets_raw":str(int(x["data"][2:66],16)),
       "seized_collateral_shares_raw":str(int(x["data"][130:194],16))} for x in events[:8]]
  except Exception as e:row["status"]="UNAVAILABLE";row["error"]=repr(e)
  if urllib.parse.urlsplit(RPC[m["chain"]]).netloc in DENIED:break
 return out
def main():
 report={"scope":"USD3/USDC and yoETH/WETH and sUSDX/USDC Morpho collateral rights, borrower and cash limits",
   "read_only":True,"cash_profit_established":False,"can_trade":False,
   "limitations":["Positive previewRedeem is NOT instant cash, especially for YO async vaults",
     "USD3 withdrawals depend on liquidity and ring-fenced reserves; availability must be contract verified",
     "Borrow amount is market outstanding principal, not collateral eligible for seizure",
     "API borrowing health is discovery only; onchain state, oracle and callback must be validated",
     "Three small historical log windows per market are not an exhaustive liquidation census"],
   "markets":[],"errors":[],"complete":False}
 save("REPORT.json",report)
 try:
  for ch in (8453,1):
   if int(rpc(ch,"chain_id","eth_chainId",[]),16)!=ch:raise ValueError("Wrong network")
   h=rpc(ch,"header_pin","eth_getBlockByNumber",["latest",False])
   block=int(h["number"],16)
   for m in (x for x in MARKETS if x["chain"]==ch):
    row=dict(m,block=block,hash=h["hash"])
    report["markets"].append(row);save("REPORT.json",report)
    row["api_positions"]=gql_positions(m)
    row["onchain_cash_views"]=diagnostic_views(m,block)
    row["historical_liquidations_sample"]=historical_events(m,block)
    save("REPORT.json",report)
   header_check=rpc(ch,"header_recheck","eth_getBlockByNumber",[h["number"],False])
   if header_check["hash"]!=h["hash"]:raise ValueError("Blockchain pin changed")
  report["complete"]=True
 except Exception as e:report["errors"].append(repr(e));report["traceback"]=traceback.format_exc()
 report["requests"]=NUM;report["denied_hosts"]=sorted(DENIED);save("REPORT.json",report)
 print(json.dumps({"complete":report["complete"],"requests":NUM,"markets":len(report["markets"]),
   "sample_liquidation_events":sum(w.get("event_count",0) for m in report["markets"] for w in m.get("historical_liquidations_sample",[])),
   "errors":report["errors"]},indent=2),flush=True)
 if not report["complete"]:raise SystemExit("Incomplete research; errors and missing market evidence retained")
if __name__=="__main__":main()
