# QT Stage 1 — Independent volatile dynamic-fee extraction hypothesis (2026-10-19)

**True economic question:** Uniswap's newly deployed Ethereum VolatilePair ETH/USDC hook makes bid/ask fees depend on price movement, with temporary and mid-block backrun capture. A public flash-financed trader could profit only if a finite v4-to-v3 (or v3-to-v4) same-block route closes more native ETH/WETH than it started with, *after* all swaps, gas and producer competition. This is a new 2026 dynamic-fee mechanism, not evidence of profitable backrunning.

Frozen official contracts: hook 0x000022Ec4eBD6b12294396E852E4C3876b253Cc0; ETH/USDC PoolId 0x98316e8405502774a5d0a0761276b5d26505a8195c1905169864008d5e7a3eea; v4 Quoter 0x52F0E24D1c21C8A0cB1e5a5dD6198556BD9E1203; v3 QuoterV2 0x61fFE014bA17989E743c5F6cB21bF9697530B21e. Derive v4 PoolId from abi.encode(PoolKey) before any authenticated requests; reject mismatch.

Eight historical block states at offsets [0,1,2,3,1000,7000,30000,90000] from canonical tip-minus-five; four prescribed cash route states [0,7000,30000,90000]. Input WETH sizes [0.05,0.25,1] with two v3 fee tiers 500,3000, in BOTH market directions, and one v3-only control. Use same block state for each leg. WETH unwrap/re-wrap to native ETH is 1:1 by contract but introduces gas; the quote does not pretend free flash principal or guaranteed atomic inclusion. Historical prices are returned by deployed v4/v3 Quoter contracts, not USD-par midpoints.

A finite quote is *pre-gas*; actual executions require bundling/concurrency, WETH wrap, approvals, flash premiums, gas/priority, and probability of beating existing MEV bots. No trading, signing or state mutation. Provider-denied RPC data remains unresolved. One-time PR-open study only, under strict shared 250-RU maximum, 1500 RU balance reserve, conservative 55% of verified 300 RU/minute. All raw requests/responses and SHA retained.

Primary official docs:
https://developers.uniswap.org/docs/protocols/uniswap-labs-hooks/volatile-pair/overview
https://developers.uniswap.org/docs/protocols/uniswap-labs-hooks/volatile-pair/deployments
https://developers.uniswap.org/docs/protocols/uniswap-labs-hooks/volatile-pair/guides/swap
https://developers.uniswap.org/docs/protocols/v3/deployments/v3-ethereum-deployments
