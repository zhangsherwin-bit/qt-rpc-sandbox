# QT Stage 1 forensic gate: historical Convex 78 CRV caller reward

Already frozen, **not** a holdout: Ethereum block 25,941,501, transaction 0x211f62115ec9c55f349b6fdd100f6e0c7bd6a45baad70f5e9340f8f64150db4f, chosen as the tenth distinct original recipient sampled without profitability ranking in Stage 1 PR91.

The raw 2026-10-19 receipt provides a strong **historical original executor cash trail**:

* Convex Booster --> sender: 78.0114360904997 CRV;
* sender --> Uniswap V3 pool: same 78.0114360904997 CRV;
* pool --> sender: 0.011379084255985276 WETH;
* sender WETH Withdrawal: same amount converted to native ETH;
* receipt gas: 769,480 units at 0.068381913 gwei, cost 0.00005261851441524 ETH;
* revenue less recorded L1 onchain gas: 0.011326465741570036 ETH, **conditional on no other native balance effect**.

This is stronger than a hypothetical quote; however, tx sender equals recipient (self-call via unknown previously deployed/delegated code) and historical execution does NOT mean an outsider could claim the same reward. Historical caller had fee automation and potentially existing permit/strategy advantages. The known 78 CRV is selected in the original archive and cannot be used to claim an unbiased profit frequency.

**Next minimal exact-block archival verification:** read only block hashes, transaction and receipt, sender code at parent block, ETH balance at parent and target block, current-at-the-time Booster caller fee, and predecessor Uniswap v3 CRV-to-WETH quote. Recompute all reward-token flows and WETH unwrap independently. If ETH balance difference equals the receipt-native-output minus paid transaction gas and no other block-level transfers, mark CASH_RECONCILED; otherwise UNRESOLVED. The on-chain sender may have other same-block incoming/outgoing ETH that cannot be distinguished by this balance delta alone; even equality does not establish lack of privileged orderflow.

**Controls:** max **14 conservatively estimated RU**, preserve **1,500 monthly RU**, zero broadcasting, accounts, private keys or live trades. Source HTTP responses archived with SHA. Empirical job only on PR opened; later commits run offline regression only. No Stage2 promotion before recurring PREWINNER incentive observations and outsider-capturable next-block fork tests.

Source: https://github.com/convex-eth/platform/blob/main/contracts/contracts/Booster.sol ; https://github.com/Uniswap/v3-periphery/blob/main/contracts/interfaces/IQuoter.sol .
