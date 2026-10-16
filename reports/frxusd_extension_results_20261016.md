# QT frxUSD extension — completed results, 16 October 2026

Two new read-only GitHub experiments were launched during this continuation, not merely retrieved from old runs. PR #16/run 38917824889 completed collection at 14:53:59 UTC; PR #17/run 38919921563 completed at 15:05:34 UTC. Both compiled and executed research probes in historical EVM state. All 45 RPC response hashes and both artifact digests were independently checked. Sixteen route simulation cases: four paid cash and twelve failed principal coverage. These are correlated scenario tests, not sixteen independent opportunities or a success-rate estimate. No transactions were signed or broadcast; PRs remain unmerged.

## A stronger cash route, not a large-income confirmation

At the beginning of Ethereum block 25,643,400, the original 20,000-USDC route (USDC->WETH->crvUSD->frxUSD->USDC redemption) paid 526.949931 USDC after repaying financing and buying 0.0002 ETH reserve. A direct USDC->WETH->crvUSD->USDC pool route paid **528.926943 USDC** under the same reserve and state. No competitive inclusion bid is included. Actual upfront gas, deployment, failed attempts and capture are not established.

The direct exit produced 20,529.307700 USDC, repaid 20,000 USDC, spent 0.380757 USDC buying the reserve and paid 528.926943 USDC. It consumed 613,404 gas versus 970,662 for the original: **357,258 gas or 36.8056% less**, with **1.977012 USDC more cash**. All initial token/native balances at the executor and caller were zero. Full USDC repayment and payout were checked against transfers; the probe finished with no intermediate-token/native balance. Synthetic caller gas price is zero; measured gas is costed afterward, with the fixed reserve exceeding historical base-fee cost.

The alternative only changes the final exit and coin-order guard; repayment, callback, minimum-profit and terminal-balance checks remain. Curve's official repository identifies the direct pool 0x4DEcE678ceceb27446b35C672dC7d61F30bAD69E with USDC index 0 and crvUSD index 1. The probe checks those coins.

## Size and later-state tests

Original-route payout at the +1-block state:

| USDC principal | USDC paid |
|---:|---:|
| 500 | 24.577452 |
| 5,000 | 220.452516 |
| 20,000 | 526.949931 |
| 50,000 | Reverted before covering principal |
| 100,000 | Reverted before covering principal |
| 250,000 | Reverted before covering principal |

At +2 blocks, all four tested original sizes (500/5,000/20,000/50,000) failed principal coverage. The direct route failed at 20,000/+2 and 100,000/+1. A larger flash loan does not multiply the observed margin. Twenty thousand is the best tested original size, not a proven global optimum. Counterfactual size/route profits cannot be added.

The same original 20,000-USDC route failed after the selected July 31 and August 30 wrapper events. Those are retrospective extensions, not clean prospective holdouts. They do not support a repeatability claim; neither does a 1/3 success-rate interpretation. Their original transactions did not dispose through the same specific pool pair as the July 30 seed. The next event filter should concern actual price-moving pool flows, not just liquidation labels.

## Exact transaction that removes the original margin

The next-block pool-log query found two ETH/crvUSD Tri-pool exchanges, no frxUSD/crvUSD pool exchanges, and one transaction at index zero:

0x16b00a1ef23a7f028fbb0f4366ea0282ed82e186cd30ba171272209ccd51afcf

The second study replays that actual transaction in the canonical parent state and target header. Its status, gas and normalized logs exactly match the canonical receipt. Retrying the original 20,000-USDC route immediately afterward fails the principal-coverage guard, with full rollback. Before that transaction, the same route paid 526.949931 USDC. This isolates a sufficient state-changing transaction; it does not prove failure of every other possible route or size.

The intervening transaction sent 11.017474963648977725 WETH into the Tri pool and received 21,522.663047704695285773 crvUSD. It also exchanged 20,382.491294823436062476 crvUSD for 20,363.891366 USDC through the direct pool. It did not use the original frxUSD/crvUSD pool. These are pool-local flows, not whole-transaction profit. The direct route was tested at +2, not immediately after this prefix.

The evidence supports a quickly competed pool-price discrepancy, not a unique frxUSD redemption advantage. The direct cash exit was already present in the intervening historical transaction; the improvement is to our implementation, not proof of market novelty.

## Inclusion comparison must be scoped correctly

The actual target block used 59,996,979 of 60,000,000 gas. Our direct probe would require at least 610,383 gas of other work to be displaced (original route: 967,641), holding that limit fixed. A beginning-of-block simulation is not an obtainable slot.

The index-zero transaction consumed 9,848,734 gas, emitted 527 logs and transferred 20 distinct ERC20 tokens. Its visible direct producer payment was 2.335894705123339920 ETH, plus 0.000009848734 ETH priority fees, total 2.335904553857339920 ETH. This is compensation for the entire multi-operation transaction; it is not a demonstrated minimum bid for our single smaller loop. Do not subtract all of it from our loop or assume zero inclusion cost. The relevant lost-producer-revenue counterfactual has not been measured. Sender/root-executor balance vectors do not establish beneficial ownership or whole-bot P&L.

## Verification and next decision

First-job offline tests: 10. Second-job exact source-transformation tests: 5. Additional independent audit tests: 8. Twenty-three distinct engineering test methods, not twenty-three trading trials. All canonical header, source/runtime, zero-principal, repayment, payout and rollback checks passed. The 20,000-USDC original +1 and +2 cases reproduce earlier observations; they are not new independent events. Reserved October 3–9 outcomes remain untouched.

Next priority is a frozen cohort of comparable pool disposals, competing complete cash exits, transaction-level persistence and realistic inclusion costs. This next study has not been scheduled. No live deployment or large-income claim is supported by these two runs.

Artifacts: 12053463065 (SHA256 342594c706296b189b5cc8e891e8867a50468de120b4e004658d5904d5d207f2); 12054626034 (SHA256 5f3af5063339b84deac6493e5366c3d59f4e2b79f7c2d2b71377736e568c0589).
