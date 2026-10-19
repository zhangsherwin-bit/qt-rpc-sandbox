# Programme III Stage 1 — Beefy permissionless harvest caller reward
New, non-liquidation revenue mechanism: contractually defined compensation for compounding yield. Documents: docs.beefy.finance/developer-documentation/strategy-contract and /beefy-api, with explicit Cowllector incumbent in docs.beefy.finance/dao/treasury.

No wallet, key, transaction broadcast, trading capital, state edits, provider-denial workaround, or claim of independent capture. Fixed date of research: 2026-10-19.

## Frozen empirical design
- API metadata /vaults /tvl /apy /fees: top 3 vaults by positive TVL, plus top 3 by TVL * reported APY * caller fee, excluding dead vaults, separately Ethereum and Base. **Selection before on-chain reward measurements**.
- Onchain anchor latest-4; verify chain ID and canonical block hash.
- Strategy contract callReward(), native(), paused(), lastHarvest(), plus read-only harvest gas estimation. Positive quote is not cash.
- Ten disjoint historical event search periods (5 per chain) each 950 blocks, offset [100,9100,18100,36100,72100] from canonical tip anchor; only ChargedFees topic on six selected strategies per chain. Zero log pages don't imply all harvesting is absent because strategy ABI/version may differ.
- First 8 historical fee events per chain selected by ascending block/log, not by amount: validate canonical receipts, wrapped native ERC20 Transfer from strategy to exact actual tx sender matching ChargedFees amount, gas, and Base L1 fee if present. Missing L1 fee is explicitly incomplete.
- Onchain third-party actual receipts are not independent trader profits; gas does not establish priority or builder competition; strategy fee emission not necessarily externally cash payable.
- Stop that provider on HTTP401/403/429; cap 75 RPC calls per chain and 15MB response per API GET. Preserve exact bodies, SHA-256 and all failures.

## Economic decision gate
Cash reward > actual gas + L1 + producer payments with real transfer to independent ordinary sender and authentic harvest rights at a prewinner time. Even positive selected receipts are incumbent income, **not** proven future outsider capture or expected monthly portfolio PnL.
