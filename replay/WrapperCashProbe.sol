// SPDX-License-Identifier: MIT
pragma solidity 0.8.34;
// Research eth_call/eth_simulateV1 probe only. No deployment or sending code is provided.
struct MarketParams {address loanToken; address collateralToken; address oracle; address irm; uint256 lltv;}
interface IERC20 {function balanceOf(address) external view returns(uint256);function approve(address,uint256) external returns(bool);function transfer(address,uint256) external returns(bool);}
interface IMorpho {function liquidate(MarketParams calldata,address,uint256,uint256,bytes calldata) external returns(uint256,uint256);}
interface IWrapper {function claimLiquidation(address liquidator,address victim,uint256 amount) external;function REWARD_VAULT() external view returns(address);}
interface IVault {function redeem(uint256,address,address) external returns(uint256);function asset() external view returns(address);}
interface ICurve {function remove_liquidity_one_coin(uint256,int128,uint256) external returns(uint256);function coins(uint256) external view returns(address);}
contract WrapperCashProbe {
 address constant MORPHO=address(bytes20(hex'bbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb'));
 address constant WRAP=address(bytes20(hex'a31b5941f2e74d89bdc66632959fe6a152692920'));
 address constant VAULT=address(bytes20(hex'4fdb3cb3dbd6d24b64276645c1adcb85cbb39dc6'));
 address constant LP=address(bytes20(hex'9a9e2e70919c75d80aaaa1d483c46cdbb8ac4d1b'));
 address constant FRX=address(bytes20(hex'cacd6fd266af91b8aed52accc382b4e165586e29'));
 address constant USDC=address(bytes20(hex'a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'));
 address constant CUST=address(bytes20(hex'4f95c5ba0c7c69fb2f9340e190ccee890b3bd87c'));
 address constant USTB=address(bytes20(hex'00000000564ee6a571c5819057f27bb671e78bd5'));
 address constant ORACLE=address(bytes20(hex'9aa3bfb984f520eb18a34030110010509a985b52'));
 address constant IRM=address(bytes20(hex'870ac11d48b15db9a138cf899d20f13f79ba00bc'));
 bool private armed; address private victim; uint256 private size; uint256 private fraction;
 uint256 private cashRequired; uint256 private lpReceived; uint256 private lpBurned;
 function environment() external view returns(uint256,uint256,uint256,uint256){return(block.chainid,block.number,block.timestamp,address(this).balance);}
 function bal(address token) internal view returns(uint256){return IERC20(token).balanceOf(address(this));}
 function approve(address token,address spender,uint256 n) internal {require(IERC20(token).approve(spender,0),'reset');require(IERC20(token).approve(spender,n),'approve');}
 function execute(address borrower,uint256 seized,uint256 lpBps,address exit,uint256 minimumUSDC) external returns(uint256 repaid,uint256 receivedLP,uint256 burnedLP,uint256 surplusFRX,uint256 paidUSDC,uint256 residualLP,uint256 internalGas){
  uint256 g=gasleft(); require(!armed && block.chainid==1 && address(this).balance==0,'environment');
  require(exit==address(0)||exit==CUST||exit==USTB,'exit');require(lpBps>0&&lpBps<=10000,'fraction');
  if(exit!=address(0))require(lpBps==10000,'cash requires all LP');
  require(bal(WRAP)==0&&bal(VAULT)==0&&bal(LP)==0&&bal(FRX)==0&&bal(USDC)==0,'initial principal');
  require(IWrapper(WRAP).REWARD_VAULT()==VAULT&&IVault(VAULT).asset()==LP&&ICurve(LP).coins(0)==FRX,'route mismatch');
  victim=borrower;size=seized;fraction=lpBps;cashRequired=0;lpReceived=0;lpBurned=0;armed=true;
  (,repaid)=IMorpho(MORPHO).liquidate(MarketParams(FRX,WRAP,ORACLE,IRM,915000000000000000),borrower,seized,0,hex'01');
  require(!armed&&repaid==cashRequired,'callback');receivedLP=lpReceived;burnedLP=lpBurned;
  require(bal(WRAP)==0&&bal(VAULT)==0,'collateral residue');surplusFRX=bal(FRX);residualLP=bal(LP);require(surplusFRX>0,'no surplus');
  if(exit!=address(0)){
   require(residualLP==0,'LP residue');approve(FRX,exit,surplusFRX);IVault(exit).redeem(surplusFRX,address(this),address(this));
   paidUSDC=bal(USDC);require(paidUSDC>0&&paidUSDC>=minimumUSDC&&bal(FRX)==0,'cash closure');
   require(IERC20(USDC).transfer(msg.sender,paidUSDC),'payout');
  }else{
   require(IERC20(FRX).transfer(msg.sender,surplusFRX),'frx payout');
   if(residualLP>0)require(IERC20(LP).transfer(msg.sender,residualLP),'LP payout');
  }
  require(bal(FRX)==0&&bal(USDC)==0&&bal(LP)==0&&address(this).balance==0,'terminal residue');internalGas=g-gasleft();
 }
 function onMorphoLiquidate(uint256 assets,bytes calldata) external {
  require(msg.sender==MORPHO&&armed&&bal(WRAP)==size,'authenticated liquidation');armed=false;cashRequired=assets;
  // Exact victim receives its own accrued rewards inside the protocol wrapper. No reward redirection.
  IWrapper(WRAP).claimLiquidation(address(this),victim,size);
  uint256 shares=bal(VAULT);require(shares>0,'no vault shares');IVault(VAULT).redeem(shares,address(this),address(this));
  lpReceived=bal(LP);lpBurned=lpReceived*fraction/10000;require(lpBurned>0,'no LP');
  ICurve(LP).remove_liquidity_one_coin(lpBurned,0,assets);
  require(bal(FRX)>=assets,'repayment deficit');approve(FRX,MORPHO,assets);
 }
}
