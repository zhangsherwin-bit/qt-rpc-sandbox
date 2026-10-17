import json
from pathlib import Path
import re
import unittest
import run_study as s
class Tests(unittest.TestCase):
 def test_read_only(self):
  for name in ('eth_sendRawTransaction','eth_sendTransaction','personal_sign'):
   with self.assertRaises(ValueError):s.Client().val('x',name,[])
 def test_budget(self):
  c=s.Client();c.count=100
  with self.assertRaises(RuntimeError):c.val('x','eth_chainId',[])
 def test_provider_stop(self):
  c=s.Client();c.stop=True
  with self.assertRaises(RuntimeError):c.val('x','eth_chainId',[])
 def test_unsigned_encoder(self):
  with self.assertRaises(ValueError):s.encode('12345678',-1)
  with self.assertRaises(ValueError):s.encode('12345678',2**256)
 def test_word_shape(self):
  with self.assertRaises(ValueError):s.words('0x00',1)
  self.assertEqual(s.words('0x'+'0'*64,1),[0])
 def fake(self):
  h={'number':'0x100','timestamp':'0x200','baseFeePerGas':'0x300'};w=[1,256,512,768]
  for i in range(32):
   x=s.SIZES[i//4]*10**6;w.extend([x,100 if (i//2)%2==0 else 500,i%2,1,x-100,1,2,3])
  return h,'0x'+''.join(f'{x:064x}' for x in w)
 def test_negative_quotes_not_zero(self):
  h,r=self.fake();rows=s.decode_quotes(r,h)
  self.assertEqual(len(rows),32);self.assertTrue(all(x['gross_raw']==-100 for x in rows))
 def test_missing_quote_not_negative(self):
  h,r=self.fake();w=s.words(r,260);w[7]=0;r='0x'+''.join(f'{x:064x}' for x in w)
  self.assertIsNone(s.decode_quotes(r,h)[0]['gross_raw'])
 def test_wrong_context_rejected(self):
  h,r=self.fake();h['timestamp']='0x201'
  with self.assertRaises(ValueError):s.decode_quotes(r,h)
 def test_selection_no_duplicates_or_reserved_days(self):
  a=json.loads((s.BASE/'selected_states.json').read_text());self.assertEqual(len(a),21)
  self.assertEqual(len({x['block'] for x in a}),21)
  self.assertEqual(sum(x['role']=='systematic_development_sample' for x in a),18)
  self.assertTrue(all(x['block']<26000000 for x in a))
 def test_address_lengths_and_source_safety(self):
  for x in (s.QUOTE,s.CASH,s.CALLER,s.USDC,s.MORPHO):self.assertEqual(len(x),42)
  text=(s.BASE/'RouteStudy.sol').read_text()
  for x in re.findall(r"hex'([0-9a-f]+)'",text):
   if len(x)>2:self.assertEqual(len(x),40)
  self.assertIn('callback authentication',text);self.assertIn('Shortfall(x,bal(U))',text)
if __name__=='__main__':unittest.main()
