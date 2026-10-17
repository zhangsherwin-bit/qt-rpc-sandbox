import unittest
import reward_census as r

def enc(*v):return '0x'+''.join(f'{x:064x}' for x in v)
def log(topic,data,extra):return {'topics':[topic]+[enc(x) for x in extra],'data':data,'blockNumber':'0x1','blockHash':'0x'+'11'*32,'transactionHash':'0x'+'22'*32,'logIndex':'0x0'}
class Tests(unittest.TestCase):
 def test_prize_is_not_reward(self):
  x=r.decode(log(r.TOPICS['claims'],enc(9,2,1,1000000,700,4),[1,2,3]))
  self.assertEqual(x['reward'],700);self.assertEqual(x['winner_payout'],1000000)
 def test_withdraw_is_distinct(self):
  x=r.decode(log(r.TOPICS['withdrawals'],enc(8,10),[1,2]));self.assertEqual(x['amount'],8);self.assertNotIn('reward',x)
 def test_claim_shape_rejected(self):
  with self.assertRaises(ValueError):r.decode(log(r.TOPICS['claims'],enc(1,2),[1,2,3]))
 def test_address_overflow(self):
  with self.assertRaises(ValueError):r.addr(2**160)
 def test_uint_shape(self):
  with self.assertRaises(ValueError):r.uint('0x')
 def test_no_send_method(self):
  self.assertNotIn('eth_sendRawTransaction',r.ALLOWED);self.assertNotIn('eth_sendTransaction',r.ALLOWED)
 def test_nonreserved_three_day_window(self):
  self.assertEqual(r.END-r.START,3*86400);self.assertEqual(r.dt.datetime.fromtimestamp(r.START,r.dt.timezone.utc).month,9)
