# QT Programme III Stage 1 — a new right: pay UNI to release protocol revenue

**20 Oct 2026. Source-grounded contractual mechanism, NOT current QT income.**

Official Ethereum deployed Uniswap TokenJar 0xf38521f130fcCF29dB1961597bc5d2B60F995f85 and Firepit 0x0D5Cd355e2aBEB8fb1552F56c965B867346d6721. Source: https://github.com/Uniswap/protocol-fees . Uniswap Docs https://developers.uniswap.org/docs/protocols/protocol-fee/overview .

## Economics, participants and why this was absent from a swap-only search

The Uniswap protocol earns fees from v2/v3/v4 and channels assets to TokenJar. A user with sufficient UNI can call Firepit.release(current_nonce, SELECTED_ASSETS, recipient), transferring exactly Firepit.threshold() UNI from the caller to 0xdead and releasing **all available balances of each selected asset** from TokenJar to recipient (up to MAX_RELEASE_LENGTH=20 assets). Caller must own or atomically source burn UNI; governance controls threshold. The fee assets are NOT ownerless/unpaid arbitrary ERC20 balances. Their legitimate purchase right is fully specified by the release contract.

The opportunity is purchasing *a finite basket of mixed assets* with a fixed cost denominated in another asset, UNI; neither a conventional Uniswap two-leg swap nor a generic keeper reward. A searcher without an oracle can still compare exact liquidation routes and decide whether conversion into UNI repays principal/burn/fees. A possible flash-financed callback is ONLY hypothetical until atomic UNI borrowing, approval, the release, sale of the complete non-UNI asset basket and repayment are simulated in a fork. The fixed threshold may demand substantial working capital in UNI (historically 4000 mainnet according to governance in 2026); zero-principal is NOT an established capability.

For each asset j, obtain jar balance q_j and executable liquidation value V_j(q_j) on the same pinned block, accounting for token restrictions and transfer fees. LP tokens require proportional underlying token reserves/realizable burn proceeds; treating v2 LP as an ERC20 price without checking underlying claims may miss value. The correct action is choose at most 20 assets maximizing sum_j V_j(q_j) - UNI acquisition/burn cost - gas - routing fees - miner/validator bids - any working capital finance. NOTE: assets not selected remain in TokenJar, while the UNI burn is per release; splitting one profitable group across releases creates repeated costs. A serious baseline is a solver with this SAME official release ABI and live basket prices, not a simplistic spot spread algorithm. An actually better discovery only exists if richer temporal or contingent rights reveal value missed by that baseline.

The nonce is indispensable: read offchain and pass frozen; do not reread nonce inside a wrapper in the same transaction. Existing Uniswap docs warn this could lead to burning UNI for a depleted basket. Calls after another release should revert without burning when nonce mismatched. Transaction **success** alone is NOT actual retained net P&L: QT's Convex receipts taught us that block-fee-recipient ETH transfers consume apparently enormous reward value. Historical receipts show only token movement and regular tx gas; direct ETH/builder payments require execution tracing.

Official ABI:
- Firepit extends ExchangeReleaser.sol and ResourceManager.sol, with release(uint256,address[],address), threshold(), nonce(), MAX_RELEASE_LENGTH(), RESOURCE(), TOKEN_JAR().
- TokenJar public releaser() must equal Firepit; only it can release assets. Each selected asset is released in its entirety.
- Firepit emits Released(uint256 indexed nonce,address indexed recipient,Currency[] assets).
- Uniswap v2 LP token balances may be material; docs explicitly caution underlying accounting/finite slippage.
- Max release basket 20 tokens.

## First zero-write existence screen

One Ethereum pinned head; only historical read-only RPC. Verify actual code, jar.releaser, firepit.tokenJar, burn UNI address/threshold/nonce. Fixed partial inventory of 10 mainstream ERC20/v2 LP assets, plus native ETH, with raw balances. LP raw reserves only when holding positive LP tokens. NO invented USD or LP token prices. Four disjoint 6000-block historical windows at offsets [200,26000,115000,440000] from pinned head; exact Released events. Earliest up to 5 release tx receipts and UNI transfers to the burn address; any ETH payout or direct fee recipient payment remains **unverified** until trace.

- Max conservative authenticated RU attempts: **170**, protect **1500** RU floor, 55% of provider rate, one run only at PR opening after offline ABI tests. No source changes cause new empirical run.
- All raw RPC requests/responses + SHA archives; unknown/blocked data = UNRESOLVED.
- No wallet, private key, order, burn, claim, swap, new subscription, or traded cash.
- Status COMPLETE_ACTIVITY_SCREEN = coverage and source matches only; never STATUS PROFITABLE.

## Best future tests if active

1. Enumerate **all** jar-held assets including newly minted v2 LP positions and dynamically changing fee-adapter inventory, not only 10 representative assets.
2. Same-block finite full-basket sale to UNI/WETH/USDC using available liquidity; compare optimised basket to asset-by-asset liquidation with repeated burn and best independent paths; test marginal bundle advantage.
3. Reconstruct incumbent fee-recipient payments by trace, not only tx.gas, and use holdout releases. Measure whether liquidity and nonce competition leave **QT-owned terminal UNI or ETH** after a hypothetical self-financing atomic execution.
4. Evaluate Base/Unichain L2 Firepit with different fee threshold/bridge cost only if actual eligible fee tokens and activity are observed. The UNI bridging/burn rights on L2 differ from Ethereum.

Independent use of this smart contract is allowed by source, but past successful third-party burns or gross fees do not establish personal income, recurring execution, or low-competition access.
