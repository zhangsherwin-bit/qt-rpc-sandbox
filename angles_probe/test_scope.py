import unittest,pathlib
from eth_abi import encode,decode
from Crypto.Hash import keccak
class TestScope(unittest.TestCase):
 def test_21_day_window(self):
  from angles.census import START,END
  self.assertEqual(END-START,21*86400)
 def test_read_only(self):
  from angles.census import ALLOWED
  self.assertFalse(any('send' in x.lower() or 'sign' in x.lower() for x in ALLOWED))
 def test_stable_and_native_payout_guards(self):
  s=pathlib.Path('angles_probe/CashProbe.sol').read_text()
  self.assertIn('t==USDC||t==USDT',s);self.assertIn('BENEFICIARY.call{value:n}',s)
 def test_measurement_reverts_whole_branch(self):
  s=pathlib.Path('angles_probe/CashProbe.sol').read_text()
  self.assertIn('revert Measurement(t,n)',s);self.assertIn('require(!ok,"missing reset")',s)
 def test_distinct_auction_instances(self):
  self.assertIn('auctionA!=auctionB',pathlib.Path('angles_probe/CashProbe.sol').read_text())
 def test_flash_callback_authenticated(self):
  self.assertIn('msg.sender==MORPHO&&assets==principal',pathlib.Path('angles_probe/CashProbe.sol').read_text())
 def test_self_only_measurement(self):
  self.assertIn('require(msg.sender==address(this),"measure self")',pathlib.Path('angles_probe/CashProbe.sol').read_text())
 def test_job_encoding(self):
  typ='(uint256,address,uint256[],uint256,uint256,bytes)'
  j=(2,'0x'+'11'*20,[1,2],0,0,b'')
  self.assertEqual(decode([typ],encode([typ],[j]))[0],(2,j[1],(1,2),0,0,b''))
 def test_zero_address_is_not_income(self):
  def income(to,fee):return to!='0x'+'00'*20 and to!=fee
  self.assertFalse(income('0x'+'00'*20,'0x'+'22'*20))
 def test_no_privileged_calls(self):
  s=pathlib.Path('angles_probe/CashProbe.sol').read_text()
  for bad in ['setPrice(', 'setGovernance(', 'withdraw_profit(', 'setIsAuthorized(']:self.assertNotIn(bad,s)
if __name__=='__main__':unittest.main()
