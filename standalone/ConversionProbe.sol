// SPDX-License-Identifier: MIT
pragma solidity 0.8.34;
interface ITokenC {function balanceOf(address) external view returns(uint256);function approve(address,uint256) external returns(bool);function transfer(address,uint256) external returns(bool);}
interface IFlash {function flashLoan(address,uint256,bytes calldata) external;}
interface IWethC {function withdraw(uint256) external;}
interface IRedeemC {function redeem(uint256,address,address) external returns(uint256);}
interface ITriC {function coins(uint256) external view returns(address);function exchange(uint256,uint256,uint256,uint256,bool) external payable returns(uint256);}
interface IStableC {function coins(uint256) external view returns(address);function exchange(int128,int128,uint256,uint256) external returns(uint256);}
interface IRouterC {
 struct ExactInputSingleParams {address tokenIn;address tokenOut;uint24 fee;address recipient;uint256 deadline;uint256 amountIn;uint256 amountOutMinimum;uint160 sqrtPriceLimitX96;}
 struct ExactOutputSingleParams {address tokenIn;address tokenOut;uint24 fee;address recipient;uint256 deadline;uint256 amountOut;uint256 amountInMaximum;uint160 sqrtPriceLimitX96;}
 function exactInputSingle(ExactInputSingleParams calldata) external payable returns(uint256);
 function exactOutputSingle(ExactOutputSingleParams calldata) external payable returns(uint256);
}
contract ConversionProbe {
 address constant MORPHO=address(bytes20(hex'bbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb'));
 address constant USDC=address(bytes20(hex'a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'));
 address constant WETH=address(bytes20(hex'c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'));
 address constant FRX=address(bytes20(hex'cacd6fd266af91b8aed52accc382b4e165586e29'));
 address constant CRVUSD=address(bytes20(hex'f939e0a03fb07f59a73314e73794be0e57ac1b4e'));
 address constant USTB=address(bytes20(hex'00000000564ee6a571c5819057f27bb671e78bd5'));
 address constant TRI=address(bytes20(hex'4ebdf703948ddcea3b11f675b4d1fba9d2414a14'));
 address constant STABLE=address(bytes20(hex'13e12bb0e6a2f1a3d6901a59a9d585e89a6243e1'));
 address constant ROUTER=address(bytes20(hex'e592427a0aece92de3edee1f18e0157c05861564'));
 bool private active;bool private callbackDone;uint256 private amount;uint256 private frxBought;
 receive() external payable {require(active&&msg.sender==WETH,'native sender');}
 function bal(address t) internal view returns(uint256){return ITokenC(t).balanceOf(address(this));}
 function approve(address t,address spender,uint256 a) internal {require(ITokenC(t).approve(spender,0)&&ITokenC(t).approve(spender,a),'approve');}
 function environment() external view returns(uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256){return(block.chainid,block.number,block.timestamp,address(this).balance,bal(USDC),bal(WETH),bal(FRX),msg.sender.balance,ITokenC(USDC).balanceOf(msg.sender));}
 function execute(uint256 principal,uint256 gasReserveWei,uint256 minimumCash) external returns(uint256 loanRepaid,uint256 grossProfit,uint256 reserveCost,uint256 paidCash,uint256 paidReserve,uint256 redeemedFrx){
  require(!active&&block.chainid==1&&address(this).balance==0,'environment');require(bal(USDC)==0&&bal(WETH)==0&&bal(CRVUSD)==0&&bal(FRX)==0,'initial principal');
  require(ITriC(TRI).coins(0)==CRVUSD&&ITriC(TRI).coins(1)==WETH&&IStableC(STABLE).coins(0)==FRX&&IStableC(STABLE).coins(1)==CRVUSD,'route');
  active=true;callbackDone=false;amount=principal;frxBought=0;IFlash(MORPHO).flashLoan(USDC,principal,hex'01');require(callbackDone,'callback');loanRepaid=principal;grossProfit=bal(USDC);redeemedFrx=frxBought;
  approve(USDC,ROUTER,grossProfit);reserveCost=IRouterC(ROUTER).exactOutputSingle(IRouterC.ExactOutputSingleParams(USDC,WETH,500,address(this),block.timestamp,gasReserveWei,grossProfit,0));
  require(bal(WETH)==gasReserveWei,'reserve amount');IWethC(WETH).withdraw(gasReserveWei);(bool ok,)=payable(msg.sender).call{value:gasReserveWei}(hex'');require(ok,'reserve payout');paidReserve=gasReserveWei;
  paidCash=bal(USDC);require(paidCash>=minimumCash,'minimum profit');require(ITokenC(USDC).transfer(msg.sender,paidCash),'cash payout');
  require(address(this).balance==0&&bal(USDC)==0&&bal(WETH)==0&&bal(CRVUSD)==0&&bal(FRX)==0,'residue');active=false;
 }
 function onMorphoFlashLoan(uint256 assets,bytes calldata) external {
  require(msg.sender==MORPHO&&active&&!callbackDone&&assets==amount&&bal(USDC)==amount,'flash authentication');callbackDone=true;
  approve(USDC,ROUTER,amount);uint256 w=IRouterC(ROUTER).exactInputSingle(IRouterC.ExactInputSingleParams(USDC,WETH,500,address(this),block.timestamp,amount,1,0));IWethC(WETH).withdraw(w);
  ITriC(TRI).exchange{value:w}(1,0,w,1,true);uint256 c=bal(CRVUSD);approve(CRVUSD,STABLE,c);IStableC(STABLE).exchange(1,0,c,1);
  frxBought=bal(FRX);approve(FRX,USTB,frxBought);IRedeemC(USTB).redeem(frxBought,address(this),address(this));require(bal(USDC)>=amount,'not profitable');approve(USDC,MORPHO,amount);
 }
}
