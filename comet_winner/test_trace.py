import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import trace as R
class TestWinner(unittest.TestCase):
 def test_event_topics(self):self.assertNotEqual(R.ABS,R.BUY)
 def test_selected_amounts(self):
  self.assertEqual(R.BLOCK,25984761);self.assertEqual(len(R.TX),66)
 def test_transfer_balances(self):
  token=R.USDC;x='0x'+'a'*40;y='0x'+'b'*40
  r=[{'token':token,'from':x,'to':y,'value_raw':'100'}]
  self.assertEqual(R.balances(r,{x,y})[y][token],100)
  self.assertEqual(R.balances(r,{x,y})[x][token],-100)
 def test_native_coinbase_no_double_count(self):
  x='0x'+'f'*40
  t={'type':'CALL','to':x,'value':'0x4','calls':[{'type':'DELEGATECALL','to':x,'value':'0x4'}]}
  self.assertEqual(len(R.coinbase_transfers(t,x)),1)
 def test_no_send_calls(self):
  s=(Path(__file__).parent/'trace.py').read_text()
  for forbidden in ('eth_sendTransaction','eth_sendRawTransaction','private_key','wallet_seed'):
   self.assertNotIn(forbidden,s)
 def test_quote_not_cash(self):
  self.assertIn('hypothetical_quote_is_not_terminal_cash',(Path(__file__).parent/'trace.py').read_text())
if __name__=='__main__':unittest.main()
