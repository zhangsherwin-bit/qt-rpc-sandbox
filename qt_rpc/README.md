# QT Stage 1: Blockmachine RPC restoration, 19 October 2026

Verified original Frax RPC response #062: HTTP429 with JSON-RPC code -32029, limit 60 CU/min and retry_after_ms 6000. Its old script never sent a credential. Beefy Base public log query returned HTTP429 code -32011. Neither error means the key exhausted its monthly RU allocation.

Use official Blockmachine Ethereum and Base endpoints. A GitHub Actions repository secret named BLOCKMACHINE_API_KEY supplies the credential. It is never committed, printed, sent in a URL, or stored in evidence. Rotate old keys that were ever pasted into a conversation.

Authenticated jobs may check the read-only key status endpoint, verify active status and current RU cap/remaining, then throttle shared ETH+Base calls to a conservative 55% of rate_limit_rpm. Without any key they fall back to a very conservative portion of the 60 RU/min keyless tier. A provider code -32030 stops the run, not a retry or fallback.

Published getLogs cost reference: 5 RU for <=100 blocks, 10 RU for <=1000, 25 RU for <=10000. All log block ranges must be <=10000. Others in the allowlisted method set count one RU. With failures -32029/-32011, read retry_after_ms, reset or Retry-After, make at most three attempts, and preserve raw request/responses and SHA hashes. 401/403, -32021, -32030 are terminal. The actual cost can depend on current vendor policy; lower documented rates are not assumed.

No trade, signing, secret leak, proxy, bypass, branch merge, or unjustified claim of profit. Research provider recovery is separate from proving profitability. For large datasets reuse retained archives or negotiate documented data throughput.

Sources: https://blockmachine.io/docs/rpc
https://blockmachine.io/docs/ai-agents
https://blockmachine.io/docs/gateway-methods
https://blockmachine.io/docs/base-rpc
https://status.base.org/

## Low-budget safeguard (978 RU reported 2026-10-19)
**Do not place a fresh authenticated key in active experiment workflows merely to increase speed.**
Even if BLOCKMACHINE_API_KEY is configured, authenticated RPC calls now require a second, explicit environment value `QT_ALLOW_AUTHENTICATED_RPC=YES`; otherwise ReadOnlyRPC stops before the first authenticated blockchain request. A read-only key-status query may still occur to diagnose allowance. This value is deliberately *not* present in GitHub experiment workflows.

Once deliberately enabled, the monthly-account status snapshot must report numerical `ru_remaining`. The default `AuthenticatedBudget` protects a **900 RU floor** and a **50 RU per-process/run cap**, whichever binds first. Client instances operating on multiple chains must share one AuthenticatedBudget; PR81 shares it between ETH and Base. Each attempted RPC counts conservatively, even transient retries. The floor is a snapshot, not a guarantee against third-party usage or independent concurrent consumers of the same key.

For routine innovation-first Stage 1, prefer no key, free public permitted sources, retained historical artifacts, and inexpensive falsification; use authenticated archive RU only for a pre-approved, narrow research question when public historical access is insufficient. Provider documentation says keyless is 60 RU/minute per IP with no monthly cap but **does not guarantee archive access**.
