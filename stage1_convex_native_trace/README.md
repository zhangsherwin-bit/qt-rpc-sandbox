# QT Stage 1 — separate token revenue from spendable ETH

A deterministic, forensic continuation of the 2026-10-19 PR91 earliest-12 transaction. No new opportunity was selected based on favorable outcome.

### Frozen relevant evidence

Transaction 0x211f62115ec9c55f349b6fdd100f6e0c7bd6a45baad70f5e9340f8f64150db4f, Ethereum block 25,941,501, had:

- **78.011436090499686987 CRV** received from Booster.
- Same amount sent into a Uniswap v3 pool, with **0.011379084255985277 WETH** received.
- Same WETH amount unwrapped to native ETH.
- Actual gas cost **0.000052618514415240 ETH**.
- But independent historic archive eth_getBalance at parent/child showed **only 0.000069675416337178 ETH native account increase**. This is much smaller than WETH received minus gas.

The original attempt PR94 used rounded hardcoded wei and therefore also signaled a token mismatch; the exact wei inputs have been corrected without re-executing any authenticated read. The unexplained native outflow, approximately **0.011256790325232859 ETH** *if no other tx in that block touched the account*, needs a trace. One plausible but UNVERIFIED explanation is a block-builder payment. Never state this is a bribe until a real beneficiary/value trace supports it.

### Frozen exact-block test

Read-only Blockmachine Ethereum debug_traceTransaction of the **single exact hash** with geth callTracer, documented 25 RU; one read-only chain ID, header, parent/child balance cross-check. Strict **35 RU maximum** across attempts and **1,500 RU monthly account reserve**, abort on 403, 429 after bounded handling, no broader scan. No wallet/broadcast or new calldata execution. Persist raw response and SHA in artifact.

Sum CALL/CREATE native ETH value transfers to and from the historical actor, ignoring DELEGATECALL accounting and self-call. Compare net trace-minus-actual gas to independent native balance delta. If they match, report retained end-of-block ETH change as a historical original sender result (not QT income). If a builder/coinbase destination is observed, classify grounded. If not, label **UNRECONCILED** and withhold profit claims.

Read-only trace is not proof we can win future orderflow. Next validation would be prewinner reward observability, recurring independent opportunities, ability to combine calls, realistic builder competition and actual inclusion (not trading).
