# QT Stage 1 — two new forms of genuinely transferable but non-fungible value

20 October 2026. Distinct from token exchanges, ordinary liquidations and unrelated rights-graphs. **Presence tests are NOT trading profits.**

## 1. Time-conditioned payment streams: Sablier Lockup

Official Sablier lockup contract deployed Ethereum `0x93b37Bd5B6b278373217333Ac30D7E74c85fBDCB` from https://github.com/sablier-labs/evm-monorepo/blob/main/misc/benchmarks/src/lockup/Benchmark.sol . The source `lockup/src/SablierLockup.sol` explicitly rejects ERC721 owner-to-owner transfers for streams with `isTransferable=false`. The recipient NFT controls claims **only if it can be transferred**; the sender may still hold the cancellation option in cancellable streams. `cancel()` checks msg.sender==sender and returns unvested tokens to sender. Thus a stream is NOT a risk-free stream of future payments. Its value is a two-party, time-contingent option-like contract.

Source: https://github.com/sablier-labs/evm-monorepo/blob/main/lockup/src/SablierLockup.sol and https://github.com/sablier-labs/evm-monorepo/blob/main/lockup/src/interfaces/ISablierLockup.sol . Sablier entered maintenance mode in July 2026 without halting its immutable onchain stream contracts: https://blog.sablier.com/sablier-labs-is-entering-maintenance-mode . Do not infer a spike in demand or a listing discount from maintenance status.

**Novel economic thesis:** if a buyer legally buys a receivable NFT from a cash-constrained recipient while the stream creator retains cancellation power, buyer is purchasing *the vested/expected stream payments minus a callable-receivable risk*, not a fixed-maturity bond. The value of the sender's later **renunciation of the cancel option** may exceed any token-price move. A bankable factoring price needs the actual accepted seller price, vesting schedule, cancellation right, withdrawal caps and recipient approval. Buyer can also purchase liquid token now and lock finance for same term; that is a strong baseline. If the token has poor cash liquidity, finance risk may dominate rights value.

## 2. Ownership of a wallet as an asset: ERC-6551 token-bound accounts

Singleton registry Ethereum 0x000000006551c19487814612e58fe06813775758. Official code: https://github.com/erc6551/reference/blob/main/src/ERC6551Registry.sol . ERC-6551 ties a deterministic smart-contract wallet address to NFT collection/token ID with token-holder control, according to an implementation contract. An NFT can therefore confer **a bundle of wallet-held assets and permissions** rather than only the media/identity priced by a marketplace. This is not equivalent to simply adding ERC-20 tokens: ownership composition across ERC721 and bound accounts changes the feasible action set.

**High-level unusual hypothesis:** a legitimate publicly listed NFT that controls a token-bound wallet full of transferrable ERC20 or vesting rights may be worth more than its obvious NFT floor. The underlying assets could be accidentally omitted from the seller's ask. However, this is exceptionally vulnerable to adverse selection: previous owner can remove account assets before an NFT sale unless a purchase settlement requires asset commitments and simultaneously checks the wallet; the registered NFT may also have ownership cycles or restrictive account implementations. The official ERC-6551 standard explicitly warns that the asset set may change between listing and sale. Ownership of NFT is NOT an automatic right to execute arbitrary methods of an unrelated contract or move all assets. A weak registry scan or native ETH balance cannot prove profitable acquisition.

**Next actual gate** requires known existing NFT with deployed TBA, verified implementation `execute` and signer requirements, current buyer-usable NFT listing, full held asset enumeration/valuation and atomic inventory commitment. No such listing has been established here.

## Frozen public/free activity experiment

Only **Ethereum keyless** read-only JSONRPC; no Blockmachine API secret, zero authenticated RU. First verify historical deployed bytecode; three 950-block **noncontiguous** windows offset [200,32000,275000] from one pinned head on each source. Sablier: four exact event topics Transfer, CancelLockupStream, WithdrawFromLockupStream and RenounceLockupStream; classify NFT mint/burn vs actual owner-to-owner transfers; no fee inference from Transfer. ERC-6551 singleton registry: exact ERC6551AccountCreated event; extract implementation, chain, NFT, account. Earliest up to four distinct event transaction receipts per family and native ETH at creation for TBA as a bounded wallet existence check. Every raw request/response SHA preserved.

An event is only **activity**. Contract bytecode is only existence. A zero in 950 blocks is a bounded negative, not evidence the protocol or asset class is inactive. All future economic screens must use a real actionable purchase offer or explicit fee, and a competent market-value baseline. Never buy, sign, submit, contact providers/counterparties or spend new subscriptions as part of this research.

## Broader cross-disciplinary search

These two are components of a larger mechanism family: **transfer control of a self-contained balance sheet or a path-dependent liability**, rather than transfer one asset. Time can be an explicit contract option (Sablier), and ownership hierarchy can be nested (ERC6551). Combining them could in principle transfer a wallet that contains a streaming entitlement, but no such joint instrument was observed here and chain of custody must be verified. Combining nonexistent offers does not create QT surplus.

Cheap independent non-TBA third route: ENS .eth expired names with 90-day grace and a 21-day decaying premium. There is a real legal purchase right after expiration, but the profits depend on *end-customer legitimate demand* rather than protocol reimbursement, and expired high-reputation names can raise trademark/identity harms. It is NOT an automatic trading-income source and not part of this bounded chain scan.
