"""One-shot privacy-safe Blockmachine status preflight (no secret in output)."""
import json
import os
import sys
from qt_rpc.client import RPCFailure, read_key_status

key = os.environ.get("BLOCKMACHINE_API_KEY", "").strip()
if not key:
 print(json.dumps({"auth_mode":"keyless","key_configured":False,
  "anonymous_documented_rate_ru_per_min":60,
  "action":"Set a fresh BLOCKMACHINE_API_KEY GitHub Actions secret for guaranteed archive access."}))
 sys.exit(0)
try:
 result=read_key_status(key)
 safe={name:result.get(name) for name in ("auth","rate_limit_rpm",
                                          "ru_budget","ru_remaining","is_exhausted")}
 safe["key_configured"]=True
 print(json.dumps(safe,sort_keys=True))
except RPCFailure as exc:
 print(json.dumps({"key_configured":True,"status":"NOT_VERIFIED",
                   "error_kind":exc.kind,"http_status":exc.status,
                   "rpc_error_code":exc.code},sort_keys=True))
 sys.exit(2)
