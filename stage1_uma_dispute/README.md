# Programme III Stage1 — Earn for correcting a false claim

**Novel value transfer**: UMA Optimistic Oracle V3 requires an assertion proposer to post a bond, and permits an eligible challenger to post a corresponding bond. If the assertion is disputed and determined false, the disputer receives both bonds minus an oracle fee. Unlike DEX mispricing, the edge would be identification of an objectively false claim before challenge expiry. This is risk-bearing, not a flashloan/free-capital trade. Capital is locked and may be completely lost.

Primary Solidity source: https://github.com/UMAprotocol/protocol/blob/master/packages/core/contracts/optimistic-oracle-v3/implementation/OptimisticOracleV3.sol

**Official empirical source**: UMA's subgraphs monorepo publishes OptimisticOracleV3 assertion records with amount, token currency, expiration, disputer, settlement recipient and settlementPayout, across Ethereum, Polygon, Arbitrum, Base. No bearer key or Blockmachine RU needed:
https://github.com/UMAprotocol/subgraphs/blob/master/packages/optimistic-oracle-v3/schema.graphql
https://github.com/UMAprotocol/subgraphs#optimistic-oracle-v3-events

## Frozen screen

- Four public Goldsky endpoints documented by UMA.
- Three non-exhaustive cohorts each: latest 120 by assertion block, 2026Q1 first120 by most recent assertion block, 2026Q3 first120 likewise. 12 total non-mutating public GraphQL queries.
- No selection on dispute success, payout or profitability; each record has its own unique assertion ID. Dedupe latest overlap with quarterly observations.
- Classify settled winner from observed recipient, disputer/asserter, bond, payout. A winning disputer's *gross same-token principal adjustment* = settlementPayout - originally posted bond, unpriced token raw units. A losing disputer's loss = -posted bond. Settled uncontested assertions never count as disputed income. Unsettled remain unresolved.
- Complications: third-party funding of disputes, escalation-manager restrictions and invalid challenges, payout trace vs subgraph calculation, finality of voting, token decimals/market cash exit, real gas, collateral tied up, ethics/eligibility, and time-to-discovery. Do not claim annual incidence or our own earnings from historical third-party records.
- If many windows are full (120 records), selection is truncated: do not infer full population or recurrence rates.
- No transaction signing or broadcast, no disputes initiated, no zero-risk claims, no unethical false assertion fabrication, no scraping beyond 12 declared requests.
- Stage 2 promotion needs publicly verifiable false assertions, accessible challenge rights, strong causal evidence that truth can be determined before challengers, high success probability, collectible cash after fees, sufficient frequency, and capital/risk discipline.

Novel **portfolio link**: oracle challenge income, if viable, should be uncorrelated with liquidation spreads in normal markets; test event clustering and same stress dates first, never add independent pseudo-counts. Similarly protocol rule/expiry windows could create payouts without asset mispricing, but do not predefine their profitability.
