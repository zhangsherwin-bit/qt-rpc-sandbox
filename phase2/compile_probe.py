"""Compile research probe; failures are preserved, never counted as successful simulations."""
import json,pathlib,hashlib
from codec import MARKET,OFFER,selector
ROOT=pathlib.Path(__file__).resolve().parent

def compile_probe():
 root=ROOT/'build';root.mkdir(exist_ok=True);(root/'probe_runtime.hex').unlink(missing_ok=True)
 source=(ROOT/'CashProbe.sol').read_text();status={'compiler':'0.8.34','compiled':False,'source_hash':hashlib.sha256(source.encode()).hexdigest()}
 try:
  import solcx
  if '0.8.34' not in {str(v) for v in solcx.get_installed_solc_versions()}:solcx.install_solc('0.8.34')
  standard={'language':'Solidity','sources':{'CashProbe.sol':{'content':source}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.deployedBytecode.object','evm.methodIdentifiers']}}}}
  (root/'compiler_input.json').write_text(json.dumps(standard,indent=2))
  compiled=solcx.compile_standard(standard,solc_version='0.8.34');(root/'compiler_output.json').write_text(json.dumps(compiled))
  a=compiled['contracts']['CashProbe.sol']['CashProbe']
  for sig in ['runTake('+OFFER+',bytes,uint256)','runCashLiquidation('+MARKET+',uint256,address,uint256,uint256,bool)']:
   if a['evm']['methodIdentifiers'][sig]!=selector(sig)[2:]:raise ValueError('compiler/codec selector mismatch')
  runtime=a['evm']['deployedBytecode']['object'];(root/'probe_runtime.hex').write_text('0x'+runtime)
  status.update(compiled=True,bytes=len(runtime)//2,runtime_sha256=hashlib.sha256(bytes.fromhex(runtime)).hexdigest())
 except Exception as e:status['error']=repr(e)
 (root/'compile_status.json').write_text(json.dumps(status,indent=2));print(json.dumps(status,indent=2));return status
if __name__=='__main__':compile_probe()
