# QT Stage1 high-level financial precedence in action: Arc creator fee burn

This is a ONE-transaction follow-up to the 2026-10-21 PR105, whose predeclared small source activity check located exactly one onchain TokensBurned event on Arc (Robinhood's fixed sample zero). It is an exploratory *observed incumbent*, not a holdout or QT profit.

**Target frozen before retrieving more details:** Arc chainId 5042, transaction 0xc62e40db737a4cc1ada1a357a1455e8b9531d84cd5baac48db17e26e83f6931d, block 27,067,230, Uniswap BuybackAndBurnClaimRecipient 0x5cEe9852d136833aE26c9E36a96fC02Cdfc9C40C, tokenId 261639, burn asset 0x7c7e04b8bc7e62ce801a84ad057dc7fa11794572, source TokensBurned amount 500,000*10^18 raw tokens.

**Pay-first / pay-later state machine, verified from Uniswap source:**
- BaseClaimRecipient transfers accrued claim to msg.sender (executor) first.
- BaseClaimRecipientWithCallback unconditionally calls IClaimExecutor.onClaimed.
- BuybackAndBurnClaimRecipient thereafter pulls its fixed launch-token burn amount from executor, sending to address(0xdead).
- The native currency is address(0). On Arc native is USDC, so nominal raw claim and transaction gas MUST be denominated Arc-native USDC (18 decimals), not Ethereum ETH. No market price is inferred for this burn asset.

**Frozen cheapest next gate:** original transaction and receipt, the claimed tokenId event with genuine native payout, ERC20 Transfer to burn address, gas, before-block attributed claim amount, threshold, and parent/end balances of tx.sender and tx.to (cannot assume the two are the same). An optional read-only callTracer may be denied by the public provider; absence of trace is MISSING native-payment evidence, not zero other transfers. Max 14 public keyless JSONRPC requests, no retries for 403, wallets, trades, purchases, authenticated Blockmachine RU, or external contact. Raw request-response hashes retained.

**No-profit condition:** even with real fee payout, the source must pay the cost of 500k launch tokens and meet native USDC gas/execution, slippage, allowances and potential producer incentive, and show it can repeat for an independent nonprivileged claimant. Only an actually audited closed native USDC ledger can be promoted.

Docs: https://developers.uniswap.org/docs/liquidity/liquidity-launchpad/guides/buyback-and-burn
Deployments: https://developers.uniswap.org/docs/liquidity/liquidity-launchpad/deployments
Source: https://github.com/Uniswap/liquidity-launcher/blob/main/src/periphery/BuybackAndBurnClaimRecipient.sol
