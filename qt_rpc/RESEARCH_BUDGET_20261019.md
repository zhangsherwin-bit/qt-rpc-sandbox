# Programme III — 2026-10-19 archive RU capacity gate

User-provided planned capacity: **10,000 RU period budget and 300 RU/minute** on a newly configured GitHub Actions key. These are user-reported and must be verified with the **read-only** Blockmachine `/api-keys/self/status` response. This file does not authorize actual authenticated RPC usage.

## Research spending guard

- The hourly/minute rate is not the monthly allowance. Conservatively target <=165 RU/minute (55% reported limit), shared across Ethereum, Base and other supported chains; stop when provider says no.
- Keep a 1,500-RU reserve until the next deliberate funding decision.
- Predefine expensive tests, not broad blind scans: independent discovery and cheap falsification first; accurate funded route and competition tests second; fork execution third.
- Cap any explicitly approved campaign to 500 RU per stage; recheck status after each stage and stop if less than 1,500 RU remains. **Never** assume 300 RU/min implies unlimited RU.
- Automated spending remains disabled: `QT_ALLOW_AUTHENTICATED_RPC` is unset in all experiment workflows and the shared client fails closed.
- No wallet use, transaction signing, workaround via additional free accounts, or spending without a user-approved compliant account.

## Provider terms issue

The user reported opening another free account when the original free plan had 978 RU left. Blockmachine Terms of Service §5(e) prohibit circumventing free-plan limits. Do not use a second free account to extend a single user's free allocation if that violates the provider's terms. Options: obtain written confirmation from Blockmachine that this account is permitted, or activate the published $9 Standard plan on an appropriate account. A metadata-only credential status check is not a trading or historical archive RPC request.

## Current pipeline

PR #84: shared transport, tests, budget cap. PRs #81 and #82: experimental replay clients. They remain draft, with older defaults protecting the authenticated RU by opt-in. Nothing has been merged to main. Read-only credential status may be checked without spending the monthly archive-RPC allowance.

Sources:
- https://blockmachine.io/terms
- https://blockmachine.io/docs/ai-agents
- https://blockmachine.io/docs/rpc
