"""Pure source transformations and cash accounting; no network access."""
import hashlib
BASE_SHA='664c7eb61037c7ab4c0d66125c3cd680d106e81f75d94562b112088ff522f484'
CRVUSD='0xf939e0a03fb07f59a73314e73794be0e57ac1b4e'
DIRECT='0x4dece678ceceb27446b35c672dc7d61f30bad69e'
TRI='0x4ebdf703948ddcea3b11f675b4d1fba9d2414a14'

def normlogs(xs):
    return [(x['address'].lower(),tuple(t.lower() for t in x['topics']),x['data'].lower()) for x in xs]

def logbag(c):
    if c.get('error'): return []
    out=[(x.get('address',c.get('to','')).lower(),tuple(t.lower() for t in x['topics']),x['data'].lower()) for x in c.get('logs',[])]
    for child in c.get('calls',[]): out+=logbag(child)
    return out

def native_delta(c,who):
    if c.get('error'): return 0
    f=c.get('from','').lower();t=c.get('to','').lower();v=int(c.get('value','0x0'),16)
    real=c.get('type','CALL').upper() in ('CALL','CREATE','CREATE2','SELFDESTRUCT')
    ans=((v if t==who and f!=who else 0)-(v if f==who and t!=who else 0)) if real else 0
    return ans+sum(native_delta(x,who) for x in c.get('calls',[]))

def compensation(receipt,header,direct):
    tip=int(receipt['effectiveGasPrice'],16)-int(header['baseFeePerGas'],16)
    if tip<0 or direct<0: raise ValueError('invalid fee values')
    return direct+int(receipt['gasUsed'],16)*tip

def historical_headroom(header,prefix_receipts):
    used=sum(int(x['gasUsed'],16) for x in prefix_receipts)
    left=int(header['gasLimit'],16)-used
    if left<=0: raise ValueError('no historical gas headroom')
    return left

def transform(s):
    if hashlib.sha256(s.encode()).hexdigest()!=BASE_SHA: raise ValueError('unexpected baseline source')
    s=s.replace(' bool busy;', ' uint producerPayment;\n bool busy;',1)
    a=s.index('  else if(j.kind==1)');b=s.index('  else if(j.kind==2)',a)
    branch='''  else if(j.kind==1){
   address p=Keeper(j.target).pool();uint index=j.mode>=3?1:0;address c=Pool(p).coins(index);
   require((index==0&&(c==USDC||c==USDT))||(index==1&&c==CRVUSD),"unexpected reward coin");
   require(balance(p)==0&&balance(c)==0&&balance(WETH)==0,"initial reward inventory");
   Keeper(j.target).update(address(this));uint lp=balance(p);if(lp==0)revert NoReward();
   raw(p,abi.encodeWithSignature("remove_liquidity_one_coin(uint256,int128,uint256)",lp,int128(int256(index)),uint(0)),0);
   require(balance(p)==0,"LP residue");uint n=balance(c);
   if(j.mode==3){require(Pool(DIRECT).coins(0)==USDC&&Pool(DIRECT).coins(1)==CRVUSD,"direct coins");approve(c,DIRECT,n);raw(DIRECT,abi.encodeWithSignature("exchange(int128,int128,uint256,uint256)",int128(1),int128(0),n,uint(0)),0);require(balance(c)==0,"crv residue");c=USDC;n=balance(c);}
   if(j.mode==4){require(Pool(TRI).coins(0)==CRVUSD&&Pool(TRI).coins(1)==WETH,"tri coins");approve(c,TRI,n);raw(TRI,abi.encodeWithSignature("exchange(uint256,uint256,uint256,uint256,bool)",uint(0),uint(1),n,uint(0),false),0);require(balance(c)==0,"crv residue");}
   else if(j.mode>0){approve(c,ROUTER,n);Router(ROUTER).exactInputSingle(Router.ExactInputSingleParams(c,WETH,j.mode==2?100:500,address(this),block.timestamp,n,0,0));require(balance(c)==0,"stable residue");}
   if(j.mode==0){require(producerPayment==0,"native payment only");token=c;paid=payout(c);}else{token=WETH;paid=payout(WETH);}
  }
'''
    s=s[:a]+branch+s[b:]
    constants=''.join(' address constant '+name+'=address(bytes20(hex"'+addr[2:]+'"));\n' for name,addr in [('CRVUSD',CRVUSD),('DIRECT',DIRECT),('TRI',TRI)])
    s=s.replace(' bool busy;',constants+' bool busy;',1)
    old='Wrapped(WETH).withdraw(n);(bool ok,)=BENEFICIARY.call{value:n}("");'
    new='Wrapped(WETH).withdraw(n);uint bid=producerPayment;if(n<=bid)revert CashShortfall(n,bid);producerPayment=0;if(bid>0){(bool sent,)=block.coinbase.call{value:bid}("");require(sent,"producer payment");n-=bid;}(bool ok,)=BENEFICIARY.call{value:n}("");'
    assert s.count(old)==1;s=s.replace(old,new)
    s=s.replace('require(msg.sender==BENEFICIARY,"matrix caller");','require(msg.sender==BENEFICIARY||msg.sender==address(this),"matrix caller");')
    end='''
 function checkHeader(uint number,uint stamp,uint base) internal view {require(block.chainid==1&&block.number==number&&block.timestamp==stamp&&block.basefee==base,"header mismatch");require(BENEFICIARY.balance==0&&address(this).balance==0&&balance(WETH)==0&&balance(STETH)==0&&balance(USDC)==0&&balance(USDT)==0&&balance(CRVUSD)==0,"initial balance");}
 function checkedExecute(Job calldata j,uint number,uint stamp,uint base,uint bid) external returns(address,uint){require(msg.sender==BENEFICIARY&&j.kind==1,"checked caller/kind");checkHeader(number,stamp,base);producerPayment=bid;(address t,uint n)=this.execute(j);require(producerPayment==0&&balance(CRVUSD)==0,"terminal obligations");return(t,n);}
 function checkedMatrix(Job[] calldata js,uint number,uint stamp,uint base) external returns(Result[] memory){require(msg.sender==BENEFICIARY,"matrix checked caller");checkHeader(number,stamp,base);require(producerPayment==0,"matrix bid");Result[] memory r=this.matrix(js);checkHeader(number,stamp,base);return r;}
'''
    return s.rstrip()[:-1]+end+'}\n'
