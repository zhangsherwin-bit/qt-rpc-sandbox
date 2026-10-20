# QT Programme III — Stage 1 restart readiness (2026-10-19)

**Status: offline preparation READY; authenticated research traffic PAUSED pending provider-account-use clarification.** An active API key is verified; that is not proof of permission to use a second free account to circumvent plan limits. The provider's [Terms of Service §5(e)](https://blockmachine.io/terms) prohibit circumventing free-plan limits. If the new free account was opened to replace an almost-spent free allocation, seek Blockmachine approval or upgrade an eligible account before consuming its RU for research.

## Infrastructure: verified

- Current key **status only**: HTTP200, active, 300 RU/min, 10,000 RU remaining, not exhausted (GitHub Actions status read 2026-10-19; no authenticated blockchain RPC in this verification).
- Fix for the old 403: standard Python `requests` instead of old `urllib`; never assert the HTTP403 itself proved an inactive subscription. The exact older Cloudflare 1010 and previously successful `requests` Colab preflight are preserved in QT research.
- Shared client under PR [#84](https://github.com/zhangsherwin-bit/qt-rpc-sandbox/pull/84): requests-based status and RPC, no signing/broadcast methods, original response audits, method-weighted limit, bounded retries, zero retry after account/WAF denial, explicit RU opt-in, **1,500 RU floor** and **500 RU per-run ceiling** on eligible approved usage.
- The same audited client and offline test suite are synced into PR [#81](https://github.com/zhangsherwin-bit/qt-rpc-sandbox/pull/81) and PR [#82](https://github.com/zhangsherwin-bit/qt-rpc-sandbox/pull/82).
- PR CI on #81/#82 now performs **offline checks only**. The experimental jobs are skipped on pull-request updates; historical RPC usage requires a future explicit manual dispatch with separate flags.
- The research branches remain draft, isolated from `main`. PR #83's non-RPC read-only Polymarket historical result remains preserved.

## Current frozen economics (none is realised QT trading P&L)

1. **Specialised cash-close liquidations**: two separate selected historical EVM counterfactual net payouts of +663.935004 and +446.031069 USDC under the original stated costs. Candidate for Stage 2 *shadow engineering*, not live trading or repeatable income.
2. **Morpho yoUSD third-party liquidation**: +190.689127 USDC pre-gas selected historical event; sparse recurrence, own atomic fork incomplete.
3. **Beefy service caller payout**: corrected recovery artifact 2026-10-19: 123 fee logs from 113 distinct Ethereum transactions in five sampled windows; Base one event in five windows. Observed original-caller cash/fees do not demonstrate outsider winning repeatedly.
4. **Frax/Curve issuer-cash**: complete 16 finite quotes at four frozen blocks, 13 gross-negative and 3 gross-positive; +0.204828 USDC at 5,000 USDC is not fully fundable by issuer cash at that block; two smaller positives are pre-gas/unexecuted.
5. **Polymarket binary complete sets**: 40 matched finite-depth quotes, zero gross-positive in selected markets.

The newest register is the earlier `QT_Stage1_Opportunity_Register_20261019_PR83.csv`, 50 unique entries; S1-47 and S1-48 require **versioned evidence amendments** for the recovered RPC tests, while all other rows remain intact. Do not reintroduce the earlier invalid GHO share-price arbitrage.

## Execution gates BEFORE broader Stage 1

1. Provider use rights established for the new account (or compliant paid account). **Do not auto-enable authenticated RU from secret presence alone.**
2. After user permission, run one authenticated, read-only chain-ID/archive-block smoke (<10 estimated RU), check remaining balance, source and chain ID.
3. Run a predeclared, bounded **first new-mechanism batch up to 500 RU** against genuine new economic sources, with an external market/source baseline and a locked holdout period. Stop on 401/403/429, depleted budget, missing receipt or ineligible caller.
4. Proceed to a second batch only if evidence changed expected profitability/capture. Keep a 1,500-RU emergency reserve, 165 RU/minute conservative target (55% of 300). Actual provider per-method costs may vary; the internal method scheduler intentionally overbudgets some operations.
5. Stage 2 shadow research operates in parallel for already observed liquidation mechanisms; no wallet, signing, assets or live orders.

## Innovation mandate for next tranche

Allocate most analytic work to independent novel value transfers, not repeated wrappers. Explore **(A)** residual rights/fee-refund and expired-auction value transfers, **(B)** deterministic time/expiry service bounties with accessible execution windows, **(C)** legacy-to-replacement collateral claims with real finite issuer liquidity, **(D)** constrained settlement/netting across genuinely independent cash liabilities, and **(E)** contractual protection/option exercise incentives under path-dependence. These are *untested research theses* until contract rights, inventory, conversions, terminal cash, costs, recurrence and competitor capture are demonstrated. Do not relabel any as profitable merely because proposed.

## Stop conditions

No empirically verified cash, or provider/legal restrictions, or blocked receipt/archive state, means **UNRESOLVED / DOWNGRADE** not zero profit. An overlapping transaction never counts twice in expected portfolio income. Quotes and original third-party income are separate from our own simulated net and from real income. Stage 1 stays OPEN and Stage 2 does not mean deploy.
