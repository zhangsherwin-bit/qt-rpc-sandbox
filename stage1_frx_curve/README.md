# Stage 1 — real Curve frxUSD acquisition and primary USDC redemption

*Independent cash-mechanism follow-through*, not a new live trade: public Curve 3pool is DAI/USDC/USDT with official token indices 1/2; 0xD6937eA8D33B0C21348F36F7895FdE3054bA4927 is live Curve NG frxUSD/USDT pair with frxUSD index 0 and USDT index 1. The frxUSD/USDC custodian 0x4F95C5bA0C7c69FB2f9340E190cCeE890B3bd87c is official Frax contract. Full end-to-end cash budget is USDC input -> USDT -> frxUSD -> USDC, using exact finite quotes at one pinned canonical block, not hypothetical USD=USD parity.

Official sources: https://www.curve.finance/dex/ethereum/pools/0xD6937eA8D33B0C21348F36F7895FdE3054bA4927 ; https://docs.curve.finance/developer/integration/stableswap-ng/ ; https://docs.frax.com/frxusd/mint-and-redeem-routes ; https://github.com/curvefi/curve-js/blob/master/src/constants/pools/ethereum.ts .

Predeclared anchors relative to current canonical tip: offsets [4,7004,27004,77004] across 4 disjoint market states; USDC budgets [100,1000,5000,25000] each. Verify actual pool coin addresses from chain before quoting, use 3pool and Curve NG get_dy(int128,int128,uint256), the issuer previewRedeem(uint256) fee-adjusted output, and custodian USDC balance/cap reference. Preserve all RPC bodies and SHA. Never reinterpret a failed route, redeemer permission, zero balance, rate/provider denial as negative economic proof.

This is a **pre-execution quote screen**; actual atomic financing, approvals, withdrawal rights, settlement receipts, two pool state transitions, gas, slippage from combined execution and MEV competition remain UNPROVEN. Positive gross quotes only earn a route-to-atomic-fork experiment, not Stage 2 or claimed profit. No signing, wallets, trades, provider workaround or changes to main.
