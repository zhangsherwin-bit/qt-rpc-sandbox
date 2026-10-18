import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scan as S

class TestSky(unittest.TestCase):
 def test_decode_address(self):
  a="0x"+"12"*20
  self.assertEqual(S.abiaddr("0x"+"0"*24+a[2:]),a)
 def test_refuse_ambiguous(self):
  for bad in ("0x0x","0x",None,"0x"+"1"*64):
   with self.assertRaises(ValueError):S.abiaddr(bad)
 def test_radar(self):
  self.assertEqual(S.karg("MCD_DOG"),"MCD_DOG".encode().hex().ljust(64,"0"))
 def test_frozen_boundaries(self):
  self.assertEqual((S.START,S.END),(25943261,26093737))
 def test_bounded_scan(self):
  pairs=[(i,min(i+9999,S.END)) for i in range(S.START,S.END+1,10000)]
  self.assertEqual(sum(hi-lo+1 for lo,hi in pairs),S.END-S.START+1)
  self.assertLessEqual(max(hi-lo+1 for lo,hi in pairs),10000)
 def test_event_topics(self):
  self.assertEqual(set(S.EVENTS),{"Bark","Kick","Redo"})
  self.assertTrue(all(len(v)==66 for v in S.EVENTS.values()))
 def test_prohibited_actions_not_used(self):
  src=(Path(__file__).parent/"scan.py").read_text()
  for bad in ("eth_sendRawTransaction","eth_sendTransaction","personal_sign","private_key"):
   self.assertNotIn(bad,src)
if __name__=="__main__":unittest.main()
