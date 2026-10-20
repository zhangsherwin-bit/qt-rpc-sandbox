# QT Stage 1 — Does transferable queue priority become a real saleable right?

Hypothesis selected **before** onchain samples: Lido withdrawal requests issue ERC-721 `unstETH` NFTs. The current NFT owner owns the queued claim for ETH after finalisation. Transfer can legitimately move the entitlement, unlike a generic ERC-7540 `controller` status that does not automatically move on share transfers. An ETH-rich buyer might purchase a discounted pending claim from someone who values immediate ETH more than waiting; the buyer's return is compensation for time, staking-loss risk, queue finalisation and market illiquidity, not a free spread.

Core Lido deployment: https://docs.lido.fi/contracts/withdrawal-queue-erc721/ and https://github.com/lidofinance/core/blob/v4.0.0/contracts/0.8.9/WithdrawalQueueBase.sol ; **0x889edC2eDab5f40e902b864aD4d7AdE8E412F9B1** Ethereum. Verified source Transfer(ERC721), WithdrawalRequested and WithdrawalClaimed ABI. Claim requires current token owner, finalised status and unclaimed request. No unauthorised action is contemplated.

## Participant constraints and alternatives

1. Request owner holds the queue NFT but wants ETH earlier; can instead wait for finalisation and claim full ETH, sell stETH instantly **before requesting**, or sell the NFT to a consenting buyer if a market exists. An NFT seller may also accept a price discount only under specific urgency. Unsolicited taking of a NFT or claim is not an opportunity.
2. Buyer has available ETH for the full purchase price and waits until finalisation, with slash/margin/finalisation delays. A flash loan cannot finance a multi-day wait. Its strong alternative is simply buying stETH/wstETH at best executable DEX price and requesting withdrawal, or keeping ETH and investing at its opportunity-cost rate.
3. Marketplace/matcher receives explicit fee. An OTC buyer and seller may avoid fees, but negotiation/credit/settlement risks remain. QT only earns claim yield if it legally buys the NFT under accepted listing/contract; service fees would need a separate paying agreement.
4. Protocol pays ETH on claim once; buying both NFT and stETH cannot double count one already-escrowed claim.

**Conventional baseline:** compare a valid NFT bid with (i) immediately available stETH best executable sale price, and (ii) same-size ETH cost of buying stETH then creating own withdrawal request at same time. Include current yield forfeited in the queue, discounted ETH finalisation value, expected slashing losses, gas, transaction marketplace fees and capital carry. Same information and feasible actions for all strategies. If an NFT has no observed actionable ask, an onchain ERC721 transfer cannot prove a cash arbitrage.

**Lido-specific novel lens:** a *dated, fungible-asset-denominated, transferable queue claim* is a different instrument from liquid stETH. A queue NFT may be faster to redeem than a fresh request when it already has an older position. However, its underlying ETH payout is bounded by its requested stETH and finalisation terms. A priced NFT would be interesting if its risk-adjusted cost were below the *same-time best alternative* by more than all costs.

## Frozen cheap empirical gate

- Ethereum only; chain ID and deployed code verification.
- Four **250-block noncontiguous windows** offset `[200,15000,90000,450000]` blocks from one pinned near-current head. One `eth_getLogs` per window with OR of exact Transfer, WithdrawalRequested, WithdrawalClaimed topics. Split ERC721 mint, secondary owner transfer, and burn; track source requested stETH and actual claims separately, never compare unlike units without precision/risk adjustment.
- From earliest up to eight distinct secondary transfer txs, obtain original transaction and receipt; detect *direct same-transaction ERC20 buyer-to-seller payment hints only*. A transfer alone is NOT proof of sale. Native ETH/marketplace conduit payments require deeper trace and offchain order price and ownership checks.
- Original requests/responses SHA256 archived, abort on missing windows, malformed ABI or account restrictions. **90 conservatively charged authenticated RU max** with **1500 RU protected monthly reserve**; one empirical run on first PR opening only. No live orders, purchase, signature, claim or wallet; no new subscription.
- Confidence hierarchy: `CLAIM_TRANSFER_SUPPORTED_BY_SOURCE` (grounded); `SECONDARY_OWNER_CHANGE_OBSERVED` (only after events); `CASH_PURCHASE_PRICE_VERIFIED` (NOT established by this test); `QT_PROFIT` (NOT established).

Follow-up ONLY if nonmint transfers actually exist: establish contemporaneous binding listing/transaction payment price, age of request at transfer, finalisation outcome and discount net of future expenses vs best liquid-stETH trade. If no real paid purchases exist, retain as permissioned bilateral sale/service hypothesis but do not spend further archive RU just because the token is transferable.
