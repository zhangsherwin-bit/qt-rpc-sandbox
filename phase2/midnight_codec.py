"""Bounded ABI codec. No signing. Layout: Midnight 581aa26b445a52cf131858da200eb0f825aee89e.
Uses pycryptodome Keccak, cross-checked against eth-abi in offline tests.
"""
from Crypto.Hash import keccak

def keccak256(data):
    h=keccak.new(digest_bits=256);h.update(data);return h.digest()
def selector(signature):return '0x'+keccak256(signature.encode())[:4].hex()
CORE='0xAdedD8ab6dE832766Fedf0FaC4992E5C4D3EA18A'
USDC='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
ZERO='0x'+'00'*20
PROBE='0x'+'00'*17+'a71501'
CALLER='0x'+'00'*17+'a71502'
MARKET='(uint256,address,address,(address,uint256,uint256,address)[],uint256,uint256,address,address)'
OFFER='('+MARKET+',bool,address,uint256,uint256,uint256,bytes32,address,bytes,address,address,bool,uint128,uint128,uint256)'
def word(n):
    if isinstance(n,str):n=int(n,16) if n.startswith('0x') else int(n)
    if not isinstance(n,int) or not 0<=n<2**256:raise ValueError('not uint256')
    return n.to_bytes(32,'big')
def addr(s):
    if not isinstance(s,str) or len(s)!=42 or not s.startswith('0x'):raise ValueError('bad address')
    return bytes(12)+bytes.fromhex(s[2:])
def h32(s):
    if not isinstance(s,str) or len(s)!=66 or not s.startswith('0x'):raise ValueError('bad bytes32')
    return bytes.fromhex(s[2:])
def bhex(s):
    if not isinstance(s,str) or not s.startswith('0x'):raise ValueError('bad hex')
    return bytes.fromhex(s[2:])
def dyn_bytes(b):return word(len(b))+b+bytes((-len(b))%32)
def tuple_body(parts):
    n=32*len(parts);head=[];tail=[]
    for dynamic,b in parts:
        if dynamic:head.append(word(n));tail.append(b);n+=len(b)
        else:
            if len(b)!=32:raise ValueError('static field not word')
            head.append(b)
    return b''.join(head+tail)
def market_body(m,core=CORE):
    if m.get('midnight',core).lower()!=core.lower():raise ValueError('core mismatch')
    coll=m.get('collaterals',m.get('collateral_params'))
    if not isinstance(coll,list) or not 1<=len(coll)<=128:raise ValueError('invalid collateral list')
    cs=word(len(coll))+b''.join(addr(c['token'])+word(c['lltv'])+word(c['liquidation_cursor'])+addr(c['oracle']) for c in coll)
    return tuple_body([(False,word(m['chain_id'])),(False,addr(core)),(False,addr(m['loan_token'])),(True,cs),(False,word(m['maturity'])),(False,word(m['rcf_threshold'])),(False,addr(m['enter_gate'])),(False,addr(m['liquidator_gate']))])
def market_id(m,core=CORE):
    creation=bytes.fromhex('600b380380600b5f395ff3')+word(32)+market_body(m,core)
    return '0x'+keccak256(b'\xff'+bhex(core)+bytes(32)+keccak256(creation)).hex()
def offer_body(o):
    if not isinstance(o['buy'],bool) or not isinstance(o['reduce_only'],bool):raise ValueError('invalid bool')
    for k in ('max_units','max_assets'):
        if not 0<=int(o[k])<2**128:raise ValueError('cap overflow')
    return tuple_body([(True,market_body(o['market'])),(False,word(int(o['buy']))),(False,addr(o['maker'])),(False,word(o['start'])),(False,word(o['expiry'])),(False,word(o['tick'])),(False,h32(o['group'])),(False,addr(o['callback'])),(True,dyn_bytes(bhex(o['callback_data']))),(False,addr(o['receiver_if_maker_is_seller'])),(False,addr(o['ratifier'])),(False,word(int(o['reduce_only']))),(False,word(o['max_units'])),(False,word(o['max_assets'])),(False,word(o['continuous_fee_cap']))])
def run_take(o,ratifier_data,units):
    return selector('runTake('+OFFER+',bytes,uint256)')+tuple_body([(True,offer_body(o)),(True,dyn_bytes(bhex(ratifier_data))),(False,word(units))]).hex()
def run_liquidation(m,index,borrower,seized,repaid,post):
    return selector('runCashLiquidation('+MARKET+',uint256,address,uint256,uint256,bool)')+tuple_body([(True,market_body(m)),(False,word(index)),(False,addr(borrower)),(False,word(seized)),(False,word(repaid)),(False,word(int(post)))]).hex()
def view_data(signature,*values):
    return selector(signature)+b''.join(addr(v) if isinstance(v,str) and len(v)==42 else h32(v) if isinstance(v,str) and len(v)==66 else word(v) for v in values).hex()
def decode_words(result):
    b=bhex(result)
    if len(b)%32:raise ValueError('unaligned result')
    return [int.from_bytes(b[i:i+32],'big') for i in range(0,len(b),32)]
