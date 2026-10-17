// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;
interface Token {function balanceOf(address) external view returns(uint);function approve(address,uint) external returns(bool);function transfer(address,uint) external returns(bool);}
interface Wrapped {function withdraw(uint) external;function deposit() external payable;}
interface Flash {function flashLoan(address,uint,bytes calldata) external;}
interface Keeper {function update(address) external returns(uint);function pool() external view returns(address);}
interface Pool {function coins(uint) external view returns(address);}
interface Liquidator {function batchLiquidateTroves(uint[] calldata) external;function collToken() external view returns(address);}
interface ARM {function swapExactTokensForTokens(address,address,uint,uint,address) external returns(uint[] memory);}
interface WstETH {function unwrap(uint) external returns(uint);}
interface Auction {function want() external view returns(address);function take(address,uint,address,bytes calldata) external returns(uint);}
interface Router {
 struct ExactInputSingleParams {address tokenIn;address tokenOut;uint24 fee;address recipient;uint deadline;uint amountIn;uint amountOutMinimum;uint160 sqrtPriceLimitX96;}
 function exactInputSingle(ExactInputSingleParams calldata) external payable returns(uint);
}
contract CashProbe {
 address constant WETH=address(bytes20(hex"c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"));
 address constant STETH=address(bytes20(hex"ae7ab96520de3a18e5e111b5eaab095312d7fe84"));
 address constant WSTETH=address(bytes20(hex"7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"));
 address constant USDC=address(bytes20(hex"a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"));
 address constant USDT=address(bytes20(hex"dac17f958d2ee523a2206206994597c13d831ec7"));
 address constant ARM_ADDR=address(bytes20(hex"85b78aca6deae198fbf201c82daf6ca21942acc6"));
 address constant CURVE=address(bytes20(hex"dc24316b9ae028f1497c275eb9192a3ea0f67022"));
 address constant MORPHO=address(bytes20(hex"bbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb"));
 address constant ROUTER=address(bytes20(hex"e592427a0aece92de3edee1f18e0157c05861564"));
 address constant BENEFICIARY=address(bytes20(hex"00000000000000000000000000000000dead8821"));
 bool busy;uint principal;uint armMode;address auctionA;address auctionB;address fromA;address fromB;uint amountB;
 error CashShortfall(uint available,uint needed);
 error Measurement(address token,uint paid);
 error NoReward();
 struct Job {uint kind;address target;uint[] ids;uint amount;uint mode;bytes extra;}
 struct Result {bool completed;bytes data;uint gasUsed;}
 receive() external payable {require(msg.sender==WETH||msg.sender==CURVE,"unexpected ETH");}
 function balance(address t) internal view returns(uint){return Token(t).balanceOf(address(this));}
 function approve(address t,address s,uint a) internal{require(Token(t).approve(s,0),"approve0");require(Token(t).approve(s,a),"approve");}
 function raw(address t,bytes memory d,uint value) internal returns(bytes memory r){bool ok;(ok,r)=t.call{value:value}(d);if(!ok)assembly{revert(add(r,32),mload(r))}}
 function env() external view returns(uint,uint,uint,uint,uint,uint){return(block.chainid,block.number,block.timestamp,block.basefee,address(this).balance,BENEFICIARY.balance);}
 function balances(address[] calldata ts) external view returns(uint[] memory out){out=new uint[](ts.length);for(uint i;i<ts.length;i++)out[i]=balance(ts[i]);}
 function payout(address t) internal returns(uint n){n=balance(t);if(n==0)revert NoReward();if(t==WETH){Wrapped(WETH).withdraw(n);(bool ok,)=BENEFICIARY.call{value:n}("");require(ok,"ETH payout");}else{require(t==USDC||t==USDT,"not terminal cash");require(Token(t).transfer(BENEFICIARY,n),"payout");}require(balance(t)==0&&address(this).balance==0,"residue");}
 function execute(Job calldata j) external returns(address token,uint paid){require(msg.sender==BENEFICIARY||msg.sender==address(this),"caller");require(!busy&&address(this).balance==0,"busy/native");busy=true;
  if(j.kind==0){require(balance(WETH)==0&&balance(STETH)==0,"initial inventory");principal=j.amount;armMode=j.mode;Flash(MORPHO).flashLoan(WETH,principal,"");require(balance(STETH)<=2,"stETH residue");token=WETH;paid=payout(token);principal=0;}
  else if(j.kind==1){address p=Keeper(j.target).pool();address c=Pool(p).coins(0);require(c==USDC||c==USDT,"cash coin");require(balance(p)==0&&balance(c)==0,"initial inventory");Keeper(j.target).update(address(this));uint lp=balance(p);if(lp==0)revert NoReward();raw(p,abi.encodeWithSignature("remove_liquidity_one_coin(uint256,int128,uint256)",lp,int128(0),uint(0)),0);require(balance(p)==0,"LP residue");token=c;paid=payout(c);}
  else if(j.kind==2){address c=Liquidator(j.target).collToken();require(balance(c)==0&&balance(WETH)==0&&balance(STETH)==0,"initial inventory");Liquidator(j.target).batchLiquidateTroves(j.ids);uint n=balance(c);if(c==WSTETH){WstETH(c).unwrap(n);c=STETH;n=balance(c);}if(c==STETH){approve(c,j.mode==0?ARM_ADDR:CURVE,n);if(j.mode==0)ARM(ARM_ADDR).swapExactTokensForTokens(c,WETH,n,0,address(this));else{raw(CURVE,abi.encodeWithSignature("exchange(int128,int128,uint256,uint256)",int128(1),int128(0),n,uint(0)),0);Wrapped(WETH).deposit{value:address(this).balance}();}require(balance(STETH)<=2,"stETH residue");}else if(c!=WETH&&n>0){approve(c,ROUTER,n);Router(ROUTER).exactInputSingle(Router.ExactInputSingleParams(c,WETH,3000,address(this),block.timestamp,n,0,0));require(balance(c)==0,"collateral residue");}token=WETH;paid=payout(token);}
  else if(j.kind==3){(auctionA,auctionB,fromA,fromB,amountB)=abi.decode(j.extra,(address,address,address,address,uint));require(auctionA!=auctionB&&Auction(auctionA).want()==fromB&&Auction(auctionB).want()==fromA,"pair mismatch");require(balance(fromA)==0&&balance(fromB)==0,"initial inventory");Auction(auctionA).take(fromA,j.amount,address(this),hex"01");require(balance(fromA)==0,"noncash residue");token=fromB;paid=payout(token);}
  else revert("kind");busy=false;
 }
 function onMorphoFlashLoan(uint assets,bytes calldata) external {require(busy&&msg.sender==MORPHO&&assets==principal&&balance(WETH)==assets,"flash auth");Wrapped(WETH).withdraw(assets);raw(CURVE,abi.encodeWithSignature("exchange(int128,int128,uint256,uint256)",int128(0),int128(1),assets,uint(0)),assets);uint got=balance(STETH);approve(STETH,armMode==0?ARM_ADDR:CURVE,got);if(armMode==0)ARM(ARM_ADDR).swapExactTokensForTokens(STETH,WETH,got,0,address(this));else{raw(CURVE,abi.encodeWithSignature("exchange(int128,int128,uint256,uint256)",int128(1),int128(0),got,uint(0)),0);Wrapped(WETH).deposit{value:address(this).balance}();}if(balance(WETH)<assets)revert CashShortfall(balance(WETH),assets);approve(WETH,MORPHO,assets);}
 function auctionTakeCallback(address f,address sender,uint amount,uint needed,bytes calldata) external{require(busy&&sender==address(this),"auction sender");if(msg.sender==auctionA){require(f==fromA&&balance(fromA)>=amount,"A");Auction(auctionB).take(fromB,amountB,address(this),hex"02");if(balance(fromB)<needed)revert CashShortfall(balance(fromB),needed);approve(fromB,auctionA,needed);}else{require(msg.sender==auctionB&&f==fromB,"B");if(balance(fromA)<needed)revert CashShortfall(balance(fromA),needed);approve(fromA,auctionB,needed);}}
 function measure(Job calldata j) external{require(msg.sender==address(this),"measure self");(address t,uint n)=this.execute(j);revert Measurement(t,n);}
 function matrix(Job[] calldata js) external returns(Result[] memory r){require(msg.sender==BENEFICIARY,"matrix caller");r=new Result[](js.length);for(uint i;i<js.length;i++){uint before=gasleft();(bool ok,bytes memory d)=address(this).call(abi.encodeCall(this.measure,(js[i])));require(!ok,"missing reset");bytes4 s;if(d.length>=4)assembly{s:=mload(add(d,32))}r[i]=Result(s==Measurement.selector,d,before-gasleft());}require(!busy&&address(this).balance==0,"matrix leaked state");}
}
