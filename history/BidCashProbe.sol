// SPDX-License-Identifier: MIT
pragma solidity 0.8.34;
interface CashToken { function balanceOf(address) external view returns(uint256); function approve(address,uint256) external returns(bool); function withdraw(uint256) external; }
interface CashPool { function liquidationCall(address,address,address,uint256,bool) external; function getUserAccountData(address) external view returns(uint256,uint256,uint256,uint256,uint256,uint256); }
// Research-only simulation of a complete same-asset liquidation including producer payment.
contract BidCashProbe {
 address constant W=address(bytes20(hex"c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"));
 address constant P=address(bytes20(hex"87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"));
 address constant CALLER=address(0xa71502);
 function environment() external view returns(uint256,uint256,uint256,uint256) { return(block.chainid,block.number,block.timestamp,address(this).balance); }
 function execute(address borrower,uint256 repay,uint256 producerPayment) external returns(uint256 gross,uint256 cashAfterBid,uint256 internalGas,uint256 nativeRemaining) {
  uint256 g=gasleft();require(msg.sender==CALLER && block.chainid==1,"RESEARCH_DOMAIN");
  require(address(this).balance==0 && CashToken(W).balanceOf(address(this))==0,"NO_PRINCIPAL");
  (,uint256 d0,,,,)=CashPool(P).getUserAccountData(address(this));require(d0==0,"INITIAL_DEBT");
  require(CashToken(W).approve(P,type(uint256).max),"APPROVE");
  CashPool(P).liquidationCall(W,W,borrower,repay,false);
  gross=CashToken(W).balanceOf(address(this));require(gross>producerPayment,"BID_NOT_COVERED");
  require(CashToken(W).approve(P,0),"RESET");
  (,uint256 d1,,,,)=CashPool(P).getUserAccountData(address(this));require(d1==0,"FINAL_DEBT");
  if(producerPayment>0) { CashToken(W).withdraw(producerPayment); (bool ok,)=block.coinbase.call{value:producerPayment}("");require(ok,"PRODUCER_PAYMENT"); }
  cashAfterBid=CashToken(W).balanceOf(address(this));nativeRemaining=address(this).balance;
  require(cashAfterBid==gross-producerPayment && nativeRemaining==0,"FINAL_CASH_VECTOR");internalGas=g-gasleft();
 }
 receive() external payable { require(msg.sender==W,"ONLY_WETH_UNWRAP"); }
}
