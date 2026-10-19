import unittest
from gearbox_expiry import scan as S
class TestReadonlyExpiry(unittest.TestCase):
    def test_frozen_noncontiguous_calendar(self):
        self.assertEqual(len(S.WINDOWS),3)
        self.assertEqual(len(set(a.lower() for a in S.FACADES)),9)
        self.assertTrue(all(x["end"]-x["start"]==2199 for x in S.WINDOWS))
        self.assertLess(S.WINDOWS[0]["end"],S.ANCHOR)
    def test_event_topic_is_keccak256(self):
        self.assertEqual(len(S.EVENT),66)
        self.assertEqual(S.EVENT,S.h("LiquidateCreditAccount(address,address,address,uint256)"))
    def test_no_trade_apis(self):
        import inspect
        s=inspect.getsource(S)
        for bad in ("eth_sendRaw"+"Transaction","eth_send"+"Transaction","wallet_private_key"):
            self.assertNotIn(bad,s)
    def test_no_dollar_conflation(self):
        self.assertEqual(S.GETTERS["version"],S.h("version()",8))
        self.assertNotEqual(S.GETTERS["version"],S.GETTERS["expirable"])
if __name__=="__main__":unittest.main()
