# QT Programme III — value rights and retained cash, 2026-10-20

This research deliberately changes the *representation* of an opportunity. It is not simply another swap-graph or keeper-reward census. An action requires an actual legitimate entitlement, a public observation, a time window, an owner or approved operator, spendable capital and a terminal cash payoff. It may also require a costly inclusion bid. An owner-only redemption held by another account is not our bounty.

## Offline Convex source-based reanalysis (zero RU)

Original authorised archive: `QT_Convex_UMA_incomplete_20261019.zip` with SHA256 `3d5dd9777ab1636b7d95a0a56546ff7ebee2bab118377539045193acd0d9e794`. All 44 Ethereum JSON-RPC request and response pairs match stored SHA256 (88 hash checks). The four historical 7000-block outgoing Convex Booster CRV windows have 4025 unique Transfer logs. Source `Booster._earmarkRewards` sends up to five distinguishable CRV transfers per call; **all 805 observed transfer groups contain exactly the same three position-pinned protocol recipients and independent caller/LP recipients**. Thus 4025 raw transfers are **805 paid operations**, grouped into **390 onchain transactions**.

Transactions with 1,2,3,4,5,6 reward operations: **159,107,77,37,7,3**. This means **231/390 (59.2%)** already batch at least two harvests. Batching Convex itself is not novel.

**Market segmentation discovered after inspecting outcomes**: 15 caller-reward-recipient addresses; top two by activity take **714/805 (88.7%)** reward payments but only **214.587516760053504184 CRV of total 2660.640290556904423926 CRV (8.07%)**. Median caller payment **0.192472520022940144 CRV**. **14 payouts >=50 CRV** all came from **single-harvest** original transactions. Those threshold comparisons are post hoc; not prospective alpha or a rigorously estimated event hazard. Most frequent caller is not the highest gross reward claimant. The rarer high-value cases may also face stronger competition, as PR95 demonstrated on the **78-CRV** historical original executor (98.93% converted ETH paid to block fee recipient). Do not extrapolate PR95's payout ratio to other jobs.

## New empirical test: controlled LARGE-payment retention, not another sweep

Frozen **after exploratory archive screening** (not holdout):

- Original tx 0x80040416b1d01c1349eb5fcbade8351bfbfdb1709f208dba46f096ef1207499d, Ethereum block 26133003, original *caller recipient* 0x96e0b3b687f71b7de00dd4641c35f6f1b50fb1d1, 385.298381897244354451 CRV.
- Original tx 0x51a17bdcc45b22f058fea4a6a34b70219c429243182a2a1f1039be9b06c92795, block 25945376, second distinct recipient 0x229965b0ee9ed33450317e6725edec3909dcd340, 164.154511351069237764 CRV.

Script reads only exact Ethereum tx/receipt, canonical header, two balance deltas and, where supported, a callTracer. It checks the original CRV payout by amount and recipient, token net balances for the actual executing/supposed beneficiary accounts, gas, block fee-recipient cash transfers and ETH balance reconciliation.

**No conversion / PnL is fabricated.** If the recipient kept CRV or WETH rather than final ETH, it is not automatically spendable ETH. If recipient and tx sender differ, their cash or costs cannot simply be merged as QT profit. A block-end balance mismatch might reflect another same-block event; it is not automatically a bribe. Past execution does not prove public prewinner access or a strategy for nonprivileged outsiders.

**RU/permission:** explicit user permission already provided; only existing Blockmachine allowance. <=**115** conservative RU, >=**1,500** RU protected reserve, provider 300 RU/min with shared 55% limiter from `qt_rpc`. Never use private keys, funds, owner-only calls, sign, broadcast, subscribe to paid APIs or bypass 403/429. Empirical job **only once at initial pull-request opening**, later updates offline only, raw RPC request/response SHA retained by transport. No merge into `main`.

## New transferable concept / next tests

Crosschain settlement and async vault claims are **time-and-rights** problems, not merely swap rates: ERC-7540 requires claim/controller rights, ERC-7683 represents crosschain origin/destination fill conditions, and Across relayers finance destination fills then await refund. A true combo must satisfy prerequisites, avoid double using a single right, and outperform the best independently feasible route after producer bids, failure rates and capital carry. Colliding rights are not additive. Flash credit does not finance delayed settlement.

This PR tests the previously missing **retained** side first. The fuller offline rights/time/bundle modeling laboratory and reproducible 805-group audit are provided separately in the QT Stage1 ValueRights artifact; no numerical hypothetical result from that lab is evidence of true onchain profit.

Sources:
- https://github.com/convex-eth/platform/blob/main/contracts/contracts/Booster.sol
- https://eips.ethereum.org/EIPS/eip-7540
- https://www.erc7683.org/spec
- https://docs.across.to/introduction/fees
- QT corrected native fee-recipient forensic PR #95
