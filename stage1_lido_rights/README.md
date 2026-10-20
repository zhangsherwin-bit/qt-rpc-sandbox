# QT Stage 1: transfer of delayed Lido ETH withdrawal entitlement

New research family, not a recycled Convex or generic swap search. Lido WithdrawalQueueERC721 at Ethereum 0x889edC2eDab5f40e902b864aD4d7AdE8E412F9B1 represents an ETH claim as an ERC721 unstETH request token.

**Verified official access:** The *current NFT owner* may transfer the NFT and, after queue finalisation, claim ETH. It is not enough to see a request owned by someone else: we cannot redeem without acquiring the NFT or express authorisation. Lido docs explicitly state transferability; the withdrawal request is NOT guaranteed to receive staking rewards while waiting, and in unusual slashing conditions the eventual ETH payout may be lower.

Primary sources:
https://docs.lido.fi/contracts/withdrawal-queue-erc721/
https://help.lido.fi/en/articles/7858352-how-do-lido-withdrawal-nfts-work
https://lido.fi/how-lido-works/withdrawals

**Participants:** Seller owns queue NFT, seeks ETH now, alternative is hold and claim after finalisation or sell original stETH before requesting withdrawal. Buyer is an independent participant with ETH capital, needs legally sold NFT and must value settlement-risk/time/capital carry. Protocol owes claim ETH to current NFT owner; it does not pay a claim bounty to outsiders. Marketplace execution needs a signed executable ask, not mere ERC721 transfer.

**Economic possibility:** For one NFT with claim amount A, sell/ask P, queue duration Δt, gas G and adverse event loss L, buyer expected risk-adjusted net = E[claimable ETH] - P - G - funding/hedging costs - E[L] - taxes/marketplace fees. A hypothetical 0.02 ETH discount on 10 ETH for 24h is only hypothetical until both real P and expected claim value exist. Buying stETH and queueing it, or buying ETH spot, is the competent standalone baseline using the *same snapshot*, gas and carry. Do not call a positive raw gap alpha unless it beats that alternative with actual executable prices.

**Historical activity cheap test:** Six noncontiguous 160-block windows ending at tip offsets [200,19000,96000,300000,550000,900000], source contract's exact 4-topic ERC721 Transfer logs. Distinguish protocol mint, burn, self-transfer, nonzero third-party transfer. For up to six earliest nonzero transfer TXs: verify successful actual Ethereum receipt, owner status of the exact request at end of transfer block and submitted fee (tx gas). A transfer **is not a sale**: it could be a wallet migration, gift, escrow or OTC settlement. An ownership transfer plus unrelated ERC20 transfer in same receipt is not sufficient to price an NFT purchase either.

**Missing decisive evidence:** Current live signed ask executable by ordinary buyer, unique token ID and current owner's signature, the amount/claim status from the same time and realistic net ETH after delay; and a comparable stETH-to-ETH immediate route. Without active offers, observed transfers only prove use of the rights interface, not discount or realizable profit.

**Scope:** one read-only GitHub PR-open RPC test, max **135 conservative RU** and **1,500-RU account reserve**, no wallet or authenticated exchange access, no signing, no offers submitted, no contract mutation, no main merge. Method-weighted throttle inherited from qt_rpc and original response bytes/checksums archived. Later synchronize runs offline regression ONLY.
