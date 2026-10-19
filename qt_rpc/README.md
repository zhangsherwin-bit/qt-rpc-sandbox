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
