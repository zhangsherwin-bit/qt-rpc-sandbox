// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

// Code-only historical EVM simulation. This contract is NEVER deployed or broadcast.
// Every token unit used in the opportunity must arise from a real Morpho flash loan.
interface IERC20 {
    function balanceOf(address owner) external view returns(uint256);
    function approve(address spender,uint256 amount) external returns(bool);
    function transfer(address to,uint256 amount) external returns(bool);
}
interface IMorpho {
    function flashLoan(address token,uint256 assets,bytes calldata data) external;
}
interface IGSM {
    function sellAsset(uint256 amount,address receiver) external returns(uint256 assetSold,uint256 ghoReceived);
}
interface ISwapRouter {
    struct ExactInputSingleParams {
      address tokenIn; address tokenOut; uint24 fee; address recipient;
      uint256 deadline; uint256 amountIn; uint256 amountOutMinimum;
      uint160 sqrtPriceLimitX96;
    }
    function exactInputSingle(ExactInputSingleParams calldata params) external payable returns(uint256 amountOut);
}
contract GhoCashProbe {
    address public constant MORPHO=0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb;
    address public constant USDC=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address public constant GHO=0x40D16FC0246aD3160Ccc09B8D0D3a2cD28aE6C2f;
    address public constant GSM=0x3A3868898305f04beC7FEa77BecFf04C13444112;
    address public constant ROUTER=0xE592427A0AEce92De3Edee1F18E0157C05861564;
    address public constant BENEFICIARY=0x000000000000000000000000000000000000bAbE;
    function env() external view returns(uint256,uint256,uint256,uint256,
        uint256,uint256,uint256,uint256,uint256,uint256) {
        return (block.chainid,block.number,block.timestamp,block.basefee,
        IERC20(USDC).balanceOf(address(this)),IERC20(GHO).balanceOf(address(this)),
        IERC20(USDC).balanceOf(BENEFICIARY),IERC20(GHO).balanceOf(BENEFICIARY),
        IERC20(USDC).balanceOf(GSM),IERC20(GHO).balanceOf(GSM));
    }
    function run(uint256 principal,uint24 fee) external returns(uint256 paid) {
        require(msg.sender==BENEFICIARY,"ONLY_TEST_BENEFICIARY");
        require(IERC20(USDC).balanceOf(address(this))==0 &&
            IERC20(GHO).balanceOf(address(this))==0,"EXISTING_INVENTORY");
        require(principal>0 && principal<=10000e6,"FINITE_RESEARCH_SIZE");
        require(fee==100 || fee==500,"KNOWN_FEE_TIER");
        IMorpho(MORPHO).flashLoan(USDC,principal,abi.encode(fee));
        require(IERC20(GHO).balanceOf(address(this))==0,"GHO_REMAINDER");
        paid=IERC20(USDC).balanceOf(address(this));
        require(paid>0,"NO_TERMINAL_CASH");
        require(IERC20(USDC).transfer(BENEFICIARY,paid),"PAYOUT_FAIL");
    }
    function onMorphoFlashLoan(uint256 assets,bytes calldata data) external {
        require(msg.sender==MORPHO,"INVALID_CALLBACK");
        require(IERC20(USDC).balanceOf(address(this))==assets,"FLASH_PRINCIPAL_INVALID");
        uint24 fee=abi.decode(data,(uint24));
        require(IERC20(USDC).approve(GSM,assets),"APPROVE_GSM_FAILED");
        (uint256 spent,uint256 obtained)=IGSM(GSM).sellAsset(assets,address(this));
        require(spent==assets && obtained>0,"GSM_EXACT_CASH_IN");
        require(IERC20(GHO).balanceOf(address(this))==obtained,"GHO_TRANSFER_INVALID");
        require(IERC20(GHO).approve(ROUTER,obtained),"APPROVE_ROUTER_FAILED");
        ISwapRouter(ROUTER).exactInputSingle(ISwapRouter.ExactInputSingleParams({
            tokenIn:GHO,tokenOut:USDC,fee:fee,recipient:address(this),
            deadline:block.timestamp,amountIn:obtained,
            amountOutMinimum:assets+1,sqrtPriceLimitX96:0
        }));
        require(IERC20(GHO).balanceOf(address(this))==0,"DUST_GHO");
        require(IERC20(USDC).balanceOf(address(this))>assets,"NO_CASH_EDGE");
        require(IERC20(USDC).approve(MORPHO,assets),"APPROVE_REPAY_FAILED");
    }
}
