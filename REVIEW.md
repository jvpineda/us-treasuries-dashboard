# Screen review and revamp (October 2026)

A review of version 1 from two seats: a fixed-income PM using it before the open, and a UI designer. Each flaw is
paired with what version 2 does instead. The principles behind the fixes are in [DESIGN.md](DESIGN.md).

## The interpretation itself

| Flaw in v1 | Why it matters to a PM | v2 |
|---|---|---|
| The likely driver was a blend of a hard-coded prior and headline keyword counts | Not explainable. "Macro data 33%" can't be defended in a meeting. | The 10Y move is split two ways from published models: **expected Fed path + term premium** (Fed Board Kim-Wright) and **real yield + breakeven** (TIPS). The lead driver comes from that split. |
| No macro data, only headlines | "Why did yields rise a full point?" needs inflation, expectations and jobs, not keyword counts. | Macro scorecard (FRED): CPI, core CPI, core 3-month annualized, core PCE, core goods, wages, consumers' and 5y5y inflation expectations, GDP, payrolls, unemployment, claims, fed funds, term premium, deficit, global 10Y yields, oil, gasoline, mortgages. Values at the window start are what had been released by then, with no look-ahead. |
| No notion of surprise | A hot print moves rates; a high but expected one doesn't. | Release surprises are tallied from verified headlines ("hotter/cooler than expected", "beats/misses") for inflation, jobs and growth. |
| Sentiment gauges from keyword counting | False precision. | Removed. Direction is shown only where data supports it: the ▲/▼ push of each indicator on yields. |
| No story | "Bear flattener, monetary" is a label, not an explanation. | A story engine: headline, then the monetary chain (front-end repricing → inflation trigger → Fed actions), the fiscal and global chain (term premium → its theme), three real-economy themes, so what, catalysts and risks. |
| No link to the real economy | PMs explain rates through what is happening in businesses and households. | Nine themes (AI investment boom, AI disruption and the SaaSpocalypse, tariffs and the cost of living, oil and Iran, deficits and supply, job market, housing, global bond selloff, Fed independence). They are ranked by how often verified outlets cover them alongside rates in the window. Each top theme shows its real-economy gauge, its channel to the curve, and whether the curve actually priced it. |

Example, 1Y window to Oct 14, 2026. v1 said: *"Bear flattener. Most likely driver: monetary."* v2 says: *"Yields rose
about 113bp as two forces lined up: the market flipped from pricing rate cuts to pricing hikes, and term premium rose
63bp as long-end yields jumped worldwide, led by Japan."* It backs that up with the 2Y moving from 64bp below fed
funds to 95bp above, headline CPI 3.0% → 3.7% on oil at $60 → $96 while core eased, the Fed cutting 50bp then hiking
in September, Kim-Wright splitting the 10Y's +121bp into +58bp Fed path and +63bp term premium, and JGB 10Y yields
going from 1.65% to 2.94%.

## Curve screen

| Flaw in v1 | v2 |
|---|---|
| The verdict sat in a side panel under long tables; the answer was below the fold. | Flow is levels → moves → picture → story → evidence → sources. The story headline is the most prominent text on the page. |
| "Every timeframe" sat at the bottom; it is the overview a PM wants first. | The move matrix is the second thing on the page and is also the window selector. The 1D–1Y button bar is gone. |
| The 1D–1Y buttons and the bottom table duplicated each other. | One control: matrix rows plus a custom date field in the same card header. |
| No levels anywhere; you had to hover the chart. | A market strip on every tab. |
| The Claude card was half empty when not configured. | The card is gone. A one-line note sits in the story header; when Claude is configured, its read expands inside the story card. |
| The attribution side panel was taller than the chart card, leaving a gap. | The curve chart stretches to match its partner. |
| Change bars had odd ticks and no zero line. | Axis steps of 1, 2 or 5, always through zero, with an emphasized zero line. |
| No visual for the gap between the two curves. | Shaded area between today and then: red where yields rose, blue where they fell. |

## Supply screen (was "Auctions")

| Flaw in v1 | v2 |
|---|---|
| Bills drowned out coupons, which are the auctions that set term premium. | Coupons get the main table; bills sit in a compact side table. |
| No sense of where the next auction will clear. | "Trades now" (par curve, or the TIPS real curve) vs the last stop, so you see the concession at a glance. |
| Bid-to-cover had no context. | Every demand metric shows its average over the security's prior six auctions. |
| No verdict on results. | Each result is read as Strong, In line or Soft from bid-to-cover, dealer take-down and indirect share against history. The latest read appears in the tiles and in the story's fiscal evidence. |
| Columns clipped, names wrapped onto three lines, and the Docs column fell off-screen. | No-wrap security and date cells, short names, docs folded into the last column, compact side tables. |
| Short and long cards side by side left dead space. | Bills and buybacks stack in one column beside the results; debt news runs full width in two text columns. |

## Fed screen

| Flaw in v1 | v2 |
|---|---|
| Five tiles wrapped 4 + 1. | Four tiles: policy rate (with real rate), next FOMC, priced in about 6 months, priced in about 12 months. |
| Meeting rows printed the date twice. | Date, year only when it differs, and an SEP chip. |
| The meeting table clipped the "vs 1W / 1M" shift columns. | The meeting table gets the full width. |
| Pricing never connected to what the Fed reacts to. | "What the Fed is reacting to": core PCE, core CPI 3-month annualized, wages, unemployment, payrolls, expectations, the real policy rate, and how pricing shifted over the week and month. |
| Separate cards for coverage, speeches and releases. | One "Fed communication" card with three tabs, in two text columns. |
| Slopes, breakevens, real yields and MOVE were scattered in a "pulse" card. | Slopes, the 10Y real yield and the 10Y breakeven moved to the global strip; inflation expectations moved to the Fed's dashboard. MOVE was dropped because nothing on the screen used it. |

## Round 3: explainability audit

Every figure on every screen was checked for three things: whether it reconciles with its source, whether its date
is shown, and whether a reader can tell what it means without help.

| Found | Fix |
|---|---|
| The story sat below the curve and matrix. | The story is first on the Curve page, opening with an executive summary. The window selector lives in its header. |
| "FOMC Oct 28 +9bp" in the strip meant nothing on its own. | The strip shows "34% chance of hike", with the futures arithmetic in the tooltip. The Fed tab shows "+8.5bp = 34% × 25bp". |
| Futures-implied totals (+68bp, +83bp) had no scale. | Each is restated as quarter-point moves and as the expected rate vs today's 3.88%. |
| Economic readings had no dates in the story ("payrolls 51k a month"). | Every reading carries its data period, for example "3-month average to Sep 2026". Daily readings always carry the year. |
| Fed moves said "cut 50bp, then hiked" without dates. | Each move is listed with its effective date. |
| The 10Y attribution showed +121bp and +116bp with no explanation. | Each split is labeled with its own date range. Kim-Wright runs to its latest weekly reading (Oct 9), TIPS to the Oct 14 close. |
| The curve chart had no values on it. | Yields are printed on both curves, and bp on every change bar. Labels sit on the side away from the other curve. |
| The award-mix bar had no numbers. | Percentages are printed inside each segment, with a full text line underneath. |
| A theme was "Priced: 5Y breakeven +3bp" on a 116bp move. | Each component is tagged in line, barely moved or opposite, against a stated threshold (15% of the 10Y move). |
| A 3-Year Note read "Soft" while its shown reasons looked fine. | Every result shows all three inputs it is based on: bid-to-cover, indirect share and dealer share, each vs the prior-six average. |
| The auction monitor was a list of metrics with no point of view. | Bills, notes and bonds are separated. Each upcoming auction has three labeled panels (upcoming, market now, last equivalent auction with size, rate, bid-to-cover, award mix and result) and a one-line setup that says what to expect. |
| Bills were compared on discount rate with a bond-equivalent market yield. | Bills are compared on the investment rate, so both sides are bond-equivalent. The discount rate is shown alongside. |

Spot checks: gold −1.0% over the year ($4,163 on Oct 14, 2025 vs $4,120 now) is correct, despite a mid-year peak
near $4,575. The 1M bill −8bp (4.19% → 4.11%) matches the chart. The 3m10y spread of +1 → +91bp matches the 3M
(4.02% → 4.28%) and 10Y (4.03% → 5.19%) levels.
