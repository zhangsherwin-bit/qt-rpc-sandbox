"""Research-only alternative exit and larger sizes; does not rescue frozen failures.
Run serially after the initial size/date job to preserve one paced RPC workload.
"""
from pathlib import Path
import hashlib,importlib.util,json,traceback,urllib.request
HELPER='https://raw.githubusercontent.com/zhangsherwin-bit/qt-rpc-sandbox/706141161bb58263c57d12aa3b85234aebee58f8/frx_extension/run.py'
DIRECT='0x4dece678ceceb27446b35c672dc7d61f30bad69e'
OUT=Path('evidence');OUT.mkdir(exist_ok=True)
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'QT-Pinned-Research-Source/1'}),timeout=30) as r:b=r.read(80000)
 if len(b)>=80000:raise ValueError('source body cap')
 return b
body=get(HELPER);(OUT/'helper.py').write_bytes(body)
spec=importlib.util.spec_from_file_location('frozen',OUT/'helper.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def modify(src):
 old="address constant STABLE=address(bytes20(hex'13e12bb0e6a2f1a3d6901a59a9d585e89a6243e1'));"
 new=old+"\n address constant DIRECT=address(bytes20(hex'4dece678ceceb27446b35c672dc7d61f30bad69e'));"
 assert src.count(old)==1;src=src.replace(old,new)
 old="IStableC(STABLE).coins(0)==FRX&&IStableC(STABLE).coins(1)==CRVUSD"
 new="IStableC(DIRECT).coins(0)==USDC&&IStableC(DIRECT).coins(1)==CRVUSD"
 assert src.count(old)==1;src=src.replace(old,new)
 old="uint256 c=bal(CRVUSD);approve(CRVUSD,STABLE,c);IStableC(STABLE).exchange(1,0,c,1);\n  frxBought=bal(FRX);approve(FRX,USTB,frxBought);IRedeemC(USTB).redeem(frxBought,address(this),address(this));"
 new="uint256 c=bal(CRVUSD);approve(CRVUSD,DIRECT,c);IStableC(DIRECT).exchange(1,0,c,1);\n  frxBought=0;"
 assert src.count(old)==1;return src.replace(old,new)

def compile_alt():
 import solcx
 b=(OUT/'ConversionProbe.sol').read_bytes();assert hashlib.sha256(b).hexdigest()==m.SOURCE_SHA
 src=modify(b.decode());(OUT/'AlternativeExit.sol').write_text(src)
 inp={'language':'Solidity','sources':{'C.sol':{'content':src}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.methodIdentifiers','evm.deployedBytecode.object']}}}}
 ob=solcx.compile_standard(inp,solc_version='0.8.34');m.save('alternative_compiler_input.json',inp);m.save('alternative_compiler_output.json',ob)
 c=ob['contracts']['C.sol']['ConversionProbe'];assert c['evm']['methodIdentifiers']['execute(uint256,uint256,uint256)']=='2d29a47b';runtime='0x'+c['evm']['deployedBytecode']['object'];(OUT/'alternative_runtime.hex').write_text(runtime)
 return runtime

def main():
 jobs=[('original',1,100000),('original',1,250000),('direct_crvusd_exit',1,20000),('direct_crvusd_exit',2,20000),('direct_crvusd_exit',1,100000)]
 plan={'scope':'development extension; larger sizes and a new direct crvUSD/USDC exit; ONE known event; no independent recurrence claim','jobs':jobs,'direct_pool':DIRECT,'direct_pool_reference':'curvefi/curve-stablecoin scripts/deploy/llamalend/ethereum/markets/syrupUSDC-crvUSD/deploy.py at c84e21d45503be68d46a769c03ed86e71726abf5','helper_source':HELPER,'helper_sha256':hashlib.sha256(body).hexdigest(),'public_read_only':True,'source_mutations':'only coin-order guard and replace crvUSD->frxUSD->USDC by crvUSD->USDC','amounts_not_added_across_alternatives':True,'no_storage_or_balance_overrides':True}
 m.save('PLAN.json',plan);out={'plan':plan,'started_utc':m.utc(),'cases':[],'transactions_sent':0}
 try:
  original=m.build();alternative=compile_alt();out['alternative_runtime_sha256']=hashlib.sha256(bytes.fromhex(alternative[2:])).hexdigest();assert m.val('chain','eth_chainId',[])=='0x1';seed=m.SEEDS[0]
  h=m.val('anchor','eth_getBlockByNumber',[hex(seed['block']),False]);assert h['hash']==seed['hash'];headers={seed['block']:h}
  for who,address in [('probe',m.PROBE),('caller',m.CALLER)]:assert m.val(who+'_code','eth_getCode',[address,h['number']])=='0x'
  for route,offset,usd in jobs:
   try:c=m.simulate(seed,offset,usd,original if route=='original' else alternative,headers)
   except Exception as e:c={'offset_blocks':offset,'principal_USDC':usd,'unavailable':True,'exception':repr(e),'traceback':traceback.format_exc()}
   c['route']=route;out['cases'].append(c);m.save('SUMMARY.json',out);print(json.dumps({k:v for k,v in c.items() if k not in ('response','parent','target','traceback')},indent=2),flush=True)
   if m.STOP:break
 except Exception as e:out.update(exception=repr(e),traceback=traceback.format_exc())
 out.update(completed_utc=m.utc(),rpc_requests=m.COUNT);m.save('SUMMARY.json',out)
 print(json.dumps({'case_count':len(out['cases']),'exception':out.get('exception'),'rpc_requests':m.COUNT}),flush=True)
if __name__=='__main__':main()
