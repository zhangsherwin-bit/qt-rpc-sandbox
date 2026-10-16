"""Resume only unfinished historical tests after the documented HTTP429 reset.
The prior run stopped immediately on HTTP429 with retry_after_ms=13000.
This job runs later, keeps the same endpoint/no credentials, and waits at least
65 seconds with no RPC traffic before each simulation. It still stops on 401/403/429.
No event selection, economic amounts or production state are changed.
"""
from pathlib import Path
import hashlib,json,time,sys
p=Path(__file__).with_name('run.py');src=p.read_text();original_sha=hashlib.sha256(src.encode()).hexdigest()
changes=[
 ('time.monotonic()-BEG>720','time.monotonic()-BEG>1020'),
 ('    for label,ex,fraction in routes:',"    if i==0:routes=[z for z in routes if z[1]==USTB]  # Prior two case-zero simulations are preserved in the first artifact.\n    for label,ex,fraction in routes:")
]
for old,new in changes:
 if src.count(old)!=1:raise RuntimeError('unexpected source revision; not patching')
 src=src.replace(old,new)
out=Path('evidence');out.mkdir(exist_ok=True)
(out/'run_before_continuation.py').write_text(p.read_text());p.write_text(src)
import run
original_rpc=run.rpc
pacing=[]
def paced_rpc(name,method,params,cost=1):
 if method=='eth_simulateV1':
  delay=max(0,65-(time.monotonic()-run.LAST))
  pacing.append({'name':name,'quiet_wait_seconds':delay,'started_utc':run.utc()});time.sleep(delay)
 return original_rpc(name,method,params,cost)
run.rpc=paced_rpc
run.main()
summary=json.loads((out/'SUMMARY.json').read_text());summary['continuation']={'previous_artifact_sha256':'cf6a7a2f3f3e933cb26840fcdbd6d93e8a4dfc7c31ab3b4be72362fa40109645','reason':'prior HTTP429 minute-rate reset, not authentication denial','original_source_sha256':original_sha,'patched_source_sha256':hashlib.sha256(src.encode()).hexdigest(),'completed_case_zero_variants_skipped':['frx_all_LP','usdc_custodian_all_LP'],'minimum_silent_interval_before_each_simulation_seconds':65,'pacing':pacing}
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2))
