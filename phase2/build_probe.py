"""Compilation is successful only when compile_status.json says compiled=true."""
import json,pathlib,hashlib
from midnight_codec import MARKET,OFFER,selector
ROOT=pathlib.Path(__file__).resolve().parent

def main():
 out=ROOT/'build';out.mkdir(exist_ok=True);(out/'probe_runtime.hex').unlink(missing_ok=True)
 source=(ROOT/'CashProbe.sol').read_text();status={'compiler':'0.8.34','compiled':False,'source_hash':hashlib.sha256(source.encode()).hexdigest()}
 try:
  import solcx
  if '0.8.34' not in {str(v) for v in solcx.get_installed_solc_versions()}:solcx.install_solc('0.8.34')
  inp={'language':'Solidity','sources':{'CashProbe.sol':{'content':source}},'settings':{'optimizer':{'enabled':True,'runs':200},'viaIR':True,'evmVersion':'cancun','outputSelection':{'*':{'*':['abi','evm.deployedBytecode.object','evm.methodIdentifiers']}}}}
  (out/'compiler_input.json').write_text(json.dumps(inp,indent=2))
  result=solcx.compile_standard(inp,solc_version='0.8.34');(out/'compiler_output.json').write_text(json.dumps(result))
  a=result['contracts']['CashProbe.sol']['CashProbe']
  for sig in ['runTake('+OFFER+',bytes,uint256)','runCashLiquidation('+MARKET+',uint256,address,uint256,uint256,bool)']:
   if a['evm']['methodIdentifiers'][sig]!=selector(sig)[2:]:raise ValueError('selector mismatch')
  runtime=a['evm']['deployedBytecode']['object'];(out/'probe_runtime.hex').write_text('0x'+runtime)
  status.update(compiled=True,bytes=len(runtime)//2,runtime_sha256=hashlib.sha256(bytes.fromhex(runtime)).hexdigest())
 except Exception as e:status['error']=repr(e)
 (out/'compile_status.json').write_text(json.dumps(status,indent=2));print(json.dumps(status,indent=2))
if __name__=='__main__':main()
