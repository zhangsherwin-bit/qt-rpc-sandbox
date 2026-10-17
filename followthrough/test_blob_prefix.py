import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import prefix_finish as P

class TestBlobPrefix(unittest.TestCase):
 def test_blob_hashes_preserved(self):
  t={'from':'0x'+'11'*20,'to':'0x'+'22'*20,'input':'0x1234','gas':'0x61a80','value':'0x0','maxFeePerGas':'0x10','maxPriorityFeePerGas':'0x1','maxFeePerBlobGas':'0x20','blobVersionedHashes':['0x01'+'33'*31]}
  c=P.ascall_with_blobs(t)
  self.assertEqual(c['blobVersionedHashes'],t['blobVersionedHashes']);self.assertEqual(c['maxFeePerBlobGas'],'0x20')
  self.assertEqual(c['maxFeePerGas'],'0x10');self.assertNotIn('gasPrice',c)
 def test_non_blob_unchanged(self):
  t={'from':'0x'+'11'*20,'to':'0x'+'22'*20,'input':'0x','gas':'0x5208','gasPrice':'0x1'}
  self.assertEqual(P.ascall_with_blobs(t),P.OLD_ASCALL(t))
 def test_extended_view_decode(self):
  b=P.D.encode(['uint256']*7,list(range(7)))
  self.assertEqual(P.D.decode(['uint256']*6,b),tuple(range(6)))
 def test_canonical_blob_example_has_multiple_hashes(self):
  import json
  p=pathlib.Path('input_services/raw/0003.body');h=json.loads(p.read_text())['result'];tx=h['transactions'][36]
  self.assertEqual(tx['type'],'0x3');self.assertEqual(len(P.ascall_with_blobs(tx)['blobVersionedHashes']),3)
if __name__=='__main__':unittest.main()
