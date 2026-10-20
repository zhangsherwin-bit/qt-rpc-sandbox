# QT Stage 1 — Can complementary insurance/right tokens create overlooked exercise liquidity?

19–20 October 2026 · Innovation-first / source-grounded source-intent screen.

## The economic transformation

Cork Phoenix underwrites a **Reference Asset (REF)** using a Collateral Asset (CA), issuing rights **cPT (principal)** and **cST (swap)**. Its public interface supports e.g. `exercise(marketId, cSTAmount, receiver)` and `exerciseOther` with reference assets. During a legitimate **unexpired, unpaused, eligible** market, cST and REF jointly unlock a particular amount of CA.

A token-only DEX spread finder might overlook the composite entitlement: **cST + REF + execution right => CA minus protocol fee**. Economic payoff requires an executable acquisition for cST, REF, known and bounded market rate, actual finite available collateral and all costs. This is not a free/ownerless redemption. A competent conditional-arbitrage solver with source-specified recipes and permissions would also find any genuine cash-positive route: simpler model wins if equal.

## Participants, alternatives, rights

- A hedger holds cST, wants protection or liquidity now; next best choice is exercise alone, liquidate own position or hold to expiration depending on its situation. A signed OTC sell order can legitimately transfer token rights; do NOT assume transferable permission or available asks.
- Reference-asset holder owns REF and can sell under approved market terms; next best alternative is holding/selling elsewhere.
- CA underwriter/LP has supplied collateral and is paid for absorbing risk; next best alternative is another risk/yield venue. CA may not be immediately available once liquidity consumed.
- QT, as potential buyer/authorized operator, needs genuine permission to interact, executable acquisition of BOTH rights and adequate funding. Counterparties' ownership and ask prices determine whether any residual profit exists.

If different counterparties have individually stranded cST or REF inventory, a legitimate acquisition/coordination mechanism *might* unlock higher feasible economic value. But counterparties will rationally demand part of the gains; our residual is the **incremental surplus** relative to each party's best standalone action, minus fees, gas, capital, risk, failure and inclusion. No free right transfers or automatic cooperation.

## Verified barriers from official source

`CorkPoolManager._onlyWhitelisted(poolId, msg.sender)` guards `exercise`, `exerciseOther`, `swap`, and related operations. `WhitelistManager.isWhitelisted` returns true if whitelist disabled for that market, OR global/market account explicitly whitelisted; otherwise false. Any “everyone can exercise” assumption fails unless individual target market access is established. `maxExercise`/swap can be zero after expiration or pause. Pool existence by itself does not confirm public eligible exercise, nor executable token offers.

**Official source:** https://github.com/Cork-Technology/phoenix/blob/main/contracts/core/CorkPoolManager.sol and https://github.com/Cork-Technology/phoenix/blob/main/contracts/core/WhitelistManager.sol and https://github.com/Cork-Technology/phoenix/blob/main/contracts/interfaces/IPoolManager.sol. Addresses sourced from official https://github.com/Cork-Technology/phoenix main README.

Phoenix launched 2026; do not confuse historical 2025 Cork exploit/old product with these current contracts.

## Test scope: market existence before economics

Ethereum Cork PoolManager `0xccCCcCcCCccCfAE2Ee43F0E727A8c2969d74B9eC`; WhitelistManager `0xcCccCcCccCC6e38a2772Eb42D2f408eeB89cb0eE`. One **keyless/public** read-only census. Six non-contiguous 100-block windows at head offsets [200,19000,96000,300000,550000,900000] with event filters `MarketCreated`, `PoolSwap`, `PoolModifyLiquidity`, taken from official interface. Verify contract bytecode at pinned tip; for at most 3 discovered market IDs read static `market(id)` and `isMarketWhitelistEnabled(id)`; preserve JSON-RPC responses and SHA via shared transport. 

Only a returned complete window with `count=0` is evidence of no events IN THAT window. Provider 429 / access denied is **missing data**. No authenticated Blockmachine API key sent or used, no authenticated RU consumed, no wallets, no calls that change state, no subscriptions, no OTC inquiries.

If live activity, market ID, unexpired, whitelist and signed order existence are all demonstrated, proceed to finite quote comparisons with a competent conventional conditional route/option exercise benchmark, same information and accessible actions. No presumption that a complex rights graph outperforms the baseline.

## Profit decision gate

`E[terminal CA value] - paid REF - paid cST - financing/carry - protocol fees - gas - execution bid - adverse selection > 0`, with units converted through a real finite executable exit. Stage 2 only if rights independently obtainable and retained net validated under honest competition. A closed, stale or inaccessible market is not a profit opportunity for QT.

No live trading, buying, approvals, signing, lending, outreach or paid API use.
