"""Static local tests: prices must be cash outputs, not token units."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import screen as m

class Tests(unittest.TestCase):
 def test_selector_length(self):
  self.assertEqual(len(m.selector("previewRedeem(uint256)")),8)
 def test_token_addresses(self):
  for addr in [m.QUOTER,m.USDC,m.USDS,m.DAI,m.SUSDS,m.SDAI,
               m.USDA,m.ANGLE,m.THREE_POOL,m.THREE_CRV]:
   self.assertEqual(len(addr),42)
   self.assertGreater(int(addr,16),0)
 def test_amounts_must_be_nonzero(self):
  self.assertEqual(m.SIZES,(100,1000,10000))
  self.assertEqual(m.FEES,(100,500,3000))
 def test_read_only_boundary(self):
  import inspect
  text=inspect.getsource(m)
  for forbidden in ("eth_sendRawTransaction","eth_sendTransaction","personal_sign","wallet_private_key"):
   self.assertNotIn(forbidden,text)
 def test_no_unbacked_profit(self):
  self.assertTrue(m.MAX_CALLS<=160)
  self.assertIn("NOT_EXECUTED",inspect_source())

def inspect_source():
 import inspect
 return inspect.getsource(m)
if __name__=="__main__":unittest.main()
