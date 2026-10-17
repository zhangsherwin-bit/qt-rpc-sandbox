// SPDX-License-Identifier: MIT
pragma solidity 0.8.34;
interface Token {function balanceOf(address) external view returns(uint);function approve(address,uint) external returns(bool);function transfer(address,uint) external returns(bool);}
interface Weth {function withdraw(uint) external;}
interface Tri {function coins(uint) external view returns(address);function get_dy(uint,uint,uint) external view returns(uint);function exchange(uint,uint,uint,uint,bool) external payable returns(uint);}
interface Stable {function coins(uint) external view returns(address);function get_dy(int128,int128,uint) external view returns(uint);function exchange(int128,int128,uint,uint) external returns(uint);}
interface Quoter {struct P {address tokenIn;address tokenOut;uint amountIn;uint24 fee;uint160 limit;}function quoteExactInputSingle(P calldata) external returns(uint,uint160,uint32,uint);}
interface Router {struct Input {address tin;address tout;uint24 fee;address recipient;uint deadline;uint amount;uint minimum;uint160 limit;}struct Output {address tin;address tout;uint24 fee;address recipient;uint deadline;uint amount;uint maximum;uint160 limit;}function exactInputSingle(Input calldata) external payable returns(uint);function exactOutputSingle(Output calldata) external payable returns(uint);}
interface Flash {function flashLoan(address,uint,bytes calldata) external;}
abstract contract Venues {
 address constant U=address(bytes20(hex'a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'));
 address constant W=address(bytes20(hex'c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'));
 address constant C=address(bytes20(hex'f939e0a03fb07f59a73314e73794be0e57ac1b4e'));
 address constant T=address(bytes20(hex'4ebdf703948ddcea3b11f675b4d1fba9d2414a14'));
 address constant S=address(bytes20(hex'4dece678ceceb27446b35c672dc7d61f30bad69e'));
 address constant Q=address(bytes20(hex'61ffe014ba17989e743c5f6cb21bf9697530b21e'));
 address constant R=address(bytes20(hex'e592427a0aece92de3edee1f18e0157c05861564'));
 address constant M=address(bytes20(hex'bbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb'));
 function guard() internal view {require(block.chainid==1&&Tri(T).coins(0)==C&&Tri(T).coins(1)==W&&Stable(S).coins(0)==U&&Stable(S).coins(1)==C,'venue identity');}
}
contract QuoteStudy is Venues {
 function one(uint x,uint24 f,bool rev) external returns(uint out,uint a,uint b) {
  require(msg.sender==address(this),'self only');
  if(!rev){(a,,,)=Quoter(Q).quoteExactInputSingle(Quoter.P(U,W,x,f,0));b=Tri(T).get_dy(1,0,a);out=Stable(S).get_dy(1,0,b);}
  else {a=Stable(S).get_dy(0,1,x);b=Tri(T).get_dy(0,1,a);(out,,,)=Quoter(Q).quoteExactInputSingle(Quoter.P(W,U,b,f,0));}
 }
 function quotes() external returns(uint[4] memory context,uint[8][32] memory rows){
  guard();context=[block.chainid,block.number,block.timestamp,block.basefee];
  uint[8] memory sizes=[uint(100),250,500,1000,2000,2500,5000,20000];uint k;
  for(uint i;i<8;i++)for(uint j;j<2;j++)for(uint d;d<2;d++){
   uint x=sizes[i]*1e6;uint24 f=j==0?100:500;rows[k][0]=x;rows[k][1]=f;rows[k][2]=d;uint g=gasleft();
   try this.one(x,f,d==1) returns(uint out,uint a,uint b){rows[k][3]=1;rows[k][4]=out;rows[k][5]=a;rows[k][6]=b;rows[k][7]=g-gasleft();}
   catch(bytes memory reason){rows[k][7]=uint(keccak256(reason));}k++;
  }
 }
}
contract CashStudy is Venues {
 bool private active;bool private done;uint private amount;uint24 private fee;bool private rev;
 error Shortfall(uint required,uint available);
 receive() external payable {require(active&&msg.sender==W,'native sender');}
 function bal(address t) internal view returns(uint){return Token(t).balanceOf(address(this));}
 function approve(address t,address s,uint x) internal {require(Token(t).approve(s,0)&&Token(t).approve(s,x),'approve');}
 function environment() external view returns(uint[9] memory){return [block.chainid,block.number,block.timestamp,address(this).balance,bal(U),bal(W),bal(C),msg.sender.balance,Token(U).balanceOf(msg.sender)];}
 function execute(uint x,uint24 f,bool reverse,uint reserve,uint minimum) external returns(uint loan,uint gross,uint reserveCost,uint paid,uint nativePaid){
  guard();require(!active&&(f==100||f==500)&&x>0,'input');require(address(this).balance==0&&bal(U)==0&&bal(W)==0&&bal(C)==0,'initial principal');
  active=true;done=false;amount=x;fee=f;rev=reverse;Flash(M).flashLoan(U,x,hex'01');require(done,'callback');loan=x;gross=bal(U);
  if(reserve>0){approve(U,R,gross);reserveCost=Router(R).exactOutputSingle(Router.Output(U,W,500,address(this),block.timestamp,reserve,gross,0));require(bal(W)==reserve,'reserve');Weth(W).withdraw(reserve);(bool ok,)=payable(msg.sender).call{value:reserve}('');require(ok,'reserve delivery');nativePaid=reserve;}
  paid=bal(U);require(paid>=minimum,'minimum');require(Token(U).transfer(msg.sender,paid),'cash delivery');require(address(this).balance==0&&bal(U)==0&&bal(W)==0&&bal(C)==0,'residue');active=false;
 }
 function onMorphoFlashLoan(uint x,bytes calldata) external {
  require(active&&!done&&msg.sender==M&&x==amount&&bal(U)==amount,'callback authentication');done=true;
  if(!rev){approve(U,R,x);uint w=Router(R).exactInputSingle(Router.Input(U,W,fee,address(this),block.timestamp,x,1,0));approve(W,T,w);Tri(T).exchange(1,0,w,1,false);uint c=bal(C);approve(C,S,c);Stable(S).exchange(1,0,c,1);}
  else {approve(U,S,x);Stable(S).exchange(0,1,x,1);uint c=bal(C);approve(C,T,c);Tri(T).exchange(0,1,c,1,false);uint w=bal(W);approve(W,R,w);Router(R).exactInputSingle(Router.Input(W,U,fee,address(this),block.timestamp,w,1,0));}
  if(bal(U)<x)revert Shortfall(x,bal(U));approve(U,M,x);
 }
}
