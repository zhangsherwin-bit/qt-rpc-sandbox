"""Same calendar and keepers; page the provider's explicit 10000-block limit.
Only same-block historical getters are reused from run 39014404062. No cached
entry is represented as a new observation. Pin and recheck canonical boundaries.
"""
import copy,json
import census as c
ORIGIN='7f4797f486797cdd600c75c24359ed9b30c6530df8639d27974ab03e3a60fe1c'
END=0x18d64da
REG='0x36a04caffc681fa179558b2aaba30395cddd855f'
FEE='0xa2bcd1a4efbd04b63cd03f5aff2561106ebcce00'
CRV='0xf939e0a03fb07f59a73314e73794be0e57ac1b4e'
DATA={
 'USDC':('0x4dece678ceceb27446b35c672dc7d61f30bad69e','0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',20000,0),
 'USDT':('0x390f3595bca2df7d23783dfd126427cceb997bf4','0xdac17f958d2ee523a2206206994597c13d831ec7',20000,24368282421423834800052533),
 'PYUSD':('0x625e92624bc2d88619accc1788365a69767f6200','0x6c3ea9036406852006290770bedfcaba0e23a0e8',50000,0),
 'FRXUSD':('0x13e12bb0e6a2f1a3d6901a59a9d585e89a6243e1','0xcacd6fd266af91b8aed52accc382b4e165586e29',50000,0)}
CACHED={(REG,'fee_receiver',()):int(FEE,16)}
for label,pk in c.P.items():
 pool,coin,share,debt=DATA[label]
 for k,v in [('pool',int(pool,16)),('regulator',int(REG,16)),('share',share),('debt',debt),('estimate',0)]:CACHED[(pk,k,())]=v
 CACHED[(pool,'coins',(0,))]=int(coin,16);CACHED[(pool,'coins',(1,))]=int(CRV,16)
OLDVAL=c.Client.val;OLDVIEW=c.Client.view;HITS=[];PAGES=[]
def view(self,to,key,block,args=()):
 k=(to,key,tuple(args))
 if block==END and k in CACHED:
  HITS.append({'to':to,'function':key,'args':args,'block':block,'value':CACHED[k]});c.base.save('HISTORICAL_CACHE_USED.json',{'origin_run':39014404062,'origin_artifact_sha256':ORIGIN,'reads':HITS})
  return CACHED[k]
 return OLDVIEW(self,to,key,block,args)
def first(self,t,hi):
 if t==c.base.START:n,h=0x18d111a,'0xb0ee53cd72bc3a97a492775816066b98082e90a9ee7c52791685cacf346413b3'
 elif t==c.base.END:n,h=END+1,'0x84942a535592885757c69030ba601c76c6f21392b8d2ddd898dbcb7ebf585bb3'
 else:raise ValueError('unfrozen timestamp')
 a=self.head(n);b=self.head(n-1)
 if a['hash']!=h or int(a['timestamp'],16)<t or int(b['timestamp'],16)>=t:raise ValueError('historical range mismatch')
 return n
def val(self,name,method,params):
 if method!='eth_getLogs':return OLDVAL(self,name,method,params)
 q=params[0]
 if not q.get('address'):raise ValueError('empty address list rejected')
 a=int(q['fromBlock'],16);b=int(q['toBlock'],16);rows=[]
 for lo in range(a,b+1,10000):
  hi=min(lo+9999,b);p=copy.deepcopy(q);p.update(fromBlock=hex(lo),toBlock=hex(hi));PAGES.append({'name':name,'from':lo,'to':hi});c.base.save('PAGES.json',PAGES)
  rows+=OLDVAL(self,name+'_'+str(lo),method,[p])
 if len({(x['transactionHash'],x['logIndex']) for x in rows})!=len(rows):raise ValueError('duplicate paginated logs')
 return rows
if __name__=='__main__':
 c.Client.view=view;c.Client.first=first;c.Client.val=val;c.main()
