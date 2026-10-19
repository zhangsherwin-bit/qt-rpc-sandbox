# Programme III — Prize-claim service fee optionality (S1-17 continuation)

Existing QT S1-17 said PRIZE CLAIM service data incomplete. This round makes a deep mechanism distinction, not a claim of discovered income. Winner has a nontransferable right to collect a prize; a separate independent third party can claim on their behalf in return for a programmable fee. This is NOT an NFT purchase or directional bet on the prize.

**Exact source-based cash path:** permissionless Claimer.claimPrizes on behalf of winners -> PrizePool.claimPrize -> PrizePool _rewards[feeRecipient] credit -> PrizePool.withdrawRewards(to,amount) -> prizeToken ERC20 balance credited to receiver. Receipt plus ERC20 Transfer must agree to count genuine terminal cash. The fee credit alone is *not* a payout. If claim contracts make the credit available in the same transaction, a purpose-built claimant could potentially combine claiming and withdrawal atomically; this requires own fork validation and claims that exist at decision time. Principal of the prize itself is not required but gas is.

Source: https://github.com/GenerationSoftware/pt-v5-claimer/blob/main/src/Claimer.sol
Source: https://github.com/GenerationSoftware/pt-v5-prize-pool/blob/main/src/PrizePool.sol

Official 2024 Base mainnet deployed contracts (revalidate code at present pinned block):
PrizePool 0x45b2010d8a4f08b53c9fa7544c51dfd9733732cb
Claimer 0xcdCE635b774DE77cdF791647601dba64a75547ba
Ethereum PrizePool 0x7865d01da4c9ba2f69b7879e6d2483ab6b354d95
Ethereum Claimer 0x54aa02cbc223Fc834949FB1fd8C855e4dA126c7D
Source: https://github.com/GenerationSoftware/pt-v5-mainnet/tree/main/deployments

Economic mechanism: VRGDA dynamic claim fee. For n winner-prize claims in a batch, actual claimant reward is n * computed fee-per-claim only for successful claims, and the fee path changes as claims accumulate. Batching amortizes gas, but can *dilute per-claim reward* or pick unclaimable already-spent rewards. Therefore max-size batch is not automatically profit-maximizing. Compare fee quote at historical predecessor for n=1,2,4,8, then measure true claim credits and withdrawal receipts.

Predeclared 5 historical 4000-block windows per chain, 10 total eth_getLogs calls on PrizePool with OR of exact ClaimPrize and WithdrawRewards topics, conservative <=250RU, plus <=14 unique sampled cash-withdrawal receipts and 2 predecessor fee curves per chain within <=365RU hard cap, 1,500RU monthly floor.

No wallet, no share owner impersonation, no speculative signing, no prize ticket buying. Contractual claimer only. Source code is a permissionless claim service, not authorisation to claim prizes for a user by bypassing contract rights. Self-claiming already-claimed or award not valid should fail by contract. We do not submit calls.

Important caveats: cash token may be illiquid or volatile; do not assume 1 token=$1 or claim bonus nominal USD. Deadline-based competition and pre-award winner discovery can dominate. Historical withdrawals can aggregate many credits from outside sampled windows; do not sum claim and withdrawal totals as separate revenue. Historical event counts alone do not imply forecast annual income. Stage 2 only if liquid cash conversion, own end-to-end fork, available winner inventory and capture proven.
