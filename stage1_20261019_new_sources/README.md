# Programme III Stage 1 — New economic value-transfer families

Date: 2026-10-19. All existing findings and negative controls preserved.

## A. UniswapX permissionless fallback of signed Dutch auctions

Uniswap Labs differentiates permissioned RFQ quoters from permissionless nonexclusive fillers. A nonexclusive filler may receive user input before satisfying output within one reactor executeWithCallback, allowing an onchain atomic conversion route with limited inventory. If a quote's exclusivity expires and the price decays enough, a filler might capture the difference between input cash value and output purchase+fees. This is not the earlier liquidation or issuer redemption mechanism.

Primary protocol: https://developers.uniswap.org/docs/liquidity/uniswapx/filling/overview
Filling: https://developers.uniswap.org/docs/liquidity/uniswapx/filling/dutch-v3-chains/filling-on-dutch-v3-chains
Contracts: https://github.com/Uniswap/UniswapX/blob/main/src/base/ReactorEvents.sol
Deployments: https://developers.uniswap.org/docs/liquidity/uniswapx/deployments

Predeclared Base and Ethereum sources: two official deployed reactors per chain. Event Fill(bytes32 indexed orderHash,address indexed filler,address indexed swapper,uint256 nonce). Sample five disjoint 360-block windows per chain, ending at pinned tip minus offsets [200, 20000, 70000, 160000, 360000]. Select the first eight different event transactions per family/chain by block/log order for receipt and ERC20 transfer review. Fills prove incumbent activity, not open-auction eligibility: the Fill event alone does not reveal the exclusivity timeout or whether the incumbent was the exclusive quoter. Economic cash in/out requires order ABI, finite route, native transfers and gas. Do not call a token-transfer delta profit.

## B. ERC-4337 compensated bundler service

Permissionless UserOperation aggregation provides transaction fees to an EntryPoint beneficiary. Query v0.7 and v0.8 on both chains, same fixed windows. Decode UserOperationEvent (nonce, success, actualGasCost, actualGasUsed). For earliest eight distinct transactions per chain, match tx beneficiary with tx sender, receipt events, execution gas and Base L1 fee if reported. If beneficiary matches sender, the difference between logged UserOp cost and receipt fee is only a historical third-party conditional margin proxy, not an observed ETH payout or capturable profit. Running a bundler entails simulation, public mempool monitoring, competition and upfront gas, not a flash-loan route.

Primary ABI: https://github.com/eth-infinitism/account-abstraction/blob/develop/contracts/interfaces/IEntryPoint.sol
Standard: https://eips.ethereum.org/EIPS/eip-4337
Deployed addresses: https://www.alchemy.com/docs/wallets/reference/bundler-faqs

## C. Cheap negative control: GMX V2 execution reward

GMX exchange order execution pays keeper network costs, but OrderHandler.executeOrder is guarded by onlyOrderKeeper. A regular independent trader lacks that role without special permission. No authenticated archive RU should be spent screening an accessible keeper reward on the assumption it is open.
Source: https://github.com/gmx-io/gmx-synthetics ; https://docs.gmx.io/docs/api/contracts/architecture/

## Gates and audit

Exact two-chain block hashes pinned and rechecked; five disjoint windows, two reactor/EntryPoint addresses per chain. Estimate 20 eth_getLogs calls of up to 360 blocks each at conservatively 10 RU/call (~200 RU), plus up to 64 transaction/receipt lookups, with onchain calls/read-only RPC limited by a shared 400-RU upper bound and a 1500-RU period reserve. Logs and original responses preserved with request SHA-256 in GitHub Actions artifacts. No trades, wallets, broadcasting, private order flow, geo workarounds or earnings claims.

Do not promote Stage 2 for a fee proxy or gross nonexecutable order, and do not extrapolate five noncontiguous windows into a yearly opportunity rate. This run explicitly seeks falsification of new mechanisms, not only confirmations.
