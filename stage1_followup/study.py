"""Read-only Stage 1: relayer repayment provenance and protocol sale inventory.
No signing, sending, fund endowment, access bypass or production-state changes.
All economic amounts are integers; returned quotes are not execution profits.
"""
from __future__ import annotations
import argparse, collections, datetime as dt, hashlib, json, re, time
from pathlib import Path
import urllib.request, urllib.error
from keccak_view import keccak256, selector

RPC={1:'https://rpc-eth.blockmachine.io',8453:'https://mainnet.base.org'}
TOKEN={1:'0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',8453:'0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'}
SPOKE={1:'0x5c7bcd6e7de5423a257d81b442095a1a6ced35c5',8453:'0x09aea4b2242abc8bb4bb78d537a67a245a7bec64'}
COMET={1:'0xc3d688b66703497daa19211eedff47f25384cdc3',8453:'0xb125e6687d4313864e53df431d5425969c15eb2f'}
QUOTE={1:'0x61ffe014ba17989e743c5f6cb21bf9697530b21e',8453:'0x3d4e44eb1374240ce5f1b871ab261cd16335b76a'}
ALLOWED={'eth_chainId','eth_blockNumber','eth_getBlockByNumber','eth_getCode','eth_getLogs','eth_call','eth_getTransactionReceipt'}
FILL_SIG='FilledRelay(bytes32,bytes32,uint256,uint256,uint256,uint256,uint256,uint32,uint32,bytes32,bytes32,bytes32,bytes32,bytes32,(bytes32,bytes32,uint256,uint8))'
REFUND_SIG='ExecutedRelayerRefundRoot(uint256,uint256,uint256[],uint32,uint32,address,address[],bool,address)'
LEGACY_REFUND_SIG='ExecutedRelayerRefundRoot(uint256,uint256,uint256[],uint32,uint32,address,address[],address)'
def topic(s): return '0x'+keccak256(s.encode()).hex()
FILL=topic(FILL_SIG);REFUND=topic(REFUND_SIG);LEGACY_REFUND=topic(LEGACY_REFUND_SIG)
CLAIM=topic('ClaimedRelayerRefund(bytes32,bytes32,uint256,address)')
TRANSFER=topic('Transfer(address,address,uint256)')

def words(s):
    if not isinstance(s,str) or not re.fullmatch(r'0x(?:[0-9a-fA-F]{64})*',s): raise ValueError('Malformed ABI words')
    return [int(s[i:i+64],16) for i in range(2,len(s),64)]
def address(x):
    v=int(x,16) if isinstance(x,str) else int(x)
    if not 0<=v<2**160: raise ValueError('Not an EVM address')
    return '0x'+format(v,'040x')
def enc(v): return format(int(v,16) if isinstance(v,str) else int(v),'064x')
def scalar(s,signed=False):
    w=words(s)
    if len(w)!=1: raise ValueError('Not a scalar')
    v=w[0]
    return v-2**256 if signed and v>=2**255 else v

def decode_fill(log):
    if log['topics'][0].lower()!=FILL: return None
    w=words(log['data']);t=log['topics']
    if len(w)!=15 or len(t)!=4: raise ValueError('Unexpected fill ABI')
    return {'spoke':log['address'].lower(),'origin':int(t[1],16),'deposit_id':str(int(t[2],16)),
      'repayment_address':address(t[3]),'repayment_chain':w[4],
      'input_token':address(w[0]),'output_token':address(w[1]),'input_raw':str(w[2]),
      'original_output_raw':str(w[3]),'updated_output_raw':str(w[13]),'fill_type':w[14],
      'recipient':address(w[9]),'updated_recipient':address(w[11]),'exclusive_relayer':address(w[7]),
      'exclusivity_deadline':w[6],'tx':log['transactionHash'],'block':int(log['blockNumber'],16)}

def decode_refund(log):
    t=log['topics'];signature=t[0].lower()
    if signature not in (REFUND,LEGACY_REFUND): return None
    w=words(log['data']);header=6 if signature==REFUND else 5
    if len(t)!=4 or len(w)<header: raise ValueError('Unexpected refund ABI')
    def arr(off):
        if off%32 or off//32<header or off//32>=len(w): raise ValueError('Bad array offset')
        i=off//32;n=w[i]
        if n>500 or i+1+n>len(w): raise ValueError('Bad array length')
        return w[i+1:i+1+n]
    amounts,accounts=arr(w[1]),arr(w[3])
    if len(amounts)!=len(accounts): raise ValueError('Parallel arrays differ')
    if signature==REFUND and w[4] not in (0,1): raise ValueError('Invalid deferred flag')
    return {'chain':int(t[1],16),'root_bundle_id':int(t[2],16),'leaf_id':int(t[3],16),
       'spoke':log['address'].lower(),'token':address(w[2]),'deferred':bool(w[4]) if header==6 else False,
       'tx':log['transactionHash'],'block':int(log['blockNumber'],16),'log_index':int(log['logIndex'],16),
       'payments':[{'recipient':address(a),'raw':str(v)} for a,v in zip(accounts,amounts)]}

def refund_receipt_check(receipt,target):
    """Compare all non-deferred leaves and real token transfers in ONE receipt.
    This verifies aggregate delivery, never invents a link to one deposit.
    """
    expected=collections.Counter();actual=collections.Counter()
    for log in receipt['logs']:
        r=decode_refund(log)
        if r and not r['deferred']:
            for p in r['payments']:
                k=(r['spoke'],r['token'],p['recipient'])
                if k in target: expected[k]+=int(p['raw'])
        if log['topics'][0].lower()==TRANSFER and len(log['topics'])==3:
            k=(address(log['topics'][1]),log['address'].lower(),address(log['topics'][2]))
            if k in target: actual[k]+=scalar(log['data'])
    return [{'spoke':k[0],'token':k[1],'recipient':k[2],
      'expected_raw':str(expected[k]),'transferred_raw':str(actual[k]),
      'equal':expected[k]==actual[k] and expected[k]>0} for k in sorted(target)]

def write(root,name,obj):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2)+'\n')

class Client:
    def __init__(self,out): self.out=out;self.n=0;self.denied=set();self.cache={};self.last_heavy={};self.start=time.monotonic()
    def rpc(self,chain,name,method,params):
        if chain not in RPC or method not in ALLOWED: raise ValueError('Unapproved read')
        if chain in self.denied: raise RuntimeError('Stop after provider refusal')
        if method=='eth_getLogs':
            f=params[0]
            if not f.get('address') or int(f['toBlock'],16)-int(f['fromBlock'],16)>=10000: raise ValueError('Unbounded log filter')
        key=json.dumps([chain,method,params],sort_keys=True)
        if key in self.cache:return self.cache[key]
        if self.n>=240 or time.monotonic()-self.start>1400:raise RuntimeError('Fixed request/time cap reached')
        if method=='eth_getLogs':
            time.sleep(max(0,70-(time.monotonic()-self.last_heavy.get(chain,-100))))
            self.last_heavy[chain]=time.monotonic()
        else: time.sleep(0.5)
        self.n+=1;body=b'';payload={'jsonrpc':'2.0','id':self.n,'method':method,'params':params}
        meta={'name':name,'chain':chain,'payload':payload,'url':RPC[chain],
              'requested_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'UNAVAILABLE'}
        try:
            req=urllib.request.Request(RPC[chain],data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','User-Agent':'QT-Stage1-ReadOnly/1'})
            with urllib.request.urlopen(req,timeout=25) as res:meta['http_status']=res.status;body=res.read(5_000_001)
            if len(body)>5_000_000:raise ValueError('Response body exceeds cap')
            p=json.loads(body)
            if 'error' in p:
                meta['rpc_error']=p['error'];msg=str(p['error']).lower()
                if any(t in msg for t in ('rate limit','access denied','unauthorized','client adjustable limit')):self.denied.add(chain)
                raise RuntimeError(str(p['error']))
            if 'result' not in p:raise ValueError('No RPC result')
            meta['status']='OK';self.cache[key]=p['result'];return p['result']
        except urllib.error.HTTPError as exc:
            meta.update(http_status=exc.code,error=str(exc));body=exc.read(100000)
            if exc.code in (401,403,429):self.denied.add(chain)
            raise
        except Exception as exc:meta['error']=repr(exc);raise
        finally:
            meta['sha256']=hashlib.sha256(body).hexdigest();meta['length']=len(body)
            (self.out/'raw').mkdir(parents=True,exist_ok=True)
            (self.out/f'raw/{self.n:04d}.body').write_bytes(body)
            write(self.out,f'raw/{self.n:04d}.json',meta)
    def call(self,chain,to,sig,args,block,signed=False):
        data=selector(sig)+''.join(enc(a) for a in args)
        r=self.rpc(chain,sig,'eth_call',[{'to':to,'data':data},hex(block)])
        return scalar(r,signed)


def load_cases(inp):
    out=[]
    for p in sorted((inp/'across').glob('*_detail.json')):
        d=json.loads(p.read_text())['deposit']
        out.append({'origin':int(d['originChainId']),'destination':int(d['destinationChainId']),
          'deposit_id':str(d['depositId']),'fill_tx':d['fillTx'],'fill_block':d['fillBlockNumber'],
          'input_raw':d['inputAmount'],'output_raw':d['outputAmount'],'source':p.name})
    if len(out)!=6:raise ValueError('Expected exactly the original six cases')
    return out

def across(c,report,inp,headers):
    r={'source':'The six previously captured Stage1 API examples, frozen before this run',
       'cases':[],'refund_events':[],'verified_receipt_payments':[],'errors':[],
       'deposit_to_refund_attribution':'NOT ESTABLISHED: refunds aggregate many fills and may include other corridors'}
    report['across']=r
    for case in load_cases(inp):
        row=dict(case);r['cases'].append(row)
        try:
            receipt=c.rpc(case['destination'],'frozen_fill_receipt','eth_getTransactionReceipt',[case['fill_tx']])
            if not receipt or receipt['status']!='0x1':raise ValueError('Missing successful fill')
            fs=[decode_fill(l) for l in receipt['logs'] if l['topics'][0].lower()==FILL]
            matches=[x for x in fs if x['deposit_id']==case['deposit_id'] and x['origin']==case['origin']]
            if len(matches)!=1:raise ValueError('Ambiguous deposit-to-fill link')
            x=matches[0]
            if x['spoke']!=SPOKE[case['destination']]:raise ValueError('Unexpected spoke')
            if x['input_raw']!=case['input_raw'] or x['updated_output_raw']!=case['output_raw']:raise ValueError('API/event amount mismatch')
            row.update(fill=x,fill_sender=receipt['from'].lower(),fill_tx_event_count=len(fs),
               transaction_gas_wei=str(int(receipt['gasUsed'],16)*int(receipt['effectiveGasPrice'],16)),
               transaction_l1_fee_wei=str(int(receipt.get('l1Fee','0x0'),16)),
               gas_allocation='whole transaction; do not assign twice to batched fills')
            write(c.out,'REPORT.json',report)
        except Exception as exc:row['error']=repr(exc)
    targets=collections.defaultdict(set)
    for x in r['cases']:
        f=x.get('fill',{})
        if f.get('repayment_chain') in RPC:targets[f['repayment_chain']].add(f['repayment_address'])
    for chain,accounts in targets.items():
        try:
            tip=headers[chain];end=int(tip['number'],16)
            # Pin end first. Latest maximum 6h; older obligations are expressly omitted.
            lo=max(0,end-(1800 if chain==1 else 10800)+1)
            r.setdefault('windows',[]).append({'chain':chain,'from_block':lo,'through_block':end,'end_hash':tip['hash'],'recipients':sorted(accounts)})
            for begin in range(lo,end+1,10000):
                logs=c.rpc(chain,'refund_leaves','eth_getLogs',[{'address':SPOKE[chain],
                    'topics':[[REFUND,LEGACY_REFUND,CLAIM]],'fromBlock':hex(begin),'toBlock':hex(min(begin+9999,end))}])
                for l in logs:
                    rr=decode_refund(l)
                    if rr:
                        rr['target_payments']=[p for p in rr['payments'] if p['recipient'] in accounts]
                        r['refund_events'].append(rr)
                    elif l['topics'][0].lower()==CLAIM:
                        r.setdefault('deferred_claim_events',[]).append(l)
            seen=set()
            for rr in r['refund_events']:
                if rr['chain']!=chain or not rr['target_payments'] or rr['deferred'] or rr['tx'] in seen:continue
                if len(seen)>=8:break
                seen.add(rr['tx'])
                receipt=c.rpc(chain,'refund_receipt','eth_getTransactionReceipt',[rr['tx']])
                ts={(e['spoke'],e['token'],p['recipient']) for e in r['refund_events'] if e['tx']==rr['tx'] and not e['deferred'] for p in e['target_payments']}
                checks=refund_receipt_check(receipt,ts)
                r['verified_receipt_payments'].append({'chain':chain,'tx':rr['tx'],'status':receipt['status'],'payments':checks})
            # Recheck pinned hash without assuming unchanged latest state.
            check=c.rpc(chain,'recheck_pin','eth_getBlockByNumber',[tip['number'],False])
            if check['hash']!=tip['hash']:raise ValueError('Pinned block changed')
        except Exception as exc:r['errors'].append({'chain':chain,'error':repr(exc)})
        write(c.out,'REPORT.json',report)

def compound(c,report,headers):
    r={'scope':'Two USDC Comet deployments, each current pin plus one prior recorded historical block',
       'kind':'Protocol inventory and permissioned-sale gates; quotations only; NOT full cash simulation',
       'states':[]};report['compound']=r
    for chain in (1,8453):
        for bn in sorted(set([26093737 if chain==1 else 52634077,int(headers[chain]['number'],16)])):
            row={'chain':chain,'comet':COMET[chain],'block':bn,'assets':[]};r['states'].append(row)
            try:
                head=c.rpc(chain,'comet_header','eth_getBlockByNumber',[hex(bn),False]);row['block_hash']=head['hash'];row['timestamp']=int(head['timestamp'],16)
                base=address(c.call(chain,COMET[chain],'baseToken()',[],bn))
                if base!=TOKEN[chain]:raise ValueError('Wrong base token')
                n=c.call(chain,COMET[chain],'numAssets()',[],bn)
                if not 0<n<=20:raise ValueError('Asset count exceeds fixed scope')
                reserve=c.call(chain,COMET[chain],'getReserves()',[],bn,True)
                target=c.call(chain,COMET[chain],'targetReserves()',[],bn)
                paused=c.call(chain,COMET[chain],'isBuyPaused()',[],bn)
                row.update(base_reserves_raw=str(reserve),target_raw=str(target),buy_paused=bool(paused),sale_gate_open=reserve<target and paused==0)
                for i in range(n):
                    dat=selector('getAssetInfo(uint8)')+enc(i)
                    w=words(c.rpc(chain,'asset_info','eth_call',[{'to':COMET[chain],'data':dat},hex(bn)]))
                    if len(w)!=8:raise ValueError('Unexpected asset info ABI')
                    a=address(w[1]);available=c.call(chain,COMET[chain],'getCollateralReserves(address)',[a],bn)
                    ar={'address':a,'scale':str(w[3]),'liquidation_factor':str(w[6]),'inventory_raw':str(available),'quotes':[]};row['assets'].append(ar)
                    if available==0 or not row['sale_gate_open']:continue
                    for dollars in (100,1000,10000):
                        amount=dollars*10**6
                        q=c.call(chain,COMET[chain],'quoteCollateral(address,uint256)',[a,amount],bn)
                        qr={'purchase_usdc_raw':str(amount),'collateral_quoted_raw':str(q),'fits_inventory':q<=available};ar['quotes'].append(qr)
                        if q>available or q==0:continue
                        exits=[];qr['dex_quotes']=exits
                        for fee in (500,3000):
                            try:
                                data=selector('quoteExactInputSingle((address,address,uint256,uint24,uint160))')+enc(a)+enc(base)+enc(q)+enc(fee)+enc(0)
                                v=words(c.rpc(chain,'exit_quote','eth_call',[{'to':QUOTE[chain],'data':data},hex(bn)]))
                                if len(v)!=4:raise ValueError('Invalid QuoterV2 output')
                                exits.append({'fee':fee,'cash_out_raw':str(v[0]),'sqrt_after':str(v[1]),'gross_quote_margin_raw':str(v[0]-amount),
                                    'actual_input_consumption_unverified':True,'full_execution_performed':False})
                            except Exception as exc:exits.append({'fee':fee,'error':repr(exc)})
                    write(c.out,'REPORT.json',report)
                if c.rpc(chain,'recheck_comet_hash','eth_getBlockByNumber',[hex(bn),False])['hash']!=head['hash']:raise ValueError('Block changed')
                row['views_complete']=True
            except Exception as exc:row['error']=repr(exc)
            write(c.out,'REPORT.json',report)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,default=Path('evidence'));args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True);c=Client(args.output)
    report={'scope':'Stage1 bounded read-only relayer-cash provenance and new protocol-inventory source',
      'new_profit_execution':False,'no_signing_or_broadcast':True,'across':None,'compound':None,
      'warnings':['Aggregate refund recipient match is NOT deposit-specific reimbursement proof',
        'Token prices, capital costs, rebates and costs on other chains remain unmeasured',
        'Compound collateral quotes are not completed purchase/exit executions',
        'Time snapshots are not a complete opportunity census','Unused and missing data are not zero profit']}
    try:
        headers={}
        for chain in RPC:
            if int(c.rpc(chain,'chain_id','eth_chainId',[]),16)!=chain:raise ValueError('Wrong network')
            h=c.rpc(chain,'pin','eth_getBlockByNumber',['latest',False]);headers[chain]=h
        report['pins']=headers;write(c.out,'REPORT.json',report)
        compound(c,report,headers)
        across(c,report,args.input,headers)
    except Exception as exc:report['exception']=repr(exc)
    report['new_rpc_requests']=c.n;report['provider_stopped_chains']=sorted(c.denied)
    report['all_required_reads_complete']=bool(report.get('across') and not report['across']['errors'] and all('fill' in x for x in report['across']['cases']) and report.get('compound') and all(x.get('views_complete') for x in report['compound']['states']))
    write(c.out,'REPORT.json',report)
    print(json.dumps(report,indent=2),flush=True)
    if not report['all_required_reads_complete']:raise SystemExit('Required observations incomplete; raw evidence retained')
if __name__=='__main__':main()
