# Stage 1 genuine new economic opportunity: "pay-first" creator fee claim

**Preregistered 2026-10-21 before inspecting activity; not a rebrand of UNI TokenJar.**

Uniswap's source-verified BuybackAndBurnClaimRecipient on Liquidity Launchpad first releases accrued pool fee assets to its caller; the BaseClaimRecipientWithCallback invokes IClaimExecutor.onClaimed; only AFTER callback does the contract transferFrom() a FIXED amount of that pool's launched token for permanent burn. Because cash is received first, an appropriately designed and permitted executor could purchase the burned token with the received native currency in a flash-financed atomic sequence, leaving a remainder. There may be no initial token inventory principal, unlike a "burn before receive" design; gas, approvals, slippage, and priority bid still cost money.

The source-driven inequality for a finite caller route is:
Native fee payout + token-side payout - minimum executable price of required fixed burn tokens - gas - venue fees - proposer/builder bid - any further native transfers > 0.

Source contract checks:
- https://github.com/Uniswap/liquidity-launcher/blob/main/src/periphery/BaseClaimRecipient.sol — claim uses _payout to msg.sender before _afterClaim.
- https://github.com/Uniswap/liquidity-launcher/blob/main/src/periphery/BaseClaimRecipientWithCallback.sol — mandatory callback onClaimed.
- https://github.com/Uniswap/liquidity-launcher/blob/main/src/periphery/BuybackAndBurnClaimRecipient.sol — minCurrency1BurnAmount required, transferFrom executor into 0xdead AFTER callback, native currency0 enforced.
- https://developers.uniswap.org/docs/liquidity/liquidity-launchpad/guides/buyback-and-burn
- https://developers.uniswap.org/docs/liquidity/liquidity-launchpad/deployments

**Frozen deployed tests (not exhaustive chains):**
Robinhood Chain mainnet chainId 4663 RPC https://rpc.mainnet.chain.robinhood.com; burn recipient 0xa1ba4CC12654D2b188e3ba77dc86c75cA47f1A4e.
Arc mainnet chainId 5042 RPC https://rpc.mainnet.arc.io; burn recipient 0x5cEe9852d136833aE26c9E36a96fC02Cdfc9C40C.

**Crucial chain semantic:** Arc's native currency is USDC rather than Ethereum ETH. The Solidity contract's use of Currency.ADDRESS_ZERO refers to the native asset of the particular chain; do not misprice an Arc payout as ETH because the source comments use "native ETH". Robinhood Chain native is ETH. Both sources must be priced in their real native units.

**Smallest first live-grounded question:** are these published contracts deployed and burning any token at all in representative intervals? Before quoting DEX routes, verify eth_chainId, bytecode, minCurrency1BurnAmount and exact TokensBurned event within three disjoint 450-block windows offset [250,15000,60000] from a pinned head, on both chains. GET/POST read-only public JSONRPC, <=19 requests, with SHA256 unmodified responses, no API key, no token purchases, no wallet, no transactions, no Blockmachine RU. Any endpoint denied or RPC error is MISSING evidence, not absence.

**Strong baseline:** existing Uniswap searcher documentation describes monitoring accumulated vesting/claim and burning against exact token costs. If this turns out profitable, a baseline ordinary searcher with complete route and gas evaluation should find it. Our conceptual transfer adds only the discovery of financing precedence across callback and native-currency semantic; do not claim an alpha edge unless stronger capture evidence separates it.

**Second gate only after live positive activity:** identify exact tokenId with source fee accounting, releaseable native/token assets in same block, finite executable onchain burn-token purchase route, callback implementation and approvals, gas simulation, direct block producer payments, and tight competitor inclusion. Previous QT Convex examples paid ~99% to block fee recipient, so assume zero advantage until actual retained own inclusion economics are known.
