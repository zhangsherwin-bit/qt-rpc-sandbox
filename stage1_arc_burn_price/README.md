# Stage 1 — Arc native USDC claim before launch-token burn

This is a source-frozen, one-transaction economic falsification, NOT a trade signal. Uniswap BuybackAndBurnClaimRecipient first pays attributed native currency to the caller, then calls the caller as IClaimExecutor and finally takes a fixed number of currency1 tokens for the burn address. On Arc, native currency is USDC with 18 onchain balance decimals.

The original independently observed PR107 target: Arc 5042, block 27067230, tx 0xc62e40db737a4cc1ada1a357a1455e8b9531d84cd5baac48db17e26e83f6931d; a real 10.000 native-USDC claim and actual burn of 500,000 tokens (18 decimals), asset 0x7c7e04b8bc7e62ce801a84ad057dc7fa11794572. Original transaction gas was 0.5214597 native USDC. Source tracer is unavailable and the sender balance delta is NOT attributed to claim profit.

**Necessary burn acquisition break-even:** at most 9.4785403 native USDC after the historical original gas, or 0.0000189570806 USDC per burn token BEFORE other execution costs, private producer payment and inventory financing. This is a strict ceiling, NOT a quoted token price.

## Frozen real price test

At original parent block 27067229, fetch the exact Uniswap v4 position's PoolKey from Arc PositionManager for tokenId 261639. Only trust a pool with currency0 native address(0) and currency1 the verified burn token. Fetch the token's decimals. Then perform read-only v4 Quoter quoteExactOutputSingle calls for 5,000, 50,000 and FULL 500,000 tokens. Pool fee, tick spacing and hook are from the deployed position. The FULL finite quote is the relevant comparator; smaller sizes are slippage diagnostics and never substitute for full funding.

The strong baseline is an independent solver with the same pool, same executable liquidity, fees and gas. The new precedence-based model finds a possible capital-free execution order, but gives NO automatic reduction in token acquisition cost or producer competition.

If full direct pool quote unavailable, mark it UNRESOLVED for other possible routes, not zero profit across all venues. If a positive gross quote exists, follow with exact own-executor callback and private block-producer cost accounting; no Stage2 promotion before that.

Official sources: https://developers.uniswap.org/docs/protocols/v4/deployments ; https://github.com/Uniswap/v4-periphery/blob/main/src/interfaces/IV4Quoter.sol ; https://github.com/Uniswap/v4-periphery/blob/main/src/PositionManager.sol ; https://github.com/Uniswap/liquidity-launcher/blob/main/src/periphery/BuybackAndBurnClaimRecipient.sol .

**Constraints:** <=14 public keyless read-only Arc requests, original SHA256 audit, no secrets, trades, orders, wallets, new permissions or purchases. Offline unit tests first; empirical only on PR opening. No authenticated Blockmachine RU spent. Keep existing QT baseline intact.
