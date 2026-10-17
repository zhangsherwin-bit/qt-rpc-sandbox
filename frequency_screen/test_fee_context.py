import unittest
from unittest.mock import patch
import run_fee_context as f

class FeeContextTests(unittest.TestCase):
    def setUp(self):
        f.HEADERS.clear();f.OBSERVATIONS.clear()
    def test_uses_canonical_gasprice_and_does_not_modify_input(self):
        h={'number':'0x64','timestamp':'0x3e8','baseFeePerGas':'0x2a'}
        f.HEADERS['0x64']=h
        p=[{'to':f.study.QUOTE,'data':'0x00'},'0x64',{f.study.QUOTE:{'code':'0x00'}}]
        raw='0x'+''.join(f'{i:064x}' for i in ([1,100,1000,42]+[0]*256))
        client=type('C',(),{'stop':False})()
        with patch.object(f,'ORIGINAL',return_value=raw) as call, patch.object(f.study,'save'):
            f.corrected_val(client,'q','eth_call',p)
        self.assertEqual(call.call_args.args[3][0]['gasPrice'],'0x2a')
        self.assertNotIn('gasPrice',p[0]);self.assertFalse(client.stop)
    def test_wrong_context_stops(self):
        f.HEADERS['0x64']={'number':'0x64','timestamp':'0x3e8','baseFeePerGas':'0x2a'}
        raw='0x'+''.join(f'{i:064x}' for i in ([1,100,1000,0]+[0]*256))
        c=type('C',(),{'stop':False})()
        with patch.object(f,'ORIGINAL',return_value=raw),patch.object(f.study,'save'):
            with self.assertRaises(ValueError):f.corrected_val(c,'q','eth_call',[{'to':f.study.QUOTE},'0x64',{}])
        self.assertTrue(c.stop)
    def test_missing_header_is_not_silently_defaulted(self):
        with self.assertRaises(ValueError):f.corrected_val(object(),'q','eth_call',[{'to':f.study.QUOTE},'0x64',{}])
