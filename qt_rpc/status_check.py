"""One-shot, read-only Blockmachine key-status diagnostic.

Use the standard requests client, as in the verified 2026-10-11 Colab
HTTP-client repair. HTTP403 alone is ambiguous: it may be a Cloudflare
Error 1010 HTML denial or an origin-generated account-status response.
NO blockchain RPC, redirect, retry, raw body, credential or account ID logged.
"""
import json
import os
import re
import sys

STATUS = "https://blockmachine.io/user-management-api/api-keys/self/status"

def classify(response):
    status = int(response.status_code)
    server = str(response.headers.get("Server", "")).lower()
    text = response.text[:4096]
    cf_1010 = bool(re.search(r"(?:error\s*code[:\s]+|error\s+)1010\b", text, re.I))
    cf_block = bool(re.search(r"(?:error\s*code[:\s]+|error\s+)(?:1020|1006|1007|1008|1106)\b", text, re.I))
    if status == 200:
        try:
            obj = response.json()
        except (ValueError, TypeError):
            return {"status":"UNVERIFIED", "kind":"MALFORMED_200_JSON","http_status":200}
        if not isinstance(obj, dict) or obj.get("status") != "active":
            return {"status":"UNVERIFIED","kind":"STATUS_NOT_ACTIVE_OR_INVALID","http_status":200}
        return {
            "status": "VERIFIED", "kind":"ACTIVE_KEY",
            "http_status":200, "auth":"authenticated",
            "rate_limit_rpm":obj.get("rate_limit_rpm"),
            "ru_budget":obj.get("ru_budget"),
            "ru_remaining":obj.get("ru_remaining"),
            "is_exhausted":obj.get("is_exhausted"),
        }
    result={"status":"UNVERIFIED","http_status":status}
    if cf_1010:
        result["kind"]="CLOUDFLARE_1010_CLIENT_SIGNATURE_DENIAL"
    elif cf_block:
        result["kind"]="CLOUDFLARE_ACCESS_RULE_DENIAL"
    elif status == 401:
        result["kind"]="STATUS_API_401"
    elif status == 403:
        result["kind"]="STATUS_API_403_OR_UNCLASSIFIED_WAF"
    elif status == 429:
        result["kind"]="STATUS_API_RATE_LIMIT"
    else:
        result["kind"]="OTHER_HTTP_STATUS"
    result["server_class"]="cloudflare" if "cloudflare" in server else "other_or_unknown"
    ray=str(response.headers.get("CF-Ray", ""))
    if re.fullmatch(r"[0-9a-fA-F]{12,24}-[A-Z]{3}",ray):
        result["cf_ray"]=ray
    return result

def main():
    key=os.environ.get("BLOCKMACHINE_API_KEY","").strip()
    if not key:
        print(json.dumps({"status":"UNVERIFIED","kind":"NO_GITHUB_SECRET_CONFIGURED",
                          "key_configured":False},sort_keys=True))
        return 0
    # This check is solely for key metadata, never an authenticated chain RPC.
    try:
        import requests
        response=requests.get(
            STATUS, headers={"Authorization":"Bearer "+key,
                             "Accept":"application/json"},
            timeout=(10,20),allow_redirects=False)
        report=classify(response)
    except Exception as exc:
        # Do not print exc / URL / traceback: upstream errors may contain secrets.
        report={"status":"UNVERIFIED","kind":"TRANSPORT_"+type(exc).__name__}
    report["key_configured"]=True
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="VERIFIED" else 2

if __name__=="__main__":
    sys.exit(main())
