# Stage 1 resumed data collection — PoolTogether original unconsumed evidence gate

The original 2026-10-19 PR93 empirical job never started because its offline script shadowed a crypto hash module (`keccak`). Its original numeric results are therefore **MISSING**, not negative.

This separate read-only branch reuses the corrected source code and the same **predeclared relative-window selection**, Ethereum and Base deployed contracts, five noncontiguous historical 4,000-block windows per chain, first seven distinct withdrawals per chain and first two claim-fee schedule predecessor states. The absolute end blocks are determined at this recovery run's pinned head and may differ from the unexecuted original run; don't label them identical frozen blocks.

Accounts: no user prize ownership, no ticket purchases, no claims submitted. Tests are historical logs, receipt ERC20 cash withdrawals and read-only VRGDA fee quoting; no on-chain trades. A claim credited to a fee-recipient account does not equal terminal token cash and prior prize ownership is not assumed. Conversion to native ETH or USD, prewinner observation and outsider capture are untested.

The research code now exits **nonzero** if canonical pin, any historical log window, selected receipt, or chosen fee quote remains unverified. The artifact is still archived for partial inspection. Never claim no profit if its windows were missing.

**Spending:** authenticated historical RPC only after offline tests on PR creation; maximum 365 conservatively estimated RU and 1,500 monthly reserve, 55% rate throttle from status. No actions on synchronize consume authenticated RU. The account-use permission was confirmed earlier; there are no orders, secrets in artifacts, signatures, funds, live claims, or merged PRs.

This is a new read-only empirical run, not a Stage 2 promotion.
