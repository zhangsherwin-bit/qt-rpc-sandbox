# QT Stage 1 — Logical conversion of mutually exclusive claims

**2026-10-21, new mechanism (not a repeat of PR83 YES+NO single-condition pair).**

Official NegRiskAdapter: https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/docs/NegRiskAdapter.md

On a compatible Polymarket market of mutually exclusive questions, the publicly documented convertPositions action can convert m distinct NO positions of quantity q each into (m-1)*q collateral plus residual complementary YES tokens, subject to adapter fee and market configuration. This means a portfolio of **obligations** can be transformed into *immediate collateral*, not only eventual settlement payoff.

**Economic hypothesis:** buy m finite NO ask books at common contemporaneous size q; execute the on-chain conversion where legally/technically available. A necessary conservative pre-gas, pre-fee cash-surplus screen is (m - 1)q - sum(actual_ask_cost_i) > 0. We assign ZERO value to any remaining YES positions. This is NOT an independent arb until each NO asset belongs to exactly the same valid adapter market, the index set matches the chosen questions, fees and approval/allowances are known, conversion is available to ordinary actors, entire actual executable depth is aligned, and the residual survives gas/execution/settlement competition. If a question resolves ambiguously or the group is augmented, eligibility can fail.

**Participant economy:** NO sellers legitimately own positions and sell at binding asks; adapter allows token holders to unlock specific quantities of backing collateral while creating residual YES contingent claims. Searcher must finance NO acquisition (possibly atomically if supported), hold approvals, and compete to fill books and call conversion. Counterparty willingness is established only by live finite asks—not by metadata prices.

**Strong baseline:** a sophisticated CTF claim-composition solver given all the same questions, on-chain market IDs, positions and costs could identify precisely this conversion. Our old PR83 binary complete-set matching misses it because binary YES+NO within ONE condition is different. We simplify to native adapter conversion if it proves profitable; no need for a heavy new runtime.

### Bounded empirical screen

Only public read-only Polymarket Gamma GET and CLOB GET. Two pages of up to 100 active events, source-ordered by event ID, select first three Gamma event groups containing >=3 eligible negRisk=true binary YES/NO markets with CLOB tokens and orders accepted. Up to first four NO tokens/group. Fetch <=12 CLOB books and calculate exact ask-depth portfolio costs for q=10 or 50 shares across combinations of 2–4 NOs. Record request/response SHA256, requested URL and timestamp. Never substitute Gamma midpoint/last traded probability for an executable ask. Do not scan for groups until a positive result appears.

**Critical caveat:** Gamma event nesting is NOT verified identity of the same on-chain NegRiskAdapter marketId. These are candidate constraints only. If no groups are found or provider blocks requests, the result is UNRESOLVED for the wider market, not zero opportunity. If m-NO cash inequality passes, still need separate onchain adapter market identity/fee validation, non-augmented group rules, live book recheck and realistic transaction sequence; no trade now.

HTTP cap 14 read-only GET calls, <=1 call/1.6 sec, no auth, wallet, account secret, trades, live orders, Blockmachine RU or paid data. GitHub CI offline first and empirical only on PR opening; future sync offline-only. No external outreach. This is exploratory evidence, not annual recurrence. Binary YES+NO prior negatives and Convex 99% producer bid findings preserved separately.
