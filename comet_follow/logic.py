"""Pure controls for a fixed, lawful Comet liquidation-and-purchase experiment."""
import hashlib
from collections import Counter
SOURCE_SHA='b2f0e942b4a8edbb0c3662cd06e5d7eb7a06e1c1af11a3034742dcc142db0169'
BORROWER='0xc3a6203a618438e206c9d1da2ac0dba6f36fcffd'

def add_absorption(source):
    if hashlib.sha256(source.encode()).hexdigest()!=SOURCE_SHA:
        raise ValueError('Unexpected original source; do not apply a guessed patch')
    old='interface IComet {\n'
    new=old+'    function isLiquidatable(address account) external view returns (bool);\n    function absorb(address absorber, address[] calldata accounts) external;\n'
    assert source.count(old)==1
    source=source.replace(old,new)
    marker='        uint256 pre=IERC20(USDC).balanceOf(BENEF);\n'
    extra=(marker+'        address borrower=address(uint160('+BORROWER+'));\n'
           '        require(IComet(COMET).isLiquidatable(borrower),"frozen borrower not eligible");\n'
           '        address[] memory accounts=new address[](1);\n'
           '        accounts[0]=borrower;\n'
           '        IComet(COMET).absorb(address(this),accounts);\n')
    # Leading 00 disambiguates a 20-byte lower-case address from an EIP-55 literal.
    extra=extra.replace('uint160('+BORROWER+')','uint160(0x00'+BORROWER[2:]+')')
    assert source.count(marker)==1
    return source.replace(marker,extra)

def as_call(tx):
    call={k:tx[k] for k in ('from','to','gas','value','nonce','accessList','maxFeePerGas','maxPriorityFeePerGas','maxFeePerBlobGas','blobVersionedHashes','authorizationList') if tx.get(k) is not None}
    call['input']=tx.get('input',tx.get('data','0x'))
    if not call.get('maxFeePerGas') and tx.get('gasPrice') is not None:call['gasPrice']=tx['gasPrice']
    return call

def bag(logs):
    return Counter((x['address'].lower(),tuple(t.lower() for t in x['topics']),x.get('data','0x').lower()) for x in logs)

def receipt_matches(call,receipt):
    return call.get('status')==receipt.get('status') and int(call.get('gasUsed','0x0'),16)==int(receipt['gasUsed'],16) and bag(call.get('logs',[]))==bag(receipt['logs'])

def native_delta(trace,account):
    if trace.get('error'):return 0
    typ=trace.get('type','').upper();value=int(trace.get('value','0x0'),16)
    amount=0
    if typ in ('CALL','CREATE','CREATE2','SELFDESTRUCT'):
        amount=(value if trace.get('to','').lower()==account.lower() else 0)-(value if trace.get('from','').lower()==account.lower() else 0)
    return amount+sum(native_delta(x,account) for x in trace.get('calls',[]))

def committed_logs(trace):
    if trace.get('error'):return []
    return trace.get('logs',[])+[l for sub in trace.get('calls',[]) for l in committed_logs(sub)]
