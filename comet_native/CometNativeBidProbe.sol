// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
/** Read-only historical eth_simulateV1 probe; ONLY code-overridden at unused synthetic address.
 * Alternate settlement: buy collateral, exact-output repay USDC, then unwrap leftover WETH
 * and pay the original observed producer compensation DIRECTLY in ETH.
 * No storage/balance/oracle/time override, no signing or deployment.
 */
interface IERC20D {
  function balanceOf(address) external view returns(uint256);
}
interface IWETHD {
  function withdraw(uint256) external;
}
interface IAaveD {
  function flashLoanSimple(address,address,uint256,bytes calldata,uint16) external;
}
interface ICometD {
  function isLiquidatable(address) external view returns(bool);
  function absorb(address,address[] calldata) external;
  function buyCollateral(address,uint256,uint256,address) external;
}
interface IRouterD {
  struct ExactOutputSingleParams {
    address tokenIn;
    address tokenOut;
    uint24 fee;
    address recipient;
    uint256 deadline;
    uint256 amountOut;
    uint256 amountInMaximum;
    uint160 sqrtPriceLimitX96;
  }
  function exactOutputSingle(ExactOutputSingleParams calldata) external payable returns(uint256 amountIn);
}
contract CometNativeBidProbe {
  address constant AAVE=0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2;
  address constant COMET=0xc3d688B66703497DAA19211EEdff47f25384cdc3;
  address constant USDC=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
  address constant WETH=0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
  address constant ROUTER=0xE592427A0AEce92De3Edee1F18E0157C05861564;
  address constant BENEF=address(uint160(0xdead8821));
  address constant BORROWER=address(uint160(0x00c3a6203a618438e206c9d1da2ac0dba6f36fcffd));
  uint256 constant OBSERVED_DIRECT_BID=174449845338543024;
  uint256 constant MAX_LOAN=10000000000;
  uint256 private outstanding;
  event Settled(uint256 loan,uint256 premium,uint256 seizedWeth,uint256 swapSpentWeth,uint256 producerPaidWei,uint256 beneficiaryEthWei);
  uint256 private seizedAmount;
  uint256 private spentAmount;
  uint256 private premiumAmount;
  receive() external payable {require(msg.sender==WETH,"only WETH unwrap");}
  function env() external view returns(uint256 chain,uint256 blockNum,uint256 ts,uint256 bf,
     uint256 usdc,uint256 weth,uint256 ethBal,uint256 benefUSDC,uint256 benefWETH,
     uint256 benefETH,uint256 coinbaseETH){
    return (block.chainid,block.number,block.timestamp,block.basefee,
       IERC20D(USDC).balanceOf(address(this)),IERC20D(WETH).balanceOf(address(this)),
       address(this).balance,IERC20D(USDC).balanceOf(BENEF),
       IERC20D(WETH).balanceOf(BENEF),BENEF.balance,block.coinbase.balance);
  }
  function tokenAction(address token,bytes memory data) internal {
    (bool ok,bytes memory out)=token.call(data);
    require(ok && (out.length==0 || abi.decode(out,(bool))),"token action");
  }
  function approveToken(address token,address spender,uint256 amount) internal {
    tokenAction(token,abi.encodeWithSignature("approve(address,uint256)",spender,0));
    tokenAction(token,abi.encodeWithSignature("approve(address,uint256)",spender,amount));
  }
  function run(uint256 loan,uint24 fee,bool matchBid) external returns(uint256 beneficiaryWei){
    require(msg.sender==BENEF,"beneficiary only");
    require(loan==9346567826,"original USDC purchase frozen");
    require(fee==100 || fee==500 || fee==3000 || fee==10000,"unsupported fee");
    require(outstanding==0,"reentrant");
    require(IERC20D(USDC).balanceOf(address(this))==0 &&
            IERC20D(WETH).balanceOf(address(this))==0 &&
            address(this).balance==0,"initial balances");
    require(BENEF!=block.coinbase,"beneficiary is coinbase");
    outstanding=loan;
    IAaveD(AAVE).flashLoanSimple(address(this),USDC,loan,abi.encode(fee),0);
    require(outstanding==0,"loan callback unfinished");
    require(IERC20D(USDC).balanceOf(address(this))==0,"USDC residue");
    uint256 left=IERC20D(WETH).balanceOf(address(this));
    require(left>0,"no surplus WETH");
    IWETHD(WETH).withdraw(left);
    require(IERC20D(WETH).balanceOf(address(this))==0,"WETH residue");
    uint256 producer=matchBid ? OBSERVED_DIRECT_BID : 0;
    require(address(this).balance>producer,"not enough WETH to outbid");
    if(producer>0){
      (bool good,)=payable(block.coinbase).call{value:producer}("");
      require(good,"producer transfer failed");
    }
    beneficiaryWei=address(this).balance;
    (bool good,)=payable(BENEF).call{value:beneficiaryWei}("");
    require(good,"beneficiary transfer failed");
    require(address(this).balance==0 && IERC20D(USDC).balanceOf(address(this))==0,"terminal residue");
    emit Settled(loan,premiumAmount,seizedAmount,spentAmount,producer,beneficiaryWei);
  }
  function executeOperation(address asset,uint256 amount,uint256 premium,
    address initiator,bytes calldata params) external returns(bool){
    require(msg.sender==AAVE && initiator==address(this) && asset==USDC,"bad callback");
    require(outstanding==amount && amount==9346567826,"callback amount");
    uint24 fee=abi.decode(params,(uint24));
    require(IERC20D(USDC).balanceOf(address(this))==amount,"callback USDC mismatch");
    require(ICometD(COMET).isLiquidatable(BORROWER),"borrower not liquidatable");
    address[] memory accounts=new address[](1);
    accounts[0]=BORROWER;
    ICometD(COMET).absorb(address(this),accounts);
    approveToken(USDC,COMET,amount);
    ICometD(COMET).buyCollateral(WETH,0,amount,address(this));
    seizedAmount=IERC20D(WETH).balanceOf(address(this));
    require(seizedAmount>0,"no collateral acquired");
    approveToken(WETH,ROUTER,seizedAmount);
    spentAmount=IRouterD(ROUTER).exactOutputSingle(IRouterD.ExactOutputSingleParams({
       tokenIn:WETH,tokenOut:USDC,fee:fee,recipient:address(this),
       deadline:block.timestamp,amountOut:amount+premium,
       amountInMaximum:seizedAmount,sqrtPriceLimitX96:0
    }));
    require(spentAmount>0 && spentAmount<=seizedAmount,"invalid spent");
    require(IERC20D(USDC).balanceOf(address(this))>=amount+premium,"loan shortfall");
    approveToken(USDC,AAVE,amount+premium);
    premiumAmount=premium;
    outstanding=0;
    return true;
  }
}
