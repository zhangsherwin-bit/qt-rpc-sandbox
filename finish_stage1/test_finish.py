import unittest
from unittest.mock import patch
from pathlib import Path
import finish as F
class Checks(unittest.TestCase):
 def test_official_chainlog(self):self.assertEqual(F.CHAINLOG,'0xda0ab1e0017debcd72be8599041a2aa3ba7e740f')
 def test_empty_call_is_not_address(self):
  for x in ('0x','0x0x','',None,'0x'+('ff'*32)):
   with self.assertRaises(ValueError):F.strict_addr(x)
 def test_strict_address_success(self):self.assertEqual(F.strict_addr('0x'+'0'*24+F.CHAINLOG[2:]),F.CHAINLOG)
 def test_no_empty_log_query(self):
  for x in ([],['0x0x'],['0x'+'0'*40]):
   with self.assertRaises(ValueError):F.validate_addresses(x)
 def test_known_orders(self):
  self.assertEqual(len(F.ORDERS),2)
  for x in F.ORDERS:self.assertEqual(len(x['hash']),66);self.assertEqual(len(x['tx']),66)
 def test_unique_nonces(self):self.assertEqual(len({x['nonce'] for x in F.ORDERS}),2)
 def test_nonce_partition(self):
  for x in F.ORDERS:
   n=int(x['nonce']);self.assertEqual(((n>>8)<<8)+(n&255),n)
 def test_invalid_logs_fail_without_network(self):
  c=F.VerifiedClient()
  with patch('urllib.request.urlopen') as net:
   with self.assertRaises(ValueError):c.logs('bad',['0x0x'],[],1,2)
   net.assert_not_called()
 def test_readonly(self):
  s=(Path(__file__).parent/'finish.py').read_text()
  for bad in ('eth_send'+'Transaction','eth_send'+'RawTransaction','state'+'Overrides','private_'+'key'):
   self.assertNotIn(bad,s)
 def test_frozen_window(self):self.assertEqual([F.R.A,F.R.B],[25943261,26093737])
if __name__=='__main__':unittest.main()
