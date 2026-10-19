# QT Programme III — Accounting asymmetry, innovation-first Stage 1

**Original economic thesis:** A protocol may account for fewer units than it actually possesses. A permissionless action may make that difference transferable without a price divergence, principal or flash loan. This is a *different* cash source than the 50 existing QT register opportunities and the 6-new-family October 19 addendum.

## Hypothesis A — UniswapV2 and SushiV2 permissionless `skim`

In real deployed v2 pairs, recorded `reserve0`, `reserve1` and actual ERC20 `balanceOf(pair)` can diverge after transfers/rebases. For each token, the *conditional* positive token amount is `max(0, balance-reserve)`. Public `skim(address)` can claim it, but EVM call rights, underlying token transfers, observation before the next sync/trade, inclusion competition, recoverability and consent remain separate questions.

A real positive surplus is **not** yet USD cash. Evaluate stablecoin and WETH amounts in their *native units*, then compare against actual per-chain gas for `skim`, tax or fee-on-transfer rules, observed alternate cash exit and competing builders. Do not infer any USD value for stETH, AMPL, WBTC from a dollar peg or stale oracle. If positive snapshots show up, this can justify an EVM fork of the *same pinned predecessor block*, not live collection.

**Prior art**: Uniswap v2 core and ethereum.org explicitly document unrestricted skim; third-party scanners already exist, so it would be false to label the basic `skim` idea newly invented. Novel research hypothesis: structurally predict and group replenishing surplus *across accounting domains* at moments before competing searchers can monitor them, using legal protocols and strictly owner-unrestricted rights.

Canonical Uniswap V2: https://github.com/Uniswap/v2-core/blob/master/contracts/UniswapV2Pair.sol ; docs https://developers.uniswap.org/docs/protocols/v2/deployments ; original whitepaper https://docs.uniswap.org/whitepaper.pdf ; negative-rebase notes https://developers.uniswap.org/docs/protocols/v2/guides/troubleshooting ; Sushi V2 Ethereum factory https://github.com/levx-me/sushiswap-core .
AMPL positive-rebase economic source: https://github.com/fragmentsorg/ampleforth-contracts/blob/master/README.md .

## Hypothesis B — Sushi BentoBox V1 internal-accounting reconciliation

BentoBox stores totals(token) rebase index and strategyData(token).balance, while ERC20.balanceOf(bentobox) holds external token assets. If direct balance + **accounted** strategy balance > stored total.elastic, some tokens may be uncredited to depositors. The `deposit(token, from=BentoBox, to=caller,...)` branch sometimes allows an external caller to credit the excess to their own BentoBox shares without moving funds; unlike v2 skim, final cash withdrawal, minimum share requirements and the accounting rights need a simulated transaction.

Contract and intended skim documentation: https://dev.abracadabra.money/core-contracts/bentobox ; deployment https://dev.abracadabra.money/deployment-addresses/ethereum-mainnet ; Sushi docs https://www.sushi.com/academy/what-is-bentobox . BentoBox deployment pinned: 0xf5bce5077908a1b7370b9ae04adc565ebd643966.

This is **not** an authority to appropriate mistakenly transferred assets. Some observed surpluses may be legitimately owned by users or recoverable through support/governance. We will not claim operational or legal entitlement from a public method alone, and we will not execute transfers.

## Frozen empirical experiment

- Chain 1: UniswapV2 factory and SushiV2 factory, ten token pair inputs: USDC/WETH, USDT/WETH, DAI/WETH, stETH/WETH, WBTC/WETH, AMPL/WETH, with the exact four Sushi and six Uniswap pairs declared in code.
- Chain 8453: UniswapV2 Base three independent pair candidates, WETH/USDC, WETH/DAI, USDC/DAI.
- Five disjoint chain-specific blocks anchored at latest-5 minus offsets [8, 20008, 70008, 150008, 360008]; evidence pins hashes, reserves and actual external balances.
- BentoBox four tracked tokens (USDC, USDT, WETH, DAI) at first three predeclared Ethereum anchors; compute strategy-aware discrepancy. If positive, at most six deterministic simulated `eth_call` deposit and optional gas estimates.
- V2 at most six deterministic positive surpluses per chain undergo read-only `skim` simulation and optional gas estimate.
- 430 estimated RU hard cap shared between chains with 1500RU protected floor, historical RPC uses 55% of actual rate limit. **No transactions submitted, no real assets touched**.
- All RPC responses and request bodies held with per-request SHA and key redaction; no logs containing credentials.
- Source selection precedes outcomes. There is no full registry, long-term recurrence, prewinner competition or live capture proof.

## Stage 2 promotion gate

Only after same-block static simulation of actual transfer + cash route, validated native token realisable proceeds minus gas+builder costs, non-owner rights, competition and multi-period recurrence can this join Stage 2 shadow engineering. A gross surplus >0 is a Stage 1 screening observation, not a profit event. Independent raw token quantities must never be summed as USD.
