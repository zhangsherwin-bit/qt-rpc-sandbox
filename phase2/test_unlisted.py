import unittest
from eth_abi import encode
import explore_unlisted as e
class MulticallCompatibility(unittest.TestCase):
 def test_encoding_against_library(self):
  items=[(e.USDC,e.selector('decimals()')),(e.CORE,e.view_data('marketState(bytes32)','0x'+'12'*32))]
  expected=e.selector('aggregate3((address,bool,bytes)[])')+encode(['(address,bool,bytes)[]'],[[(a,True,bytes.fromhex(b[2:])) for a,b in items]]).hex()
  self.assertEqual(e.aggregate_data(items),expected)
 def test_decoding_against_library(self):
  raw='0x'+encode(['(bool,bytes)[]'],[[(True,(6).to_bytes(32,'big')),(False,b'')]]).hex()
  self.assertEqual(e.aggregate_decode(raw,2),[{'ok':True,'data':'0x'+(6).to_bytes(32,'big').hex()},{'ok':False,'data':'0x'}])
 def test_reject_count_mismatch(self):
  raw='0x'+encode(['(bool,bytes)[]'],[[(True,b'')]]).hex()
  with self.assertRaises(ValueError):e.aggregate_decode(raw,2)
 def test_string_metadata(self):
  self.assertEqual(e.textresult({'ok':True,'data':'0x'+encode(['string'],['sample']).hex()}),'sample')
if __name__=='__main__':unittest.main()
