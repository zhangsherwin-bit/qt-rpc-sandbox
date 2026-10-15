// SPDX-License-Identifier: MIT
pragma solidity 0.8.34;
// Read-only research wrapper. No deployment or transaction sending scripts.
struct MP { address loanToken; address collateralToken; address oracle; address irm; uint256 lltv; }
interface T { function balanceOf(address) external view returns(uint256); function approve(address,uint256) external returns(bool); }
interface V { function asset() external view returns(address); function redeem(uint256,address,address) external returns(uint256); }
interface M { function liquidate(MP calldata,address,uint256,uint256,bytes calldata) external returns(uint256,uint256); }
interface A { function liquidationCall(address,address,address,uint256,bool) external; function getUserAccountData(address) external view returns(uint256,uint256,uint256,uint256,uint256,uint256); }
contract HistoricalCashProbe {
 address constant CALLER=address(0xa71502);
 address constant MORPHO=address(bytes20(hex"bbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb"));
 address constant USDC=address(bytes20(hex"833589fcd6edb6e08f4c7c32d4f71b54bda02913"));
 address constant YO=address(bytes20(hex"0000000f2eb9f69274678c76222b35eec7588a65"));
 address constant POOL=address(bytes20(hex"87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"));
 address constant WETH=address(bytes20(hex"c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"));
 bool transient active; uint256 transient received;
 function environment() external view returns(uint256,uint256,uint256,uint256) { return(block.chainid,block.number,block.timestamp,address(this).balance); }
 function yo(address borrower,uint256 seize) external returns(uint256 cash,uint256 repaid,uint256 released,uint256 internalGas) {
  uint256 g=gasleft();require(msg.sender==CALLER && block.chainid==8453 && !active,"DOMAIN");
  require(address(this).balance==0 && T(USDC).balanceOf(address(this))==0 && T(YO).balanceOf(address(this))==0,"ENDOWMENT");
  require(V(YO).asset()==USDC,"UNDERLYING");active=true;received=0;
  MP memory m=MP(USDC,YO,address(bytes20(hex"77f59c5c09e7abef6991b456170930324fe36222")),address(bytes20(hex"46415998764c29ab2a25cbea6254146d50d22687")),915000000000000000);
  (,repaid)=M(MORPHO).liquidate(m,borrower,seize,0,hex"01");
  cash=T(USDC).balanceOf(address(this));released=received;
  require(cash>0 && released==cash+repaid && T(YO).balanceOf(address(this))==0,"NOT_CASH_CLOSED");
  require(T(USDC).approve(MORPHO,0),"RESET");active=false;internalGas=g-gasleft();
 }
 function onMorphoLiquidate(uint256 due,bytes calldata) external {
  require(msg.sender==MORPHO && active,"CALLBACK");
  V(YO).redeem(T(YO).balanceOf(address(this)),address(this),address(this));
  received=T(USDC).balanceOf(address(this));require(received>due && T(YO).balanceOf(address(this))==0,"NO_CASH_EXIT");
  require(T(USDC).approve(MORPHO,due),"APPROVE");
 }
 function aave(address borrower,uint256 debtToCover) external returns(uint256 cash,uint256 internalGas) {
  uint256 g=gasleft();require(msg.sender==CALLER && block.chainid==1,"DOMAIN");
  require(address(this).balance==0 && T(WETH).balanceOf(address(this))==0,"ENDOWMENT");
  (,uint256 startDebt,,,,)=A(POOL).getUserAccountData(address(this));require(startDebt==0,"START_DEBT");
  require(T(WETH).approve(POOL,type(uint256).max),"APPROVE");
  A(POOL).liquidationCall(WETH,WETH,borrower,debtToCover,false);
  cash=T(WETH).balanceOf(address(this));require(cash>0,"NO_CASH_SURPLUS");
  (,uint256 finalDebt,,,,)=A(POOL).getUserAccountData(address(this));require(finalDebt==0,"FINAL_DEBT");
  require(T(WETH).approve(POOL,0),"RESET");internalGas=g-gasleft();
 }
}
