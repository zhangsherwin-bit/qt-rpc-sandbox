"""Read-only calendar-cohort test. No signing, broadcasting or asset endowments."""
from pathlib import Path
import hashlib, importlib.util, json, sys, time, traceback, urllib.request
OUT=Path('evidence')
SOURCE='https://raw.githubusercontent.com/zhangsherwin-bit/qt-rpc-sandbox/617c910731c6d0b0f76d23863389120358246b4e/direct_exit/run.py'
FROZEN_SHA='4fc4e36cebafd8a921f5cabe82c2aec5c541288d422515b80a1e46bc15d0c75d'
EXPECTED_RUNTIME='15511d2f00b5c9b0bd03e4d12ea0373e4774ab2cd34df4ceb2df542264b58db6'
TOPIC='0x143f1f8e861fbdeddd5b46e844b7d3ac7b86a122f36e8c463859ee6811b1f29c'
START=1788220800
END=START+86400
MIN_SOLD=5000*10**18
MIN_BLOCK_GAP=300

def decode(log):
    if log.get('removed') or not log.get('topics') or log['topics'][0].lower()!=TOPIC: return None
    raw=log.get('data','')
    if not raw.startswith('0x') or len(raw)!=386: raise ValueError('unexpected swap event schema')
    w=[int(raw[i:i+64],16) for i in range(2,len(raw),64)]
    if w[0]!=0 or w[2]!=1 or w[1]<MIN_SOLD:return None
    return {'block':int(log['blockNumber'],16),'index':int(log['transactionIndex'],16),'log_index':int(log['logIndex'],16),'block_hash':log['blockHash'],'tx':log['transactionHash'],'crv_sold_raw':str(w[1]),'weth_received_raw':str(w[3])}

def select(logs):
    hits=[r for l in logs if (r:=decode(l)) is not None]
    hits.sort(key=lambda x:(x['block'],x['index'],x['log_index']))
    chosen=[]
    for r in hits:
        if not chosen or r['block']-chosen[-1]['block']>=MIN_BLOCK_GAP:
            chosen.append(r)
            if len(chosen)==3:break
    return hits,chosen

def save(name,x):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2))

def bootstrap():
    req=urllib.request.Request(SOURCE,headers={'User-Agent':'QT-Pinned-ReadOnly-Source/1'})
    with urllib.request.urlopen(req,timeout=30) as r:b=r.read(80001)
    if hashlib.sha256(b).hexdigest()!=FROZEN_SHA:raise ValueError('frozen helper hash mismatch')
    p=OUT/'frozen_direct.py';p.write_bytes(b)
    spec=importlib.util.spec_from_file_location('frozen_direct',p);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    if hashlib.sha256(old.body).hexdigest()!='26ddad1c60362ce288061c258445cee7b9cca55673926a6a60c37ae2809a5682':raise ValueError('base helper hash mismatch')
    m=old.m;m.build();runtime=old.compile_alt()
    if hashlib.sha256(bytes.fromhex(runtime[2:])).hexdigest()!=EXPECTED_RUNTIME:raise ValueError('runtime changed')
    return m,runtime

def main():
    OUT.mkdir(exist_ok=True)
    plan={'date':'2026-09-01 UTC','selection':'first 3 canonical swaps in fixed TRI pool selling >=5000 crvUSD for WETH, at least 300 blocks apart; no selection on resulting profit','trigger_topic':TOPIC,'window_start_unix':START,'window_end_unix_exclusive':END,'size_USDC':20000,'entry':'beginning of the following canonical block; no claim of actual arrival or inclusion','route':'frozen direct USDC/WETH/crvUSD/USDC','discovery_controls_USDC':[20000,25000,30000],'scope':'retrospective new calendar cohort plus separate discovery sizing; not prospective validation','request_limit':100,'source_url':SOURCE,'source_sha256':FROZEN_SHA,'runtime_sha256':EXPECTED_RUNTIME,'read_only':True,'no_balance_storage_or_oracle_overrides':True,'no_trades':True,'reserved_Oct3_Oct9_untouched':True}
    save('PLAN.json',plan);summary={'plan':plan,'cases':[],'selection_complete':False,'new_workflow_executed':True}
    m=None
    try:
        m,runtime=bootstrap();assert m.val('chain','eth_chainId',[])=='0x1';headers={}
        def header(n):
            if n not in headers:headers[n]=m.val('header_'+str(n),'eth_getBlockByNumber',[hex(n),False])
            return headers[n]
        def lower(ts):
            lo,hi=25868888,25898888
            assert int(header(lo)['timestamp'],16)<ts<=int(header(hi)['timestamp'],16)
            while hi-lo>1:
                mid=(lo+hi)//2
                if int(header(mid)['timestamp'],16)<ts:lo=mid
                else:hi=mid
            return hi
        a,b=lower(START),lower(END)
        assert b>a and b-a<=10000
        summary['block_window']=[a,b-1]
        # One <=10k-block log query, conservatively paced as an expensive request.
        time.sleep(max(0,70-(time.monotonic()-m.LAST)))
        logs=m.val('calendar_pool_logs','eth_getLogs',[{'fromBlock':hex(a),'toBlock':hex(b-1),'address':m.TRI,'topics':[TOPIC]}])
        assert isinstance(logs,list)
        save('calendar_logs.json',logs)
        assert all(a<=int(l['blockNumber'],16)<b and l['address'].lower()==m.TRI for l in logs)
        identities=[(l['transactionHash'],l['logIndex']) for l in logs];assert len(set(identities))==len(identities)
        hits,chosen=select(logs);summary.update(logs_returned=len(logs),qualifying_swaps=len(hits),selected=chosen,selection_complete=True)
        save('SELECTED_BEFORE_QUOTES.json',summary)
        save('headers_selection.json',headers)
        for i,x in enumerate(chosen):
            h=header(x['block']);assert h['hash']==x['block_hash']
            receipt=m.val('selected_receipt_'+str(i),'eth_getTransactionReceipt',[x['tx']]);assert receipt['status']=='0x1' and receipt['blockHash']==h['hash']
            assert any(l['transactionHash']==x['tx'] and int(l['logIndex'],16)==x['log_index'] for l in receipt['logs'])
            save('triggers/sep01_'+str(i)+'.json',{'header':h,'receipt':receipt})
            for who,addr in [('probe',m.PROBE),('caller',m.CALLER)]:assert m.val(who+'_code_'+str(i),'eth_getCode',[addr,h['number']])=='0x'
            seed={'label':'calendar_Sep01_'+str(i),'block':x['block'],'hash':h['hash'],'tx':x['tx']}
            c=m.simulate(seed,1,20000,runtime,headers);c['sample_role']='new_calendar_cohort';summary['cases'].append(c);save('SUMMARY.json',summary)
            print(json.dumps({k:v for k,v in c.items() if k not in ('parent','target','response')}),flush=True)
        # Discovery sizing is separate and cannot change the cohort rule above.
        seed=m.SEEDS[0];assert header(seed['block'])['hash']==seed['hash']
        for usd in (20000,25000,30000):
            c=m.simulate(seed,1,usd,runtime,headers);c['sample_role']='discovery_sizing';summary['cases'].append(c);save('SUMMARY.json',summary)
            print(json.dumps({k:v for k,v in c.items() if k not in ('parent','target','response')}),flush=True)
    except Exception as e:summary.update(exception=repr(e),traceback=traceback.format_exc())
    summary.update(rpc_requests=m.COUNT if m else 0,provider_stop=m.STOP if m else None,transactions_sent=0)
    save('SUMMARY.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('cases','plan','traceback')},indent=2),flush=True)

def tests():
    import unittest
    class Checks(unittest.TestCase):
        def row(self,block=10,amount=MIN_SOLD,direction=(0,1)):
            return {'topics':[TOPIC],'data':'0x'+''.join(f'{x:064x}' for x in [direction[0],amount,direction[1],10**18,0,0]),'blockNumber':hex(block),'transactionIndex':'0x0','logIndex':'0x0','transactionHash':hex(block),'blockHash':hex(block+1)}
        def test_amount_threshold(self):self.assertIsNone(decode(self.row(amount=MIN_SOLD-1)));self.assertIsNotNone(decode(self.row()))
        def test_direction(self):self.assertIsNone(decode(self.row(direction=(1,0))))
        def test_spacing_and_cap(self):self.assertEqual([x['block'] for x in select([self.row(n) for n in [1000,310,10,11,610]])[1]],[10,310,610])
        def test_malformed(self):
            r=self.row();r['data']='0x'
            with self.assertRaises(ValueError):decode(r)
        def test_removed(self):r=self.row();r['removed']=True;self.assertIsNone(decode(r))
        def test_empty(self):self.assertEqual(select([]),([],[]))
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)

if __name__=='__main__':
    if '--self-test' in sys.argv:tests()
    else:main()
