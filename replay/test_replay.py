import unittest
import run
class ReplayChecks(unittest.TestCase):
 def test_wrapper_selector(self):self.assertEqual(run.selector('claimLiquidation(address,address,uint256)').hex(),'d2c744ae')
 def test_curve_selector(self):self.assertEqual(run.selector('remove_liquidity_one_coin(uint256,int128,uint256)').hex(),'1a4d01d2')
 def test_read_only_scope(self):
  for method in ('eth_sendRawTransaction','eth_sendTransaction','personal_unlockAccount'):
   with self.assertRaises(ValueError):run.rpc('rejected',method,[])
 def test_anchors(self):
  self.assertEqual([x['index'] for x in run.SEEDS],[0,0,18]);self.assertEqual(len({x['tx'] for x in run.SEEDS}),3)
  self.assertTrue(all(x['block']<26000000 for x in run.SEEDS))
 def test_transaction_copy_preserves_access(self):
  tx={'from':'0x1','to':'0x2','value':'0x0','gas':'0x100','input':'0x1234','gasPrice':'0x4','accessList':[]}
  c=run.ascall(tx);self.assertEqual(c['accessList'],[]);self.assertEqual(c['input'],tx['input']);self.assertEqual(c['gasPrice'],'0x4')
 def test_log_normalization(self):
  self.assertEqual(run.normlogs([{'address':'0xAB','topics':['0xCD'],'data':'0xEF','blockNumber':'0x1'}]),[('0xab',['0xcd'],'0xef')])
if __name__=='__main__':unittest.main()
