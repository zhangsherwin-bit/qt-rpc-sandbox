"""Read-only completion of already pinned Ethereum asset inventory.
Only the omitted rows and failed price inputs are read. Base is deliberately
not contacted following the previous provider refusal. No purchases or sends.
"""
from pathlib import Path
import json, sys, hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage1_followup'))
import study as S

class Limited(S.Client):
    def rpc(self,chain,name,method,params):
        if chain!=1: raise ValueError('This continuation never contacts Base')
        if self.n>=65: raise RuntimeError('65-call completion budget exhausted')
        if method=='eth_getLogs': raise ValueError('No log scan in this continuation')
        return super().rpc(chain,name,method,params)

def cached(path):
    entries={};n=0
    for p in sorted((path/'raw').glob('*.json')):
        m=json.loads(p.read_text());b=p.with_suffix('.body').read_bytes()
        assert hashlib.sha256(b).hexdigest()==m['sha256']
        assert len(b)==m['length']
        n+=1
        if m['status']=='OK':
            q=m['payload'];entries[json.dumps([m['chain'],q['method'],q['params']],sort_keys=True)]=json.loads(b)['result']
    return entries,n

def read_cached(entries,to,sig,args,bn):
    data=S.selector(sig)+''.join(S.enc(a) for a in args)
    key=json.dumps([1,'eth_call',[{'to':to,'data':data},hex(bn)]],sort_keys=True)
    return entries[key]

def work():
    inp=Path('input_previous');out=Path('evidence');out.mkdir(exist_ok=True)
    previous=json.loads((inp/'REPORT.json').read_text())
    entries,n=cached(inp)
    c=Limited(out);report={'kind':'Completion of exact previous two Ethereum inventory snapshots',
      'new_strategy_execution':False,'cached_responses_verified':n,'base_not_contacted':True,
      'states':[],'completed_defined_scope':False,
      'notes':['Errors for an individual asset are preserved, not converted to zero reserves',
       'No new latest state or oracle modification; original block hash must match',
       'A quote is not a cash-settled transaction and no income is claimed']}
    try:
        assert int(c.rpc(1,'chain','eth_chainId',[]),16)==1
        for orig in previous['compound']['states']:
            if orig['chain']!=1:continue
            bn=orig['block'];comet=orig['comet']
            head=c.rpc(1,'pinned_state','eth_getBlockByNumber',[hex(bn),False])
            assert head['hash']==orig['block_hash']
            expected=S.scalar(read_cached(entries,comet,'numAssets()',[],bn))
            row={'block':bn,'block_hash':head['hash'],'expected_assets':expected,
                 'prior_fully_read_assets':len(orig['assets'])-1,'added_or_repaired':[]}
            report['states'].append(row)
            sf=c.call(1,comet,'storeFrontPriceFactor()',[],bn)
            base_feed=S.address(c.call(1,comet,'baseTokenPriceFeed()',[],bn))
            base_price=c.call(1,comet,'getPrice(address)',[base_feed],bn)
            row.update(storefront_factor_raw=str(sf),base_price_raw=str(base_price),base_feed=base_feed)
            for index in range(len(orig['assets'])-1,expected):
                item={'asset_index':index,'quotes':[]};row['added_or_repaired'].append(item)
                try:
                    data=S.selector('getAssetInfo(uint8)')+S.enc(index)
                    w=S.words(c.rpc(1,'remaining_asset_info','eth_call',[{'to':comet,'data':data},hex(bn)]))
                    assert len(w)==8 and w[0]==index
                    asset,feed=S.address(w[1]),S.address(w[2])
                    inv=c.call(1,comet,'getCollateralReserves(address)',[asset],bn)
                    item.update(asset=asset,price_feed=feed,scale_raw=str(w[3]),liquidation_factor_raw=str(w[6]),inventory_raw=str(inv),inventory_observed=True)
                    try:
                        p=c.call(1,comet,'getPrice(address)',[feed],bn)
                        discount=sf*(10**18-w[6])//10**18
                        discounted=p*(10**18-discount)//10**18
                        item.update(oracle_price_raw=str(p),discount_factor_raw=str(discount),discounted_price_raw=str(discounted))
                    except Exception as e:item['price_error']=repr(e)
                    if not inv:
                        item['disposition']='NO_INVENTORY';continue
                    for usdc in (100,1000,10000):
                        q={'purchase_usdc_raw':str(usdc*10**6)};item['quotes'].append(q)
                        try:
                            amount=c.call(1,comet,'quoteCollateral(address,uint256)',[asset,usdc*10**6],bn)
                            q.update(collateral_raw=str(amount),fits_inventory=0<amount<=inv)
                        except Exception as e:
                            q['error']=repr(e)
                            item['disposition']='QUOTE_UNAVAILABLE'
                            break
                    else:item['disposition']='QUOTED_NOT_EXECUTED'
                except Exception as e:item['error']=repr(e)
                S.write(out,'COMPLETION.json',report)
                if c.denied:raise RuntimeError('Provider refused; stop')
            assert c.rpc(1,'recheck_pin','eth_getBlockByNumber',[hex(bn),False])['hash']==head['hash']
        report['completed_defined_scope']=all(all(x.get('inventory_observed') for x in s['added_or_repaired']) and s['prior_fully_read_assets']+len(s['added_or_repaired'])==s['expected_assets'] for s in report['states'])
    except Exception as e:report['exception']=repr(e)
    report['new_rpc_requests']=c.n;report['provider_stopped']=sorted(c.denied)
    S.write(out,'COMPLETION.json',report)
    print(json.dumps(report,indent=2),flush=True)
    if not report['completed_defined_scope']:raise SystemExit('Asset observation coverage incomplete')
if __name__=='__main__':work()
