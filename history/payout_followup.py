"""Fair terminal-asset follow-up: the same historical liquidation and producer bid,
but unwrap the entire surplus and actually pay remaining ETH to the simulated caller.
This is not a trade; no native balance is endowed. Original raw prefix calls, exact
status/log/gas comparisons and explicit synthetic gasPrice=0 convention are retained.
"""
import pathlib,json,hashlib
import bid_followup as previous

HERE=pathlib.Path(__file__).resolve().parent
OLD='''  if(producerPayment>0) { CashToken(W).withdraw(producerPayment); (bool ok,)=block.coinbase.call{value:producerPayment}("");require(ok,"PRODUCER_PAYMENT"); }
  cashAfterBid=CashToken(W).balanceOf(address(this));nativeRemaining=address(this).balance;
  require(cashAfterBid==gross-producerPayment && nativeRemaining==0,"FINAL_CASH_VECTOR");internalGas=g-gasleft();'''
NEW='''  uint256 recipientBefore=msg.sender.balance;
  CashToken(W).withdraw(gross);
  if(producerPayment>0) { (bool ok,)=block.coinbase.call{value:producerPayment}("");require(ok,"PRODUCER_PAYMENT"); }
  uint256 payout=address(this).balance;
  (bool paid,)=payable(msg.sender).call{value:payout}("");require(paid,"PROFIT_PAYOUT");
  cashAfterBid=msg.sender.balance-recipientBefore;nativeRemaining=address(this).balance;
  require(cashAfterBid==gross-producerPayment && nativeRemaining==0 && CashToken(W).balanceOf(address(this))==0,"FINAL_CASH_VECTOR");internalGas=g-gasleft();'''

def main():
 root=HERE/'payout_run';root.mkdir(exist_ok=True)
 source=(HERE/'BidCashProbe.sol').read_text()
 if source.count(OLD)!=1:raise ValueError('Exact reviewed source block not found once')
 updated=source.replace(OLD,NEW)
 (root/'BidCashProbe.sol').write_text(updated)
 manifest={'basis':'same-bid historical contract changed only to complete profit payout as ETH','parent_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'payout_source_sha256':hashlib.sha256(updated.encode()).hexdigest(),'no_balance_or_protocol_storage_override':True}
 (root/'PAYOUT_CHANGE.json').write_text(json.dumps(manifest,indent=2))
 previous.ROOT=root
 previous.main()
 paths=sorted(root.glob('bid_*/SUMMARY.json'))
 if not paths:raise ValueError('No follow-up summary')
 path=paths[-1];s=json.loads(path.read_text())
 s['comparison']='complete ETH profit payout, not WETH retained in the executor'
 s['source_change']=manifest
 if 'cash_after_bid_weth_wei' in s:
  s['cash_delivered_eth_wei']=s.pop('cash_after_bid_weth_wei')
  s['terminal_weth_wei']='0'  # The successful source require checks this exactly.
 path.write_text(json.dumps(s,indent=2))
 print('PAYOUT_SUMMARY',json.dumps({k:v for k,v in s.items() if k not in ('response','canonical_prefix','original_receipt')},indent=2))

if __name__=='__main__':main()
