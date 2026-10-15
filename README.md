# US Treasuries Dashboard

A local US Treasuries desk. It explains every curve move as a story about the economy: what happened, what the
curve's shape says investors expect, and whether business and consumer surveys back it. It
also covers coupon supply with demand reads and meeting-by-meeting Fed pricing.

- [DESIGN.md](DESIGN.md): the principles (usability and elegance; no unused space, practitioner-centric flow, clean)
- [REVIEW.md](REVIEW.md): the screen-by-screen review of v1 and what v2 changed
- [CRITIQUE.md](CRITIQUE.md): a UST portfolio manager's critique and recommendations
- [TREASURER_REVIEW.md](TREASURER_REVIEW.md): a global-bank treasurer's review, and what it changed

## Run

```bash
python3 server.py --open
```

### Published site

A static copy is published to GitHub Pages by `.github/workflows/pages.yml`. It is rebuilt twice on every US Treasury
trading day: about 8:50am New York time, after the 8:30am economic releases, and about 6:30pm, after the close once
Treasury has posted the day's curve. Weekends and SIFMA bond-market holidays are skipped (`trading_day.py`). It also
rebuilds on every push to `main` and on demand from the Actions tab. `build_static.py`
computes every API response once and saves it under `site/data/`; the page reads those files when `config.js` marks
it as static. The published site covers the preset windows (1D to 1Y). Custom dates and Claude's sourced read need
the local server.

It opens http://127.0.0.1:8765. It uses only the Python 3.10+ standard library, so there is nothing to install.
Set `PORT` to change the port.

### Optional: Claude's sourced read

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python3 server.py
```

The story header then shows "Ask Claude for a sourced read". Claude receives the computed story and evidence,
checks it with web search restricted to verified outlets, and writes the narrative with citations. The default model
is `claude-opus-5-5`; override it with `CLAUDE_MODEL`. Each window is one API call, and results are cached in
`.cache/ai/`.

## The executive summary (`report.py`, with `tape.py`)

A short report in complete sentences, ready to paste to a head of trading ("Copy summary" copies it as plain text):
a bottom line, then The move, Monetary, The economy, Fiscal and global, and The read (cross-asset and what is next).
Short windows under 1σ get a short report that says so and restates the 1-year picture. Windows over two years are
told through their chapters, where we are now and the fiscal backdrop. The tape below it (collapsed by default) shows
every move with its size in standard deviations:

- **Size in σ.** Every move is divided by the asset's own realized volatility: the standard deviation of daily
  changes over the 252 trading days before the window (FRED H.15 for rates, Yahoo for cross-asset), times √(trading
  days in the window). Under 1σ is Noise, 1–2σ Notable, 2–3σ Big move, over 3σ Extreme. Noise windows say so and
  point back to the 1-year regime.
- **Size in history.** "Largest 1-year rise in the 2Y since Sep 2023": the most recent window of the same length,
  ending before this one, with a move at least as large (H.15 daily since 1976). Shown only when it is long ago.
  Levels too: "10Y highest since Jul 2007".
- **Priced.** Next FOMC odds and the hikes or cuts priced through the last listed meeting; the change in pricing over
  1W and 1M windows; for longer windows, the 2Y against fed funds at both ends.
- **Drivers.** Only what happened inside the window: CPI and jobs releases, oil, AI capex prints, Fed decisions, JGBs,
  and the news themes most tied to rates.
- **Cross-asset.** S&P 500, DXY, WTI, gold, VIX and MOVE with their σ, read as a regime: stocks up with yields is a
  growth-led selloff (good news is good news); stocks down with yields up is a rates shock (good news is bad news);
  both down is risk-off; yields down, stocks up is goldilocks. A weaker dollar with higher yields is flagged.
- **Surveys.** Only surveys that printed inside the window, with their change over it and their average since 2000.

## How the narrative is built

Bond yields are anchored on what is happening in the economy, so the story (`narrative.py`) always runs in this order:

1. **The thesis.** What the curve did, what its shape says investors expect, the economic story behind it, and
   whether surveys back it. Example (1Y, Oct 14, 2026): yields rose most at the short end, so investors expect the Fed
   to keep rates high to cool an economy running hot. The story behind it is an AI investment boom, an oil shock and
   a Fed back to raising rates. Business surveys confirm it, but consumers are gloomy.
2. **What happened.** Events and data in causal order: AI and business investment, energy, inflation, jobs, the Fed,
   the rest of the world. Short windows add what verified news tied to rates, and sit inside the bigger story.
3. **What the curve says.** The shape read as expectations (`EXPECT`): a bear flattener means a Fed leaning against
   a hot economy; a bear steepener means optimism about growth or worry about inflation and deficits; a bull
   steepener means expected cuts, either optimistic (a soft landing) or pessimistic (a weakening economy), and the
   surveys decide which; a bull flattener is pessimistic. The TIPS split says whether the move is growth and the Fed
   (real yields) or inflation. Each shape also has a read on the AI investment story.
4. **Checking the thesis.** Business and consumer surveys and investment data, each against its average since 2000:
   Philadelphia Fed six-month outlook and capex plans, core capital goods orders, investment in computers, software
   and data-center equipment, University of Michigan sentiment and inflation expectations. For a hot or strong
   economy, two-thirds of the business measures above average confirm it, one-third partly confirms it.
5. **What would change the story.** Risks tied to the thesis, then the next FOMC and coupon auctions.

The three story cards are the AI investment boom (the major story now) plus the two themes verified outlets most
often tied to rates in the window, each tested against the part of the curve it should move.

Verified outlets: Reuters, Bloomberg, WSJ, FT, CNBC, MarketWatch, Barron's, AP, NYT, Washington Post, The Economist,
Axios, the Federal Reserve, Treasury, the New York Fed, CBO, BLS, BEA and CME Group.

## Supply metrics

The four tiles at the top of the Supply tab are the supply numbers desks watch:

| Metric | What it measures | Source |
|---|---|---|
| Net new cash | Announced offering amounts minus publicly held securities maturing on the same settlement date. A paydown returns cash to investors; a raise drains money markets. | TreasuryDirect |
| Duration supply ahead | Coupon auctions ahead in 10-year equivalents (size × modified duration ÷ 10Y duration); unsized auctions use the last equivalent size, marked "est." | TreasuryDirect, Treasury par curve |
| Bills share of marketable debt | Bills ÷ total marketable debt, now and a year earlier, against TBAC's long-standing ~20% norm | Monthly Statement of the Public Debt (Fiscal Data) |
| Coupon auctions vs market | How many of the last 10 coupon auctions were strong or soft against the market, and which ones | TreasuryDirect, Treasury par curve |

**Strong and Soft are judged against market expectations.** Desks measure an auction by its tail: the stop versus the
when-issued yield at the 1pm deadline. When-issued yields are not free, so the dashboard uses the same maturity's par
yield at that day's close and removes the security's usual gap to the fitted curve:

    read = (auction rate − same-day closing yield) − average of that gap over the security's prior six auctions

At +2.0bp or more the auction priced cheaper than the market expected (Soft, it tailed); at −2.0bp or less it priced
richer (Strong, it stopped through). 2bp is about one standard deviation of this read across last year's coupon
auctions. Without a same-day yield, demand decides (bid-to-cover, dealer take-down and indirect share vs the prior six).
Every result shows the full calculation on hover.

Each auction is one row with its ISIN (US + CUSIP + ISO 6166 check digit, click to copy); clicking a row opens the
detail. The Bills, Notes and Bonds sections collapse and expand, and a "Jump to" bar opens any coupon auction.

## Long windows: episodes and the secular story

| Window | Told as |
|---|---|
| Up to 2 years | The current story, from the data and verified news in the window |
| 2 to 20 years | The episodes in between, each a shock to the economy (COVID lockdowns, the inflation shock, the AI boom) |
| 20 years or more | The secular story (four decades of falling inflation and rates, now being tested), then the episodes |

- **Episodes** (`narrative.EPISODES`) are dated history through 2025, each told as cause, economy, Fed, yields. The
  chapter after 2025 is described only from the data (AI investment, oil, inflation, Fed moves).
- Over long windows the net shape is history, not a forecast: "what investors expect" comes from today's chapter.
- **Turning points.** The 10Y path is split at turning points (zigzag of 150bp for 20-year windows, 75bp for 2 to 20
  years, 20bp daily under two years). Each is labelled with its episode; under two years, with the story verified
  news focused on in those weeks.
- **Long-run anchor** (20-year windows only): the neutral real rate (NY Fed Laubach-Williams r*) plus expected
  inflation (Cleveland Fed), against the 10Y.
- **Ray Dalio's long-term debt cycle** (*Principles for Navigating Big Debt Crises*, *How Countries Go Broke*):
  monetary-policy regimes MP1 to MP3 classified from data, eight warning signals with evidence, and a stage call.

## Data sources

| Data | Source |
|---|---|
| Nominal and real par yield curves | home.treasury.gov |
| Auctions (upcoming and results) | TreasuryDirect TA_WS |
| Buybacks | Fiscal Data API |
| EFFR and target range | New York Fed |
| FOMC calendar, speeches, press releases | federalreserve.gov |
| Macro series, business and consumer surveys, investment, global 10Y yields | FRED (public CSV, no key) |
| 30-day fed funds futures, sector ETFs, gold | Yahoo Finance chart API (unofficial) |
| Headlines | Google News RSS, filtered to the verified list |
| Neutral rate (r*) | New York Fed, Laubach-Williams estimates (xlsx) |
| SOFR | New York Fed reference rates API |
| TGA balance | Fiscal Data, Daily Treasury Statement |
| Long history: yields, fed funds, recessions, debt, interest, holdings, dollar, Fed balance sheet, reserves, ON RRP, IORB | FRED |

## Limits

- Curve data is end of day. Headlines published after the last close are listed separately and are not counted
  as causes of the move.
- The TIPS curve is a fitted estimate. Auction reads use closing yields as a stand-in for when-issued yields.
- Surveys are monthly or quarterly; the latest reading can be one to three months old (each shows its period).
- Theme ranking reflects coverage volume in Google News' top results, which is a proxy for attention.
- Futures odds more than about 6 months out are indicative.
- Not investment advice.
