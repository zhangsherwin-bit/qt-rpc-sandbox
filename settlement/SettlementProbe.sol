// SPDX-License-Identifier: MIT
pragma solidity 0.8.34;
interface IToken {function balanceOf(address) external view returns(uint256);function approve(address,uint256) external returns(bool);function transfer(address,uint256) external returns(bool);}
interface IWrapped {function withdraw(uint256) external;}
interface ICashProbe {function execute(address,uint256,uint256,address,uint256) external returns(uint256,uint256,uint256,uint256,uint256,uint256,uint256);}
interface IV3Router {
 struct ExactOutputSingleParams {address tokenIn;address tokenOut;uint24 fee;address recipient;uint256 deadline;uint256 amountOut;uint256 amountInMaximum;uint160 sqrtPriceLimitX96;}
 function exactOutputSingle(ExactOutputSingleParams calldata) external payable returns(uint256);
}
contract SettlementProbe {
 address constant CASH=address(bytes20(hex'00000000000000000000000000000000dead7711'));
 address constant USDC=address(bytes20(hex'a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'));
 address constant WETH=address(bytes20(hex'c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'));
 address constant ROUTER=address(bytes20(hex'e592427a0aece92de3edee1f18e0157c05861564'));
 bool private active;
 receive() external payable {require(msg.sender==WETH && active,'native sender');}
 function environment() external view returns(uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256){
  return(block.chainid,block.number,block.timestamp,address(this).balance,IToken(USDC).balanceOf(address(this)),IToken(WETH).balanceOf(address(this)),msg.sender.balance,IToken(USDC).balanceOf(msg.sender),block.coinbase.balance);
 }
 function execute(address borrower,uint256 seized,address exit,uint24 poolFee,uint256 producerWei,uint256 gasReserveWei,uint256 minimumCash) external returns(uint256 grossCash,uint256 swapCost,uint256 paidCash,uint256 paidProducer,uint256 nativeReserve){
  require(!active && block.chainid==1 && address(this).balance==0,'environment');
  require(IToken(USDC).balanceOf(address(this))==0 && IToken(WETH).balanceOf(address(this))==0,'starting cash');active=true;
  ICashProbe(CASH).execute(borrower,seized,10000,exit,0);
  grossCash=IToken(USDC).balanceOf(address(this));uint256 nativeNeeded=producerWei+gasReserveWei;
  require(nativeNeeded>0 && grossCash>0,'no output');
  require(IToken(USDC).approve(ROUTER,0) && IToken(USDC).approve(ROUTER,grossCash),'approval');
  swapCost=IV3Router(ROUTER).exactOutputSingle(IV3Router.ExactOutputSingleParams(USDC,WETH,poolFee,address(this),block.timestamp,nativeNeeded,grossCash,0));
  require(IToken(WETH).balanceOf(address(this))==nativeNeeded,'wrapped output');IWrapped(WETH).withdraw(nativeNeeded);
  (bool ok,)=payable(block.coinbase).call{value:producerWei}(hex'');require(ok,'producer delivery');paidProducer=producerWei;
  (ok,)=payable(msg.sender).call{value:gasReserveWei}(hex'');require(ok,'reserve delivery');nativeReserve=gasReserveWei;
  paidCash=IToken(USDC).balanceOf(address(this));require(paidCash>=minimumCash,'minimum cash');
  require(IToken(USDC).transfer(msg.sender,paidCash),'cash payout');
  require(address(this).balance==0 && IToken(USDC).balanceOf(address(this))==0 && IToken(WETH).balanceOf(address(this))==0,'terminal residue');active=false;
 }
}
