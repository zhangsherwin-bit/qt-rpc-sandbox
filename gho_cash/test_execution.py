import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import execute as E
class GhoCashResearchTests(unittest.TestCase):
 def test_instant_no_initial_principal(self):
  s=Path('gho_cash/GhoCashProbe.sol').read_text()
  self.assertIn('IERC20(USDC).balanceOf(address(this))==0',s)
  self.assertIn('IMorpho(MORPHO).flashLoan',s)
  self.assertIn('ONCHAIN',Path('gho_cash/execute.py').read_text())
 def test_exact_assets_and_repayment(self):
  s=Path('gho_cash/GhoCashProbe.sol').read_text()
  self.assertIn('spent==assets',s)
  self.assertIn('IERC20(USDC).approve(MORPHO,assets)',s)
  self.assertIn('IERC20(USDC).balanceOf(address(this))>assets',s)
 def test_simulated_evm_only(self):
  s=Path('gho_cash/execute.py').read_text()
  for forbidden in ('eth_sendRawTransaction','eth_sendTransaction','private_key','wallet_seed','stateDiff','balance":'):
   self.assertNotIn(forbidden,s)
  self.assertIn("stateOverrides':{PROBE:{'code':code}}",s)
 def test_historical_source_date_pinned(self):
  self.assertEqual([x['block'] for x in E.STATES],[26090422,26220131])
  self.assertEqual([x['trials'] for x in E.STATES],[[(100,100),(1000,100)],[(100,500),(1000,500)]])
 def test_calldata(self):
  self.assertEqual(len(E.khash('run(uint256,uint24)')),10)
  self.assertEqual(len(E.word(1)),64)
  self.assertEqual(E.decode_words('0x'+E.word(50)+E.word(60),2),[50,60])
 def test_wrong_env_rejected(self):
  ev=[1,26090422,1234,100,0,0,0,0,0,0]
  cs=[{'status':'0x1','returnData':'0x'+''.join(E.word(x) for x in ev)},
      {'status':'0x0','gasUsed':'0x0'},{'status':'0x1','returnData':'0x'+''.join(E.word(x) for x in ev)}]
  with self.assertRaises(ValueError):E.audit_sim([{'calls':cs}],{'number':hex(26090422),'timestamp':hex(1240),'baseFeePerGas':hex(100)},100*10**6,100)
 def test_residual_tokens_not_profit(self):
  e=[1,26090422,1234,100,0,0,0,0,0,0];z=e[:];z[4]=1
  cs=[{'status':'0x1','returnData':'0x'+''.join(E.word(x) for x in e)},
     {'status':'0x1','gasUsed':'0x100','returnData':'0x'+E.word(10)},
     {'status':'0x1','returnData':'0x'+''.join(E.word(x) for x in z)}]
  with self.assertRaises(ValueError):E.audit_sim([{'calls':cs}],{'number':hex(26090422),'timestamp':hex(1234),'baseFeePerGas':hex(100)},100*10**6,100)
if __name__=='__main__':unittest.main()
