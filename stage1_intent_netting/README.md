# QT Stage 1 — independent multi-order atomic intent netting

UniswapX BaseReactor implements executeBatchWithCallback, where _prepare
pulls *all* signed order inputs to the fill contract before reactorCallback,
and _fill subsequently transfers required output token amounts. As a
consequence, a pair of opposing, simultaneously valid fillable signed
orders may clear inside a common token inventory with no external DEX
swap and no principal. This is a NEW mechanism combining compatible claims
across orders, not single-order DEX arb or past liquidation analysis.

For inputs A: x units token X, output y of Y; B: z units token Y,
output w of X, potential self-clearing necessary condition is
x >= w and z >= y, after fee-output obligations. For 3-asset cycles,
sum token by token; no nominal USD conversion or unit comparison across
different token decimals. Must keep each full order with fee outputs.

**Predeclared free-data snapshot:** public UniswapX /v2/orders
filter chain=Ethereum Dutch_V2 and Base Dutch_V3, status=open, 50 newest
each, four snapshots ~15 seconds apart. Parse typed JSON only; examine
all opposing single-output pairs and distinct-token triple cycles,
using min(start,end) inputs and max(start,end) ALL output amounts. Save
bounded original GET and response SHA. Rate <=0.5RPS, well under
Uniswap filler documented 4RPS limit. No API key needed and no Blockmachine RU.

This screen is deliberately NOT a cash-profit proof: no oracle pricing,
nonce revalidation, exclusivity expiry, signed-byte contract verification,
simultaneous fill, real gas, competition or swapper availability. Even
a strongly-positive token residual is merely a necessary inventory
envelope. Historical winning fills and these snapshots must never
be added to expected portfolio income without unique opportunities and
live inclusion evidence.

Official refs:
https://developers.uniswap.org/docs/liquidity/uniswapx/filling/overview
https://developers.uniswap.org/docs/liquidity/uniswapx/filling/faq
https://github.com/Uniswap/UniswapX/blob/main/src/reactors/BaseReactor.sol
https://github.com/Uniswap/uniswapx-service/blob/main/swagger.json

No trade, no wallet, no secret, no POST/order API calls, no retry on
403/429, no re-running empirical requests on PR synchronize.
