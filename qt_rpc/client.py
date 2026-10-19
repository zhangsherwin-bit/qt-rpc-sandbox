"""QT Stage 1 shared, read-only, quota-aware Blockmachine JSON-RPC client.

Safety: Bearer key is read from environment and never written to disk; never bypass
a provider throttle, never sign/broadcast, and never infer a zero result from denial.
For documented limits: https://blockmachine.io/docs/rpc and /gateway-methods.
"""
from collections import deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

ALLOWED_METHODS = frozenset({
    "eth_chainId", "eth_blockNumber", "eth_getBlockByNumber",
    "eth_getCode", "eth_call", "eth_getLogs", "eth_estimateGas",
    "eth_getTransactionByHash", "eth_getTransactionReceipt",
    "eth_getBalance", "eth_getStorageAt",
})
ENDPOINTS = {
    1: "https://rpc-eth.blockmachine.io",
    8453: "https://rpc-base.blockmachine.io",
}
STATUS_URL = "https://blockmachine.io/user-management-api/api-keys/self/status"


class RPCFailure(RuntimeError):
    def __init__(self, kind, status=None, code=None, detail=""):
        super().__init__(f"{kind}: http={status}, rpc_code={code}, {detail[:180]}")
        self.kind = kind
        self.status = status
        self.code = code


class WeightedLimiter:
    """Rolling 60-second conservative RU allowance, shared across chains."""
    def __init__(self, cap_ru=30, now=None, sleeper=None):
        if not 5 <= cap_ru <= 100000:
            raise ValueError("Invalid RU cap")
        self.cap_ru = float(cap_ru)
        self.now = now or time.monotonic
        self.sleep = sleeper or time.sleep
        self.events = deque()

    def admit(self, weight):
        if weight > self.cap_ru:
            raise RPCFailure("REQUEST_EXCEEDS_SAFE_RU_WINDOW", detail=str(weight))
        while True:
            current = self.now()
            while self.events and current - self.events[0][0] >= 60:
                self.events.popleft()
            used = sum(w for _, w in self.events)
            if used + weight <= self.cap_ru + 1e-8:
                self.events.append((current, weight))
                return
            self.sleep(max(0.05, 60.05 - (current - self.events[0][0])))


def request_units(method, params):
    """Conservative getLogs RU tiers from published gateway reference.
    The Ethereum marketing page sometimes quotes cheaper eth_getLogs; do not
    depend on the cheaper schedule when protecting user RU capacity.
    """
    if method not in ALLOWED_METHODS:
        raise RPCFailure("METHOD_NOT_READ_ONLY_OR_UNSUPPORTED", detail=method)
    if method != "eth_getLogs":
        return 1
    if not params or not isinstance(params[0], dict):
        raise RPCFailure("INVALID_LOG_FILTER")
    f = params[0]
    a, b = f.get("fromBlock"), f.get("toBlock")
    if not (isinstance(a, str) and isinstance(b, str)
            and a.startswith("0x") and b.startswith("0x")):
        raise RPCFailure("EXPLICIT_LOG_RANGE_REQUIRED")
    length = int(b, 16) - int(a, 16) + 1
    if not 1 <= length <= 10000:
        raise RPCFailure("LOG_RANGE_OUT_OF_BOUNDS", detail=str(length))
    if length <= 100:
        return 5
    if length <= 1000:
        return 10
    return 25


def read_key_status(key, opener=None):
    """Validate key with the provider's read-only status API.

    Use the standard requests HTTP client for the deployed client, reproducing
    the previously successful 2026-10-11 transport fix. An explicitly injected
    opener retains the deterministic urllib unit-test path. No retries,
    redirects, logging of token/key_prefix, or key in the request URL.
    """
    if not key:
        return {"auth": "keyless", "rate_limit_rpm": None,
                "ru_remaining": None, "is_exhausted": None}
    headers = {"Authorization": "Bearer " + key, "Accept": "application/json"}
    if opener is None:
        try:
            import requests
            response = requests.get(STATUS_URL, headers=headers,
                                    timeout=(10, 20), allow_redirects=False)
            if response.status_code != 200:
                raise RPCFailure("KEY_STATUS_AUTH_OR_SERVICE_FAILURE",
                                 status=response.status_code)
            obj = response.json()
        except requests.RequestException as exc:
            raise RPCFailure("KEY_STATUS_UNAVAILABLE",
                             detail=type(exc).__name__) from None
        except (ValueError, TypeError) as exc:
            raise RPCFailure("KEY_STATUS_UNAVAILABLE",
                             detail=type(exc).__name__) from None
    else:
        request = urllib.request.Request(
            STATUS_URL, headers=headers, method="GET")
        try:
            with opener(request, timeout=20) as response:
                raw = response.read(50000)
                if response.status != 200:
                    raise RPCFailure("KEY_STATUS_HTTP_ERROR",
                                     status=response.status)
            obj = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise RPCFailure("KEY_STATUS_AUTH_OR_SERVICE_FAILURE",
                             status=exc.code) from None
        except (ValueError, OSError) as exc:
            raise RPCFailure("KEY_STATUS_UNAVAILABLE",
                             detail=type(exc).__name__) from None
    if not isinstance(obj, dict) or obj.get("status") != "active":
        raise RPCFailure("KEY_NOT_ACTIVE_OR_STATUS_INVALID")
    fields = ("rate_limit_rpm", "ru_remaining", "ru_budget", "is_exhausted")
    report = {k: obj.get(k) for k in fields}
    report["auth"] = "authenticated"
    if obj.get("is_exhausted") is True or obj.get("ru_remaining", 0) < 1:
        raise RPCFailure("RU_BUDGET_EXHAUSTED")
    if not isinstance(obj.get("rate_limit_rpm"), (int, float)):
        raise RPCFailure("MISSING_AUTHENTICATED_RU_RATE")
    return report

def parse_retry_seconds(headers, error, now_unix=None):
    now_unix = now_unix if now_unix is not None else time.time()
    vals = []
    if isinstance(error, dict):
        data = error.get("data")
        if isinstance(data, dict):
            n = data.get("retry_after_ms")
            if isinstance(n, (int, float)) and 0 < n <= 300000:
                vals.append(n / 1000)
            reset = data.get("reset")
            if isinstance(reset, (int, float)) and 0 < reset - now_unix <= 300:
                vals.append(reset - now_unix)
    text = headers.get("Retry-After", "") if headers else ""
    if text:
        try:
            secs = float(text)
            if secs > 0:
                vals.append(secs)
        except ValueError:
            try:
                delta = parsedate_to_datetime(text).timestamp() - now_unix
                if delta > 0:
                    vals.append(delta)
            except (TypeError, ValueError, OverflowError):
                pass
    return max(vals) if vals else None



class AuthenticatedBudget:
    """Fail-closed billing-period spending guard.

    An authenticated API key is *not* permission to spend its RU balance.
    A separate QT_ALLOW_AUTHENTICATED_RPC=YES opt-in is required. After opt-in,
    this object prevents the process from spending over a small per-run cap
    or crossing the RU reserve measured at the key-status snapshot.
    Other account consumers can change actual remaining RU independently.
    """
    def __init__(self, status, reserve_floor=1500, max_run_ru=500,
                 approved=None):
        if status.get("auth") != "authenticated":
            raise RPCFailure("AUTHENTICATED_STATUS_REQUIRED")
        if approved is None:
            approved = os.environ.get("QT_ALLOW_AUTHENTICATED_RPC", "") == "YES"
        if not approved:
            raise RPCFailure("AUTHENTICATED_RU_SPENDING_NOT_APPROVED")
        remaining = status.get("ru_remaining")
        if isinstance(remaining, bool) or not isinstance(remaining, (int, float)):
            raise RPCFailure("AUTHENTICATED_REMAINING_RU_UNAVAILABLE")
        if not isinstance(reserve_floor, (int, float)) or reserve_floor < 0:
            raise ValueError("Reserve floor must be non-negative")
        if not isinstance(max_run_ru, (int, float)) or max_run_ru <= 0:
            raise ValueError("Max run RU must be positive")
        self.reserve_floor = float(reserve_floor)
        self.initial_remaining = float(remaining)
        self.cap_ru = min(float(max_run_ru),
                          max(0.0, self.initial_remaining - self.reserve_floor))
        self.attempted_ru = 0.0
        if self.cap_ru < 1:
            raise RPCFailure("MONTHLY_RU_RESERVE_PROTECTED")

    def admit(self, weight):
        if self.attempted_ru + weight > self.cap_ru + 1e-8:
            raise RPCFailure("AUTHENTICATED_RUN_RU_CAP_REACHED",
                             detail="No additional paid-RU call issued")
        # Conservatively count *attempts*, including denied/retried calls.
        self.attempted_ru += weight



class ReadOnlyRPC:
    def __init__(self, chain_id, archive_dir, limiter=None, api_key=None,
                 max_attempts=3, max_requests=125, opener=None,
                 sleeper=None, now_unix=None, status=None, budget=None):
        if chain_id not in ENDPOINTS:
            raise ValueError("Unsupported chain")
        self.chain_id = chain_id
        self.endpoint = ENDPOINTS[chain_id]
        self.key = os.environ.get("BLOCKMACHINE_API_KEY", "").strip() if api_key is None else api_key.strip()
        self.status = status if status is not None else read_key_status(self.key, opener=opener)
        if self.key and self.status.get("auth") != "authenticated":
            raise RPCFailure("KEY_STATUS_REQUIRED", detail="Refusing silent free-tier fallback")
        self.budget = None
        if self.key:
            self.budget = budget if budget is not None else AuthenticatedBudget(
                self.status)

        limit = self.status.get("rate_limit_rpm") if self.key else 60
        # Leave capacity for other users of this global account/key/IP.
        cap = int(float(limit) * 0.55) if limit else 30
        cap = max(5, cap)
        self.limiter = limiter or WeightedLimiter(cap_ru=cap, sleeper=sleeper)
        self.max_attempts = max(1, min(4, max_attempts))
        self.max_requests = max_requests
        self.opener = opener or urllib.request.urlopen
        self.sleep = sleeper or time.sleep
        self.now_unix = now_unix or time.time
        self.archive = Path(archive_dir)
        self.archive.mkdir(parents=True, exist_ok=True)
        self.attempted = 0
        self.logs = []
        self.aborted = False

    def _archive(self, body, raw, status, code, method, attempt, retry):
        idx = self.attempted
        basename = f"{idx:04d}"
        # Never store Authorization headers, key, or URLs containing credentials.
        raw = raw.replace(self.key.encode(), b"[REDACTED]") if self.key else raw
        (self.archive / (basename + ".req.json")).write_bytes(body)
        (self.archive / (basename + ".response")).write_bytes(raw)
        rec = {
            "seq": idx, "method": method, "chain_id": self.chain_id,
            "http_status": status, "rpc_code": code, "attempt": attempt,
            "request_sha256": hashlib.sha256(body).hexdigest(),
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "retry_sleep_s": retry, "response_bytes": len(raw),
        }
        self.logs.append(rec)
        (self.archive / "REQUEST_INDEX.json").write_text(
            json.dumps(self.logs, indent=2) + "\n", encoding="utf8")

    def rpc(self, method, params):
        if self.aborted:
            raise RPCFailure("CIRCUIT_OPEN")
        units = request_units(method, params)
        if self.attempted >= self.max_requests:
            raise RPCFailure("FIXED_HTTP_ATTEMPT_LIMIT")
        request_body = json.dumps({
            "jsonrpc": "2.0", "method": method,
            "params": params, "id": self.attempted + 1},
            sort_keys=True, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json",
                   "User-Agent": "QT-Stage1-ReadOnly-Research/2"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        for attempt in range(1, self.max_attempts + 1):
            if self.attempted >= self.max_requests:
                raise RPCFailure("FIXED_HTTP_ATTEMPT_LIMIT")
            if self.budget is not None:
                self.budget.admit(units)
            self.limiter.admit(units)
            self.attempted += 1
            status = -1
            raw = b""
            resp_headers = {}
            try:
                req = urllib.request.Request(
                    self.endpoint, data=request_body, headers=headers, method="POST")
                with self.opener(req, timeout=35) as response:
                    status = response.status
                    raw = response.read(2500000)
                    resp_headers = response.headers
            except urllib.error.HTTPError as exc:
                status = exc.code
                raw = exc.read(2500000)
                resp_headers = exc.headers
            except (OSError, TimeoutError) as exc:
                raw = json.dumps({"transport_error": type(exc).__name__}).encode()
            try:
                result = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                result = {}
            error = result.get("error") if isinstance(result, dict) else None
            code = error.get("code") if isinstance(error, dict) else None
            transient = status in (429, 502, 503, 504) or code in (-32029, -32031, -32011)
            terminal = status in (401, 403) or code in (-32021, -32030)
            if terminal:
                kind = "RU_BUDGET_EXHAUSTED" if code == -32030 else "AUTH_OR_ACCESS_DENIED"
                self.aborted = True
            elif status == 200 and isinstance(result, dict) and "result" in result:
                self._archive(request_body, raw, status, code, method, attempt, 0)
                return result["result"]
            else:
                kind = "TRANSIENT_THROTTLE" if transient else "RPC_RESPONSE_ERROR"
            retry = 0
            if transient and not terminal and attempt < self.max_attempts:
                proposed = parse_retry_seconds(resp_headers, error, now_unix=self.now_unix())
                retry = min(80.0, max(1.0, proposed if proposed else 8 * (2 ** (attempt - 1))) + 0.4)
            self._archive(request_body, raw, status, code, method, attempt, retry)
            if retry:
                self.sleep(retry)
                continue
            # Repeated limit failure is a stop, not permission to rotate endpoints.
            if transient or terminal:
                self.aborted = True
            raise RPCFailure(kind, status=status, code=code)
        raise RPCFailure("RETRY_LIMIT_EXHAUSTED")
