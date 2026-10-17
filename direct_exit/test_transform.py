import ast
from pathlib import Path
import unittest
code=(Path(__file__).resolve().parent/'run.py').read_text();tree=ast.parse(code)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='modify');ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'transform','exec'),ns)
SOURCE="""address constant STABLE=address(bytes20(hex'13e12bb0e6a2f1a3d6901a59a9d585e89a6243e1'));
IStableC(STABLE).coins(0)==FRX&&IStableC(STABLE).coins(1)==CRVUSD
uint256 c=bal(CRVUSD);approve(CRVUSD,STABLE,c);IStableC(STABLE).exchange(1,0,c,1);
  frxBought=bal(FRX);approve(FRX,USTB,frxBought);IRedeemC(USTB).redeem(frxBought,address(this),address(this));
require(bal(USDC)>=amount,'not profitable');
"""
class TestTransform(unittest.TestCase):
 def test_direct_exit(self):
  x=ns['modify'](SOURCE);self.assertIn('IStableC(DIRECT).exchange(1,0,c,1)',x);self.assertNotIn('IRedeemC(USTB).redeem(',x)
 def test_coin_order(self):
  x=ns['modify'](SOURCE);self.assertIn('IStableC(DIRECT).coins(0)==USDC&&IStableC(DIRECT).coins(1)==CRVUSD',x)
 def test_preserves_repayment_check(self):
  self.assertIn("require(bal(USDC)>=amount,'not profitable');",ns['modify'](SOURCE))
 def test_rejects_unexpected_source(self):
  with self.assertRaises(AssertionError):ns['modify']('different version')
 def test_transform_is_not_repeatable(self):
  with self.assertRaises(AssertionError):ns['modify'](ns['modify'](SOURCE))
if __name__=='__main__':unittest.main()
