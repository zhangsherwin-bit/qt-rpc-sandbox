// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * Exact observed Compound III USDC/WETH collateral purchase.
 * Research-only code deployed solely by eth_simulateV1 code override at an
 * unused address. No production contract or storage is modified.
 * Aave V3 flashLoanSimple -> Comet.buyCollateral -> Uniswap V3 exactInputSingle
 * -> repay Aave -> transfer all excess USDC to frozen research beneficiary.
 */
interface IERC20 {
    function balanceOf(address who) external view returns (uint256);
}
interface IAavePool {
    function flashLoanSimple(address receiver,address asset,uint256 amount,bytes calldata params,uint16 referralCode) external;
}
interface IComet {
    function buyCollateral(address asset,uint256 minAmount,uint256 baseAmount,address recipient) external;
}
interface ISwapRouter {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
    }
    function exactInputSingle(ExactInputSingleParams calldata params) external payable returns(uint256);
}
contract CometCashProbe {
    address internal constant AAVE = 0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2;
    address internal constant COMET = 0xc3d688B66703497DAA19211EEdff47f25384cdc3;
    address internal constant USDC = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address internal constant WETH = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    address internal constant ROUTER = 0xE592427A0AEce92De3Edee1F18E0157C05861564;
    address internal constant BENEF = address(uint160(0xdead8821));
    uint256 private constant MIN_LOAN = 1_000_000; // minimum 1 USDC
    event CollateralAndSwap(uint256 loan,uint256 premium,uint256 collateralIn,uint256 usdcAfterSwap);
    event PaidInUSDC(uint256 amount);

    function _tokenCall(address t,bytes memory callData) internal {
        (bool ok, bytes memory result)=t.call(callData);
        require(ok && (result.length==0 || abi.decode(result,(bool))),"token action failed");
    }
    function _approve(address t,address spender,uint256 amt) internal {
        _tokenCall(t,abi.encodeWithSignature("approve(address,uint256)",spender,0));
        _tokenCall(t,abi.encodeWithSignature("approve(address,uint256)",spender,amt));
    }
    function env() external view returns
      (uint256 chain,uint256 blockNum,uint256 ts,uint256 basefee,uint256 probeUSDC,uint256 probeWETH,
       uint256 beneficiaryUSDC,uint256 beneficiaryWETH,uint256 beneficiaryETH) {
        return (block.chainid,block.number,block.timestamp,block.basefee,
          IERC20(USDC).balanceOf(address(this)),IERC20(WETH).balanceOf(address(this)),
          IERC20(USDC).balanceOf(BENEF),IERC20(WETH).balanceOf(BENEF),BENEF.balance);
    }

    function run(uint256 loan,uint24 fee,uint256 minimumProfit) external returns(uint256 cashOut) {
        require(msg.sender==BENEF,"frozen synthetic beneficiary only");
        require(loan>=MIN_LOAN && loan<=50_000_000_000,"bounded USDC loan");
        require(fee==500 || fee==3000,"fee not frozen");
        require(minimumProfit>=1_000_000,"require positive cash");
        require(IERC20(USDC).balanceOf(address(this))==0 &&
                IERC20(WETH).balanceOf(address(this))==0,"initial inventory");
        uint256 pre=IERC20(USDC).balanceOf(BENEF);
        IAavePool(AAVE).flashLoanSimple(address(this),USDC,loan,abi.encode(fee,minimumProfit),0);
        cashOut=IERC20(USDC).balanceOf(address(this));
        require(cashOut>=minimumProfit,"no terminal surplus");
        _tokenCall(USDC,abi.encodeWithSignature("transfer(address,uint256)",BENEF,cashOut));
        require(IERC20(USDC).balanceOf(address(this))==0,"unpaid USDC residue");
        require(IERC20(WETH).balanceOf(address(this))==0,"unconverted WETH");
        require(IERC20(USDC).balanceOf(BENEF)==pre+cashOut,"cash payout mismatched");
        emit PaidInUSDC(cashOut);
        return cashOut;
    }
    function executeOperation(address asset,uint256 amount,uint256 premium,
        address initiator,bytes calldata params) external returns(bool) {
        require(msg.sender==AAVE && initiator==address(this) && asset==USDC,"bad callback");
        (uint24 fee,uint256 minProfit)=abi.decode(params,(uint24,uint256));
        require(amount>=MIN_LOAN,"bad loan amount");
        require(IERC20(USDC).balanceOf(address(this))==amount,"unexpected callback cash");
        _approve(USDC,COMET,amount);
        IComet(COMET).buyCollateral(WETH,0,amount,address(this));
        uint256 seized=IERC20(WETH).balanceOf(address(this));
        require(seized>0,"no available collateral");
        _approve(WETH,ROUTER,seized);
        uint256 got=ISwapRouter(ROUTER).exactInputSingle(
            ISwapRouter.ExactInputSingleParams({
                tokenIn:WETH,tokenOut:USDC,fee:fee,recipient:address(this),
                deadline:block.timestamp,amountIn:seized,
                amountOutMinimum:amount+premium+minProfit,sqrtPriceLimitX96:0
            })
        );
        require(IERC20(WETH).balanceOf(address(this))==0,"residual WETH");
        require(got>=amount+premium+minProfit,"flash principal or fee not covered");
        _approve(USDC,AAVE,amount+premium);
        emit CollateralAndSwap(amount,premium,seized,got);
        return true;
    }
}
