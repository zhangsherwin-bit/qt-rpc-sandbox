"""Read-only, keyless Stage 1 data-provider readiness check. No strategy tests."""
import datetime,json,pathlib,time,urllib.request,urllib.error,urllib.parse

OUT=pathlib.Path('preflight_evidence');OUT.mkdir(exist_ok=True)
rows=[];blocked=set();calls=0
def check(name,url,payload=None):
    global calls
    host=urllib.parse.urlsplit(url).netloc
    if host in blocked:
        rows.append(dict(name=name,host=host,status='SKIPPED_AFTER_DENIAL'));return
    if calls>=22:
        rows.append(dict(name=name,host=host,status='SKIPPED_BUDGET'));return
    if calls:time.sleep(0.5)
    calls+=1
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request(url,data=data,method='POST' if data else 'GET',
         headers={'User-Agent':'QT-Stage1-public-data-preflight/1','Accept':'application/json',
                  'Content-Type':'application/json'})
    x=dict(name=name,host=host,status='UNKNOWN',timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        with urllib.request.urlopen(req,timeout=12) as r:
            body=r.read(65536)
            x.update(status='HTTP_OK',http_status=r.status,content_type=r.headers.get('Content-Type'),bytes_sampled=len(body))
            try:
                v=json.loads(body)
                if isinstance(v,dict) and 'jsonrpc' in v:
                    if v.get('error'):
                        x.update(status='RPC_ERROR',rpc_code=v['error'].get('code'),rpc_message=str(v['error'].get('message'))[:180])
                    else:x['rpc_result_type']=type(v.get('result')).__name__
                elif isinstance(v,dict):x['json_keys']=list(v)[:8]
                elif isinstance(v,list):x['json_shape']='list'
            except Exception:x['body']='JSON truncated or not parseable; reachability only'
    except urllib.error.HTTPError as e:
        x.update(status='HTTP_ERROR',http_status=e.code,error=str(e.reason)[:120])
        if e.code in (401,403,429):blocked.add(host)
    except Exception as e:x.update(status='TRANSPORT_ERROR',error=str(e)[:200])
    rows.append(x);print(json.dumps(x,sort_keys=True),flush=True)

def rpc(name,url,method,params):
    check(name,url,{'jsonrpc':'2.0','id':calls+1,'method':method,'params':params})

check('uniswapx_open_mainnet','https://api.uniswap.org/v2/orders?orderStatus=open&chainId=1&orderType=Dutch_V2&limit=1')
check('uniswapx_open_base','https://api.uniswap.org/v2/orders?orderStatus=open&chainId=8453&orderType=Dutch_V3&limit=1')
check('cow_current_auction','https://api.cow.fi/mainnet/api/v1/auction')
check('cow_solver_competition','https://api.cow.fi/mainnet/api/v2/solver_competition/latest')
check('prediction_market_public','https://gamma-api.polymarket.com/markets?limit=1&active=true&closed=false')
check('prediction_book_public','https://clob.polymarket.com/markets')
check('across_deposits_auth_probe','https://across.to/api/deposits?limit=1')
eth='https://rpc-eth.blockmachine.io'
base='https://mainnet.base.org'
poly='https://polygon-bor-rpc.publicnode.com'
arb='https://arb1.arbitrum.io/rpc'
rpc('ethereum_chainid',eth,'eth_chainId',[])
rpc('ethereum_sep2026_header',eth,'eth_getBlockByNumber',[hex(25946848),False])
rpc('ethereum_historical_state',eth,'eth_call',[{'to':'0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48','data':'0x313ce567'},hex(25946848)])
rpc('base_chainid',base,'eth_chainId',[])
rpc('base_oct2026_header',base,'eth_getBlockByNumber',[hex(52634077),False])
rpc('base_historical_state',base,'eth_call',[{'to':'0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913','data':'0x313ce567'},hex(52634077)])
rpc('polygon_chainid',poly,'eth_chainId',[])
rpc('polygon_historical_header',poly,'eth_getBlockByNumber',[hex(60000000),False])
rpc('arbitrum_chainid',arb,'eth_chainId',[])
rpc('arbitrum_historical_header',arb,'eth_getBlockByNumber',[hex(100000000),False])
report={'kind':'read_only_data_access_preflight','no_trading_or_cash_tests':True,
        'no_credentials_keys_wallets_signed_or_broadcast_transactions':True,
        'runner_location_is_not_user_jurisdiction':True,
        'n_requests':calls,'results':rows,
        'limits':['Current API access does not imply historical off-chain orderbook snapshots.',
         'Basic chain RPC access does not prove archival eth_simulate support.',
         'Endpoint availability does not establish permission to trade or participation eligibility.',
         '401/403/429 are recorded and never bypassed.',
         'HTTP 200 with truncated JSON proves transport, not schema or profitable execution.']}
(OUT/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
print('PREFLIGHT_COMPLETE',len(rows),flush=True)
