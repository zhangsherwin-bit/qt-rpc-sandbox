"""Bounded read-only Morpho Midnight and Base RPC probe for GitHub Actions.

All requests are to two explicitly allowlisted public HTTPS endpoints. No secrets,
wallets, eth_sendRawTransaction, generic url inputs, external installs or trade code.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

API = 'https://api.morpho.org'
RPC = 'https://mainnet.base.org'
CORE = '0xAdedD8ab6dE832766Fedf0FaC4992E5C4D3EA18A'
USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
WETH = '0x4200000000000000000000000000000000000006'
MARKETS = [
    '0x9593c3a6dba45b6106af8dc8b45ba8c505d90d3d68a3d33f7c278dd921b637da',
    '0x6cb9f4a081803895ee5f8cb611c9a7ad7ccadd88d8a8343f478d9e5646efecac',
    '0x0ff32a563814a0e5822441b77c1b463da99f095d686cb09b637d5d80418cffed',
    '0x43d6120738c57b2bc5835901f8250fdf7fc8054efbb006c6ccba61ec898e5ed9',
]
SEL_WITHDRAWABLE = '7cf43d8c'
SEL_BALANCEOF = '70a08231'
SEL_TOTALSUPPLY = '18160ddd'
HISTORICAL_BLOCK = 52601237  # From the user's 14 October 2026 saved evidence
MAX_REQUESTS = 30
MAX_BYTES = 1_000_000


def is_safe_call(url: str, payload: dict | None) -> bool:
    if payload is None:
        return url.startswith(API+'/v0/midnight/') and len(url)<500
    return url == RPC and payload.get('jsonrpc') == '2.0' and payload.get('method') in {
        'eth_chainId','eth_blockNumber','eth_getBlockByNumber','eth_getCode','eth_call'
    }


class Client:
    def __init__(self, output: Path):
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.calls = 0
        self.records = []

    def request(self, name: str, url: str, payload: dict | None = None):
        assert is_safe_call(url, payload), 'Unapproved endpoint or RPC method'
        if self.calls >= MAX_REQUESTS:
            raise RuntimeError('Fixed read-only request budget exhausted')
        self.calls += 1
        data = json.dumps(payload).encode('utf-8') if payload is not None else None
        headers = {'User-Agent':'QT-GPT6-ReadOnly-Research/2026-10-15', 'Accept':'application/json'}
        if data is not None:
            headers['Content-Type']='application/json'
        record = {'name':name,'url':url,'method':'POST' if data else 'GET',
                  'payload':payload, 'request_number':self.calls,'status':'UNAVAILABLE'}
        body = b''
        try:
            req=urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=18) as res:
                record['http_status']=res.status
                body=res.read(MAX_BYTES+1)
                if len(body)>MAX_BYTES:
                    raise ValueError('Exceeded fixed maximum response size')
            parsed=json.loads(body)
            record['status']='RPC_ERROR' if payload is not None and isinstance(parsed,dict) and 'error' in parsed else 'OK'
            result=parsed
        except urllib.error.HTTPError as exc:
            record['http_status']=exc.code
            body=exc.read(50000)
            record['status']='HTTP_ERROR'
            record['error']=str(exc)
            result=None
        except Exception as exc:
            record['status']='UNAVAILABLE'
            record['error']=f'{type(exc).__name__}: {exc}'
            result=None
        record['response_sha256']=hashlib.sha256(body).hexdigest()
        record['response_bytes']=len(body)
        (self.output/f'{self.calls:02d}_{name}.body').write_bytes(body)
        (self.output/f'{self.calls:02d}_{name}.meta.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        self.records.append(record)
        # Respect providers even when GitHub-hosted network is fast.
        time.sleep(0.45)
        return result

    def get(self, name, path):
        return self.request(name, API+path)

    def rpc(self, name, method, params):
        payload={'jsonrpc':'2.0','id':self.calls+1,'method':method,'params':params}
        r=self.request(name, RPC, payload)
        if not isinstance(r,dict) or 'error' in r:
            return None
        return r.get('result')


def call_uint(client: Client,name: str,to: str, data: str, block: str):
    r=client.rpc(name,'eth_call',[{'to':to,'data':data},block])
    if not isinstance(r,str) or not r.startswith('0x'):
        return None
    try:return int(r,16)
    except ValueError:return None


def run(output: Path):
    c=Client(output/'raw')
    d={'research_date':'2026-10-15','scope':'Base Morpho Midnight selected markets (not a census)',
       'methods':'read only; no keys, wallet, transfers, signatures or trade simulation',
       'historical_block':HISTORICAL_BLOCK,'market_ids':MARKETS,
       'all_requests_succeeded':False,'profitable_opportunity_verified':False,
       'no_trade_submitted':True,'warnings':['REST book data is not block-atomic with RPC state.',
       'ABI selectors assume the pinned reviewed Midnight contract. Runtime/source equivalence not checked.',
       'Book rows are not validated executable offers; quote and full EVM execution are not implemented.',
       'Provider rate and archive policies may reject requests from GitHub-hosted IPs.']}
    chain=c.rpc('chainid','eth_chainId',[])
    d['chain_id']=chain
    latest=c.rpc('blocknumber','eth_blockNumber',[])
    d['latest_block']=latest
    b=c.rpc('block_latest','eth_getBlockByNumber',[latest,False]) if latest else None
    d['latest_block_hash']=b.get('hash') if isinstance(b,dict) else None
    if chain!='0x2105' or not isinstance(b,dict):
        d['error']='Base chain not verified; stopping before market reads'
    else:
        block=b['number']
        core_code=c.rpc('core_code','eth_getCode',[CORE,block])
        d['core_code_nonempty']=isinstance(core_code,str) and len(core_code)>2
        d['core_code_sha256']=hashlib.sha256(bytes.fromhex(core_code[2:])).hexdigest() if d['core_code_nonempty'] else None
        d['usdc_core_token_balance']=call_uint(c,'usdc_core_custody',USDC,'0x'+SEL_BALANCEOF+CORE[2:].lower().rjust(64,'0'),block)
        historical='0x'+format(HISTORICAL_BLOCK,'x')
        hist_head=c.rpc('historic_header','eth_getBlockByNumber',[historical,False])
        d['historical_header_available']=isinstance(hist_head,dict)
        d['historical_eth_call_totalSupply_WETH']=call_uint(c,'historic_eth_call',WETH,'0x'+SEL_TOTALSUPPLY,historical)
        d['markets']=[]
        for i,mid in enumerate(MARKETS,1):
            rec={'market_id':mid}
            rec['withdrawable_base_units']=call_uint(c,f'm{i}_withdrawable',CORE,'0x'+SEL_WITHDRAWABLE+mid[2:],block)
            for key,path in (
                ('state',f'/v0/midnight/markets/{mid}/state'),
                ('asks',f'/v0/midnight/books/{mid}/asks/takeable-offers'),
                ('bids',f'/v0/midnight/books/{mid}/bids/takeable-offers')):
                res=c.get(f'm{i}_{key}',path)
                rec[key+'_retrieved']=isinstance(res,dict)
                rec[key+'_count']=len(res['data']) if isinstance(res,dict) and isinstance(res.get('data'),list) else None
            d['markets'].append(rec)
    d['request_count']=c.calls
    d['status_counts']={k:sum(r['status']==k for r in c.records) for k in ('OK','RPC_ERROR','HTTP_ERROR','UNAVAILABLE')}
    d['all_requests_succeeded']=bool(c.records) and all(r['status']=='OK' for r in c.records)
    (output/'report.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
    print(json.dumps(d,indent=2))
    return d

if __name__=='__main__':
    result=run(Path(os.environ.get('QT_OUTPUT_DIR','evidence')))
    # Do not fail the GitHub job on provider errors; preserve the diagnostic artifact.
    sys.exit(0)
