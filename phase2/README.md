# Phase 2 actual-state cash research

Adapted from QT_GitHub_Continuation_20261015's prepared Phase 2 harness. The same pinned Midnight interfaces, exact ABI, same-token liquidation sizes and cash-closure checks are retained. Publication uses a compact test fixture instead of large historical block/code bodies. The original 24 prepared tests were rerun offline before publication; this compact remote suite has 18 methods.

Public read-only calls only. No wallet, signature, trade, state/balance/oracle/timestamp override, or schedule. The only override is the investigator's own probe code at an empty research address; all production state is preserved. Up to 300 requests, 12 comparable listed Base USDC markets and 32 discovered borrowers per market. API selection and RPC state are not atomic. No write RPC methods exist.

Compilation is an explicit gate. Core runtime must match the earlier observed fingerprint. Environmental echo must match chain, block and time. Source equivalence of the core is not established by a fingerprint alone. Missing data and reverting supported routes are not global rejections. No newly realised bad debt is supported. Fixed cohort limits are reported.

`public_*/SUMMARY.json` and `public_*/raw/` contain full partial or complete evidence. Positive probes are USDC after contract repayment but before complete gas, L1, deployment, failed attempts or inclusion payments. Independent reset-state probes must not be summed as jointly executable profit.
