import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import qt_probe

class TestReadOnly(unittest.TestCase):
    def test_allowlist(self):
        self.assertTrue(qt_probe.is_safe_call(qt_probe.API+'/v0/midnight/markets',None))
        self.assertFalse(qt_probe.is_safe_call('http://api.morpho.org/v0/midnight/markets',None))
        self.assertFalse(qt_probe.is_safe_call('https://arbitrary.site/get',None))
        self.assertFalse(qt_probe.is_safe_call(qt_probe.API+'/private',None))
        self.assertFalse(qt_probe.is_safe_call(qt_probe.RPC,{'jsonrpc':'2.0','method':'eth_sendRawTransaction'}))
        self.assertTrue(qt_probe.is_safe_call(qt_probe.RPC,{'jsonrpc':'2.0','method':'eth_call'}))

    def test_hex_data_lengths(self):
        x='0x'+qt_probe.SEL_WITHDRAWABLE+qt_probe.MARKETS[0][2:]
        y='0x'+qt_probe.SEL_BALANCEOF+qt_probe.CORE[2:].lower().rjust(64,'0')
        self.assertEqual(len(x),74)
        self.assertEqual(len(y),74)

    def test_rpc_error_does_not_become_a_zero_balance(self):
        class FakeResponse:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,_n):return json.dumps({'jsonrpc':'2.0','id':1,'error':{'code':-32001,'message':'historical state unavailable'}}).encode()
        with tempfile.TemporaryDirectory() as tmp:
            c=qt_probe.Client(Path(tmp))
            with patch('urllib.request.urlopen',return_value=FakeResponse()),patch('time.sleep',return_value=None):
                self.assertIsNone(c.rpc('rpc-error','eth_call',[{},'latest']))
            self.assertEqual(c.records[0]['status'],'RPC_ERROR')

    def test_api_failure_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=qt_probe.Client(Path(tmp))
            with patch('urllib.request.urlopen',side_effect=OSError('local sandbox no network')),patch('time.sleep',return_value=None):
                self.assertIsNone(c.get('test','/v0/midnight/markets'))
            self.assertEqual(c.records[0]['status'],'UNAVAILABLE')
            self.assertTrue(list(Path(tmp).glob('*.meta.json')))

if __name__=='__main__':unittest.main()
