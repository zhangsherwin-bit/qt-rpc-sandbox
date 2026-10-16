// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity 0.8.34;
// RESEARCH ONLY: eth_call code overrides. No live deployment or principal.
// Interfaces: morpho-org/midnight 581aa26b445a52cf131858da200eb0f825aee89e.
struct CP { address token; uint256 lltv; uint256 liquidationCursor; address oracle; }
struct Market { uint256 chainId; address midnight; address loanToken; CP[] collateralParams; uint256 maturity; uint256 rcfThreshold; address enterGate; address liquidatorGate; }
struct Offer { Market market; bool buy; address maker; uint256 start; uint256 expiry; uint256 tick; bytes32 group; address callback; bytes callbackData; address receiverIfMakerIsSeller; address ratifier; bool reduceOnly; uint128 maxUnits; uint128 maxAssets; uint256 continuousFeeCap; }
interface Token { function balanceOf(address) external view returns(uint256); function approve(address,uint256) external returns(bool); }
interface Midnight {
 function credit(bytes32,address) external view returns(uint128);
 function debt(bytes32,address) external view returns(uint128);
 function take(Offer memory,bytes memory,uint256,address,address,address,bytes memory) external returns(uint256,uint256);
 function withdraw(Market memory,uint256,address,address) external;
 function liquidate(Market memory,uint256,uint256,uint256,address,bool,address,address,bytes memory) external returns(uint256,uint256);
}
contract CashProbe {
 address constant CORE=0xAdedD8ab6dE832766Fedf0FaC4992E5C4D3EA18A;
 address constant USDC=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
 address constant RESEARCH_CALLER=address(0xa71502);
 bytes32 constant OK=keccak256("morpho.midnight.callbackSuccess");
 bytes32 private activeId; uint256 private activeUnits; uint256 private mode; bool private seen;
 function environment() external view returns(uint256,uint256,uint256,uint256) {return(block.chainid,block.number,block.timestamp,address(this).balance);}
 function id(Market memory m) public pure returns(bytes32) {return keccak256(abi.encodePacked(uint8(0xff),m.midnight,uint256(0),keccak256(abi.encodePacked(hex"600b380380600b5f395ff3",abi.encode(m)))));}
 function start(Market memory m,uint256 newMode,uint256 units) private {
  require(msg.sender==RESEARCH_CALLER && mode==0,"RESEARCH_ONLY");
  require(m.chainId==block.chainid && block.chainid==8453 && m.midnight==CORE && m.loanToken==USDC,"DOMAIN");
  require(address(this).balance==0 && Token(USDC).balanceOf(address(this))==0,"STARTING_PRINCIPAL");
  activeId=id(m);
  require(Midnight(CORE).credit(activeId,address(this))==0 && Midnight(CORE).debt(activeId,address(this))==0,"STARTING_POSITION");
  mode=newMode;seen=false;activeUnits=units;
  require(Token(USDC).approve(CORE,type(uint256).max),"APPROVE");
 }
 function finish(uint256 initialGas) private returns(uint256,uint256) {
  require(seen,"CALLBACK_NOT_SEEN");
  require(Midnight(CORE).credit(activeId,address(this))==0 && Midnight(CORE).debt(activeId,address(this))==0,"RESIDUAL_POSITION");
  uint256 cash=Token(USDC).balanceOf(address(this));require(cash>0,"NO_POSITIVE_CASH");
  mode=0;return(cash,initialGas-gasleft());
 }
 function runTake(Offer memory o,bytes memory ratifierData,uint256 units) external returns(uint256,uint256) {
  uint256 g=gasleft();require(!o.buy && units>0,"NOT_ASK");start(o.market,1,units);
  Midnight(CORE).take(o,ratifierData,units,address(this),address(0),address(this),hex"");return finish(g);
 }
 function onBuy(bytes32 mid,Market memory m,uint256 buyerAssets,uint256 units,uint256,address buyer,bytes memory) external returns(bytes32) {
  require(msg.sender==CORE && mode==1 && !seen && mid==activeId && id(m)==activeId,"BUY_CALLBACK");
  require(buyer==address(this) && units==activeUnits,"BUY_SIZE");seen=true;
  Midnight(CORE).withdraw(m,units,address(this),address(this));
  require(Token(USDC).balanceOf(address(this))>=buyerAssets,"CASH_REPAYMENT");return OK;
 }
 function runCashLiquidation(Market memory m,uint256 index,address borrower,uint256 seized,uint256 repaid,bool post) external returns(uint256,uint256) {
  uint256 g=gasleft();require(m.collateralParams[index].token==USDC,"NOT_CASH_COLLATERAL");
  require((seized==0)!=(repaid==0),"SIZE");start(m,2,0);
  Midnight(CORE).liquidate(m,index,seized,repaid,borrower,post,address(this),address(this),hex"");return finish(g);
 }
 function onLiquidate(address caller,bytes32 mid,Market memory m,uint256 index,uint256,uint256 repaid,address,address receiver,bytes memory,uint256 badDebt) external returns(bytes32) {
  require(msg.sender==CORE && mode==2 && !seen && caller==address(this),"LIQUIDATE_CALLBACK");
  require(mid==activeId && id(m)==activeId && receiver==address(this) && m.collateralParams[index].token==USDC,"LIQUIDATE_DOMAIN");
  require(badDebt==0,"BAD_DEBT_UNSUPPORTED");seen=true;
  require(Token(USDC).balanceOf(address(this))>=repaid,"LIQUIDATION_CASH");return OK;
 }
}
