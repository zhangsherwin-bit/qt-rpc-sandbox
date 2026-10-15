# QT executed findings — 15 October 2026

## Decision

The new GitHub executions establish a cash-first Aave liquidation and a measurable implementation-cost improvement, not a huge-profit business. With the same historical producer payment, the same observed effective gas price and complete ETH profit delivery, the alternative uses 369,163 gas versus 459,545 for the incumbent: 90,382 fewer gas, or 19.6677%. Its conditional net is 0.001011431554853929 ETH, versus the incumbent sender-plus-executor scoped residual of 0.000039257328726455 ETH. At an explicitly illustrative ETH price of $3,000, the alternative net is approximately $3.03. That is not a current or historical fiat execution price.

No blockchain transactions were signed or sent. No wallet keys, token endowments, native funding or live contract deployments were used. The research PRs remain drafts and unmerged. All substantive experiments described below have completed; no recurring monitor was scheduled.

## Aave: exact preceding calls, then actual cash

Historical development anchor: Ethereum block 25,832,491, transaction index 3, 25 August 2026 at 13:23:59 UTC. Transaction `0xc9a55cc994a45ee75562bc7f316e1a81414b4db888437e577829b131257ee711`.

Initial parent-state and timestamp-only scenarios reverted with HealthFactorNotBelowThreshold. Replaying the three actual preceding transactions was necessary. Each preceding call matched canonical emitted logs, success status and gas: 74,140, 150,642 and 74,260. The environment control matched chain, block number, timestamp and zero native executor balance. The resulting borrower health factor was 0.999577446865249314.

The alternative starts with zero WETH and zero native ETH, receives 8.186851527017773324 WETH collateral and repays 7.834307681356720885 WETH without a separate flash lender. Gross surplus is 0.352543845661052439 WETH. It has no remaining Aave debt.

The incumbent paid 0.347561592993146169 ETH to the block producer, approximately 98.5868% of gross surplus. Network gas cost was 0.004942995339179815 ETH. Consolidating the observed sender and executor leaves 0.000039257328726455 ETH. Beneficial ownership, private rebates and whole-bot P&L are not established. WETH Withdrawal events were debited before combining WETH and native ETH, avoiding double counting.

## Complete-payout comparison

Run 38775179765, commit cea94280802cddafa6c9c64691ed0aa48a381e1c, artifact 11994020142.

| Item | Incumbent | Alternative simulation |
|---|---:|---:|
| Gross WETH surplus | 0.352543845661052439 | 0.352543845661052439 |
| Producer payment, ETH | 0.347561592993146169 | 0.347561592993146169 |
| Full charged gas | 459545 | 369163 |
| Gas at observed 10756281407 wei/gas, ETH | 0.004942995339179815 | 0.003970821113052341 |
| Net after producer payment and priced gas, ETH | 0.000039257328726455 | 0.001011431554853929 |

The alternative actually unwraps the entire surplus, pays the observed producer bid and delivers 0.004982252667906270 ETH to the simulated caller before network-cost accounting. Executor ETH and WETH both end at zero. Improvement after priced gas is 0.000972174226127474 ETH. An earlier variant kept WETH in the executor and used 381838 gas; the complete-payout case is the stronger terminal-asset comparison.

The full gas report includes applicable refunds; the internal gasleft counter is not used as the billed transaction total. The saving belongs to the complete implementation comparison, not an experiment isolating flash-loan removal from every other code difference.

Synthetic probe calls use explicit gasPrice=0 with validation disabled, and their full measured gas is charged afterward at the historical winner's effective gas price. Real preceding calls retain their fee fields. Only research executor code is inserted at an empty address. No production balances, borrower storage, oracles or contract code are replaced. Observed header time, number and producer context are supplied explicitly.

This proves conditional historical execution, not independent state-root attestation, prospective discovery, a minimum winning bid or inclusion probability. A real sender still needs gas, and live deployment, failed attempts, operating costs and extra inclusion expenditure are excluded. The borrower and trade size were historically selected.

## yoUSD replay

Run 38771437945 reproduced the prior Base development event at block 51,840,855, 27 September 2026, 01:04:17 UTC. Actual redemption: 7480.863965 USDC. Repayment: 7290.174838 USDC. Cash before costs: 190.689127 USDC. Internal gas: 236249, not a complete Base fee.

The actual predecessor-time control and after-winner-block control reverted as healthy. Predecessor storage at the observed next-block time produced the cash above. Environment checks passed. This does not reconstruct all preceding index-45 transactions, demonstrate advance borrower discovery, add recurrence evidence or establish capture. It is not new live income.

## Fresh Midnight screen

Run 38770635819 pinned Base block 52,646,513 at 15 October 2026, 16:39:33 UTC. It received 300 listed Base USDC market definitions within three capped pages; pagination remained incomplete. Twelve comparable markets were selected within those returned pages, not a proved exhaustive or global top-12 census.

Compiler, pinned core-runtime fingerprint, market identifiers, code-only environment and ending block-hash checks passed. The 167 requests comprised 156 HTTP 200 and 11 HTTP 422 insufficient-size quote responses. Those 422 responses are application outcomes, not DNS or GitHub network failures.

The 74 borrower-market positions read in six cash-enabled markets contained no active USDC collateral. Two larger markets remained incomplete under the 32-position per-market cap; their read debt coverage was approximately 81.31% and 92.62%. Four smaller cash-enabled markets fully reconciled. No candidate qualified for a full cash-route simulation; this is an overlap-screen result, not twelve losing executed trades.

One actual sell ask existed in cbADA/USDC, November maturity: 151.817920 face units at price 0.9939828, zero observed settlement fee, purchase cost 150.904402 USDC. Its hypothetical immediate-par margin is 0.913518 USDC, but actual same-market withdrawable cash is zero. The best displayed bid price is 0.9937398; even granting full size and funding, the optimistic crossed-book spread is -0.036893 USDC before gas. Other markets' withdrawal balances cannot be assigned to this market's claim.

## Earlier repository evidence, re-audited rather than rerun

Run 38755307646 acquired a complete earlier position cohort before a later source-copy step failed. At Base block 52,643,331, 15 October 2026 14:53:29 UTC, the two relevant large markets contained 354 and 275 positions. All 629 borrower-market positions had no USDC collateral and none was unhealthy. Independent integer health and debt reconciliation matched the canonical market totals. This earlier full coverage is not substituted for the later incomplete snapshot; counts must not be added as unique borrowers.

Run 38756832435 covers a frozen indexed cohort from 10 October 00:00 to 15 October 14:45:18 UTC. The audit matched 221 Base/USDC liquidation events across 56 transactions to canonical receipts, emitter, identities and amount fields. Of these, 175 events across 34 transactions used the recorded Atlas entrypoint, accounting for 399006.486423 of 410386.777586 USDC repaid, or 97.2269%. Seven solver contract addresses were observed, not proof of seven independent firms. Indexed cohort completeness is not chain-wide completeness. Repayment volume and auction payments are not solver profit.

Atlas-mediated execution makes auction access and inclusion economics relevant in this sample. Faster polling of completed blocks alone is not a measured capture strategy. No live auction feed access, solver onboarding or bid submission was tested.

## Research priority

Retain cash-first execution and specialised immediate redemption, but optimise retained cash after the same inclusion benchmark and complete payout rather than headline liquidation bonuses. Freeze a broader event cohort before extending the selected Aave result. Separate oracle-triggered, interest-triggered, maturity-triggered and cash-replenishment opportunities; they have different information and execution requirements.

Any proposed multi-leg combination must beat the best simple alternative in the same evolving state. Do not add independently reset profits, duplicate shared maker budgets, call borrowed principal income, or presume larger flash financing creates additional collateral. Midnight-only bot development is not supported by these snapshots. A substantial business still needs qualifying flow, retained margin and actual capture, none measured prospectively here.

## Verification inventory

Seven original artifact ZIP digests and 326 raw response-body hashes were verified offline. Five substantive new stages contribute 221 observations; re-audited earlier acquisitions contribute 105. Fourteen distinct offline ABI/safety regression tests passed; repetition across workflows is not independent evidence. Intermediate automatic duplicate run 38772524341 repeated an old stage and is excluded from the independent-stage counts and economic comparisons.

New stages: 38770635819, 38771437945, 38772570599, 38773095244, 38775179765. Earlier re-audited stages: 38755307646, 38756832435. Research PRs: #5 and #6. The chat evidence package includes untouched original artifacts, Solidity/compiler outputs, raw failures, a standard-library offline audit, machine-readable results and a detailed report.
