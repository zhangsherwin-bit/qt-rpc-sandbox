# Programme III Stage 1: contrarian sources of legitimately paid cash

Research date: 2026-10-19. Two independent new economic sources, neither rescues old liquidations nor assumes stablecoin USD parity. All experiments read-only. Do not interpret a historical winner's cash as our expected profit.

## A. Insure truth, not token prices (UMA optimistic-bond disputes)

UMA OptimisticOracleV3 uses a bonded truth claim with permissionless challenges unless an escalation manager restricts disputes. The successful asserter or disputer receives two bonds minus burn fee after DVM or escalation-manager resolution. Assuming disputer posted bond B, burned fraction f, and wins, its gain before gas and lockup is B*(1-f); when wrong the entire B can be lost. Bonds remain escrowed across challenge and adjudication: a flash loan cannot provide zero-capital financing. Settlement tx sender need not be the bond beneficiary.

Primary protocol source: https://github.com/UMAprotocol/protocol/blob/master/packages/core/contracts/optimistic-oracle-v3/implementation/OptimisticOracleV3.sol
Event ABI: https://github.com/UMAprotocol/protocol/blob/master/packages/core/contracts/optimistic-oracle-v3/interfaces/OptimisticOracleV3Interface.sol
Official deployments from packages/core/networks JSON: Ethereum 0xfb55F43fB9F48F63f9269DB7Dde3BbBe1ebDC0dE; Base 0x2aBf1Bd76655de80eDB3086114315Eec75AF500c.

Four 7000-block windows per chain, end offsets [200,25000,90000,280000]. Disputed and Settled events queried together; earliest 8 distinct disputed settlements per chain require getAssertion, burnedBondPercentage, ERC20 Transfer from the oracle to actual winner, and receipt gas. Missing transfers are UNRESOLVED. Distinguish payout token, contract-specific escalations, timestamps, bond in escrow, and risk of mistaken dispute resolution.

## B. Turn negative harvest tasks into a positive bundle (Convex CRV caller incentive)

The permissionless Convex Booster earmarkRewards(uint256) pays a caller a CRV fee (earmarkIncentive / FEE_DENOMINATOR; initial contract 50/10000 = 0.5%, may have been changed in later governance). Several isolated small claims may be negative after gas and conversion, but a multi-pool atomic batch could amortize fixed gas and one final WETH swap. This is potential **cost subadditivity**, not a higher stated APY.

Booster source: https://github.com/convex-eth/platform/blob/main/contracts/contracts/Booster.sol
Booster 0xF403C135812408BFbE8713b5A23a04b3D48AAE31
CRV 0xD533a949740bb3306d119CC777fa900bA034cd52
Uniswap V3 Quoter 0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6
Quoter interface: https://github.com/Uniswap/v3-periphery/blob/main/contracts/interfaces/IQuoter.sol

Four disjoint 7000-block windows on Ethereum. CRV Transfer from Booster census; earliest 12 distinct transactions selected without looking at outcome, proof only if direct Booster earmarkRewards transaction and CRV transfer to actual tx sender. Quote CRV->WETH at predecessor block via real Uniswap v3 0.3% pool, subtract recorded original transaction gas and an additional 170,000-gas planning allowance to convert CRV to WETH. This is still not an actual historical converted-cash transaction. Check qualifying original winners within six blocks for the necessary (not sufficient) possibility of batching; not a replay.

## C. Cheap anti-intuitive falsification: flash-staking does not claim unallocated historical income in this implementation

A hypothetical one-block flash stake after a long zero-total-supply period looks attractive. But Convex BaseRewardPool's rewardPerToken() returns the stored accumulator when totalSupply() == 0; its stake() updates rewards before increasing stake supply, and updates the timestamp. The new entrant therefore cannot claim historical unallocated rewards by minting at the same block. This is a source-level disproof for that contract, not for all designs.

Source: https://github.com/convex-eth/platform/blob/main/contracts/contracts/BaseRewardPool.sol

## Empirical budget and gates

Only Ethereum/Base read-only methods and no signer, wallet, broadcasting or executed positions. Source addresses and windows frozen. 12 log windows * 25 conservatively estimated RU = 300 RU, plus receipts, quotes, headers within strict 430RU attempt cap; monthly 1500 RU protected, 55% of provider per-minute cap. No automatic reruns on PR synchronize; original raw response and SHA retained. HTTP200 plus RPC JSON error does NOT equal success.

Even a third-party winning bond or above-gas caller reward cannot establish our independent real net profit. Stage2 requires recurrence, prewinner observability, own atomic counterfactual where applicable, cash exit and competitive inclusion.
