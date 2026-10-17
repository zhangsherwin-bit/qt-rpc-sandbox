"""Deterministic execution extension, recorded before simulations.
Adds actual stable reward -> WETH sale at Uniswap V3 fee500, never a price mark.
Keeper native cash route is the preferred full-payout control; stable and native raw
integers are NOT ranked against one another. Full compiled source is archived.
"""
from pathlib import Path
import subprocess,sys
p=Path('angles_probe/execute.py');s=p.read_text()
old=" (OUT/'CashProbe.sol').write_text(s)"
assert s.count(old)==1
extension='if(j.mode==1){uint n=balance(c);approve(c,ROUTER,n);Router(ROUTER).exactInputSingle(Router.ExactInputSingleParams(c,WETH,500,address(this),block.timestamp,n,0,0));require(balance(c)==0,"stable residue");token=WETH;paid=payout(WETH);}else{token=c;paid=payout(c);}'
patch=" assert s.count('token=c;paid=payout(c);')==1\n s=s.replace('token=c;paid=payout(c);',"+repr(extension)+")\n"+old
s=s.replace(old,patch)
old="    if item['family']=='liquity' and target!=C.TMS[0]:jobs.append((2,target,ids,0,1,b''))"
assert s.count(old)==1
s=s.replace(old,old+"\n    if item['family']=='keeper':jobs.append((1,target,[],0,1,b''))")
old="     best=max(positive,key=lambda x:int(x[1]['cash_raw']))[0]"
assert s.count(old)==2
new="     eligible=([x for x in positive if x[0][4]==1] or positive) if item['family']=='keeper' else positive\n     best=max(eligible,key=lambda x:int(x[1]['cash_raw']))[0]"
s=s.replace(old,new,1)
Path('angles_probe/complete_driver.py').write_text(s)
subprocess.run([sys.executable,'-m','py_compile','angles_probe/complete_driver.py'],check=True)
subprocess.run([sys.executable,'angles_probe/complete_driver.py'],check=True)
