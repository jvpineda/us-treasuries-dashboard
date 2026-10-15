# US Treasuries Dashboard, reviewed by a UST portfolio manager

October 14, 2026. A review of the dashboard as it stands, written from the seat of a Treasury PM using it before the
open. Examples quote today's screens.

## Verdict

**A strong explainer, not yet a decision tool.** It answers "what happened and why" better than most sell-side
morning notes. The story is dated, sourced and split into Fed path versus term premium. It does not yet answer the
three questions that drive a trade: where is the value, what is priced versus what I think, and what is the
positioning and supply risk into the next catalyst. The recommendations below close that gap, most with free data.

## What works

- **Attribution a PM can repeat.** "+58bp expected short rates, +63bp term premium; +111bp real, +5bp breakeven" is
  the right first cut of a 116bp 10Y move, and every number links to its source.
- **The front-end read.** "The 2Y went from 64bp below the fed funds midpoint to 95bp above" is the cleanest single
  statement of the repricing, and it is the line I would put in my own note.
- **Honest data handling.** Release lags are respected, "no new reading in the window" replaces fake changes, and
  model gaps are labeled instead of hidden.
- **Auction setups.** "Trades 15bp above the last auction; last time dealers took 17% vs 11%" is the right framing
  for the 20Y reopening on Oct 21.

## Critique

### 1. It explains the move but never says where the value is
Everything on the Curve page is a change. There is no carry, rolldown, forwards or relative value. Today the 20Y
(5.57%) yields more than the 30Y (5.52%), the usual 20Y kink. The chart shows it, but nothing flags it as a
cheap/rich point. 5s30s flattened 50bp over the year, and nothing says whether that is stretched.

### 2. "Fed path" is mislabeled
Kim-Wright's expected-rate component is the **average expected short rate over ten years**, not the FOMC path over
the next year. A reader sees "Fed path +58bp" next to "2Y +134bp" and will conflate the two. Kim-Wright is also one
model with a weekly lag, so the 1D and 1W windows show "n/a" exactly when a trader wants it most.

### 3. Market pricing is never compared with the Fed's own guidance
Futures price +83bp of hikes through September 2027. The September SEP reportedly signals about one more hike. That
gap is the central trade in the front end today, and the dashboard doesn't show it. Neither does it show how far
Fed speakers have moved, beyond a headline count.

### 4. "Surprise" is measured by counting headlines
"14 hotter vs 12 cooler headlines" is not how a desk measures surprise. What matters is the print versus consensus
and how the curve reacted on release day. Headline counts track coverage, not shocks.

### 5. The auction monitor lacks the one number every desk watches
There is no tail: the stop versus the when-issued yield at 1pm. "Trading now" is a fitted par yield, not the CUSIP
being reopened. Strong/Soft is built from bid-to-cover, indirect and dealer shares only. The calendar covers about a
week, so there is no view of next month's supply, net new cash or the bill share of issuance.

### 6. No positioning or flows
Nothing on who owns duration and who is short it: leveraged funds' futures shorts (the basis trade), asset-manager
longs, primary dealer inventories, foreign official holdings at the Fed. In a selloff driven by term premium,
positioning is often the swing factor.

### 7. No risk or volatility layer
MOVE was dropped. There is no implied vol, swap spreads, on-the-run/off-the-run spread or liquidity gauge, so
nothing warns when the market is fragile.

### 8. Levels have no history
The 10Y real yield at 2.84% and term premium at 1.07% are extreme by recent standards, but the screen doesn't say how
extreme. Only the 10Y gets a percentile, and only against one year.

### 9. Themes rank attention, not causality
Three themes are all "priced" through the same term-premium move: Fed independence, the global selloff and
oil/Iran. The test cannot tell them apart. Contradictions go unremarked: oil is the top theme, yet 10Y breakevens
moved only +5bp over the year. That says the oil shock worked through the Fed path, not long-run inflation
expectations, and the story should say so.

### 10. Nothing translates the move into P&L
A PM thinks in DV01 and portfolio return. The 116bp 10Y move is roughly an 8–9% price loss on a 10-year note and
about 6–7% on a typical Treasury index. None of that is on screen.

### 11. Fragile inputs, no health status
Fed pricing comes from Yahoo's unofficial endpoint, and themes come from Google News RSS. If either breaks, a tab
goes blank with no warning. There is no per-source "as of" status bar.

### 12. No workflow hooks
There are no alerts (FOMC odds crossing 50%, a soft auction), no exportable morning brief, and no "what changed
since yesterday's story".

## Recommendations

Ordered by value per unit of effort. **Free** means public data the app can fetch today.

| # | Recommendation | Why it matters | Data | Effort |
|---|---|---|---|---|
| 1 | **Value panel**: carry and rolldown by tenor, the 1-year forward curve vs today, and butterflies (2s5s10s, 5s10s30s, 10s20s30s) with 1-year z-scores. Flag kinks such as 20Y over 30Y. | Turns the screen from "what happened" into "where to be". | Free (Treasury par curve) | Medium |
| 2 | **Rename and back up the split**: "expected short rates (10Y average)" instead of "Fed path"; add the NY Fed ACM term premium (daily) beside Kim-Wright; keep 2Y−EFFR as the front-end measure. | Fixes a misleading label and fills the 1D/1W gap. | Free (NY Fed ACM) | Low |
| 3 | **Market vs Fed**: plot the SEP median dots against the futures path, and show the gap by year-end. | The front-end trade in one chart. | Free (Fed SEP) | Low |
| 4 | **Event-day attribution**: how much of the window's move happened on CPI, payrolls, FOMC and auction days. Add the Cleveland Fed inflation nowcast vs the actual print. | Replaces headline counting with market reaction, which is what "surprise" means to a desk. | Free (BLS/BEA calendars, Cleveland Fed) | Medium |
| 5 | **Auctions v2**: CUSIP-level prices for the issue being reopened; a "stop vs prior close" proxy until a when-issued feed exists; a full month of supply parsed from Treasury's tentative schedule; net new cash per week; bill share; Treasury General Account balance. | Gets the auction read closer to the tail desks trade on, and shows the supply wave ahead. | Free (TreasuryDirect FedInvest, Daily Treasury Statement); when-issued yields are paid | Medium |
| 6 | **Positioning and flows**: CFTC Traders in Financial Futures (leveraged vs asset-manager positions by contract), NY Fed primary dealer positions, Fed custody holdings for foreign official accounts (H.4.1), TIC monthly. | Shows who is forced to sell into a selloff. | Free (CFTC, NY Fed, Fed, Treasury) | Medium |
| 7 | **Levels in context**: percentile ranks over 1, 5 and 20 years for 2Y, 10Y, 30Y, the 10Y real yield, breakevens, term premium, 2s10s and 5s30s. | Says whether a level is extreme, not just whether it moved. | Free | Low |
| 8 | **P&L translation**: price change and DV01-based P&L for each tenor and for a benchmark-duration portfolio over the window. | Speaks the PM's language. | Free (computed) | Low |
| 9 | **Sharper themes**: give each theme its own market fingerprint (Fed independence: 5y5y and gold; global selloff: UST-JGB and UST-Bund spreads; AI capex: IG issuance and semis; oil: 1-year breakevens). Add a "tensions" line when the story and the data disagree. | Lets the story say which theme actually moved rates. | Mostly free | Medium |
| 10 | **Risk layer**: bring MOVE back with a percentile; add on-the-run/off-the-run spreads; add swap spreads when a feed is available. | Warns when liquidity is thin. | MOVE free; swaps paid | Low to medium |
| 11 | **Data health bar**: per-source status and "as of" time, with fallbacks and a visible warning when a feed fails. | Trust in every number depends on it. | n/a | Low |
| 12 | **Workflow**: alerts on thresholds, a one-click morning brief (PDF or email), and "what changed since yesterday". | Makes it a daily habit rather than a page to visit. | n/a | Medium |

### Suggested sequence

1. **This week:** 2, 7, 8, 11. These are labels, context and trust, all low effort and high credibility.
2. **Next:** 1, 3 and 4. Value, market vs Fed, and event-day attribution are what turn it into a decision tool.
3. **Then:** 5 and 6 for supply and positioning, then 9, 10 and 12.

### What would need paid data

When-issued yields (for true auction tails), swap spreads and OIS, consensus forecasts for each release, and
intraday prices. Bloomberg, Tradeweb or ICE would cover all four. Everything else above is public.
