# US Treasuries Dashboard design principles

Two goals decide every layout and copy choice: **usability** (a rates practitioner gets the answer in the order they
ask for it, with no hunting) and **elegance** (every element earns its place, and the screen stays calm).

Four rules make those goals testable. A change that breaks one of them is a regression.

## Rule 1. No unused space

A blank region inside a card, or beside a shorter card, is a defect.

| Situation | Rule | Where applied |
|---|---|---|
| Two cards share a row and one is taller | The chart in the shorter card grows to the row height (`.stretch` + `.chart-box.grow`). | Curve beside attribution; policy path beside the Fed's dashboard |
| A list sits beside a fixed-height partner | The list card stretches and scrolls inside (`.fill .scroll`), never the page. | Headlines beside the slope chart |
| A short table beside a long one | Stack the short tables in one column (`.stack`) so the column heights match. | Bills and buybacks beside coupon results |
| A long table of narrow columns | Split it into side-by-side panels instead of stretching five columns across 1,300px. | Macro scorecard (two panels) |
| A news list across the full width | Two text columns (`.news.cols`), so lines stay readable and the card stays short. | Debt management news, Fed communication |
| A panel with nothing to show | Don't render the panel. Collapse it to one line of muted text inside a neighbor. | Claude's read collapses to a note in the story header when it isn't configured |
| Stat tiles | Four tiles per row at most; never a row with one widow tile. | Supply and Fed tiles |

## Rule 2. Practitioner-centric flow

Each screen reads top to bottom in the order a fixed-income PM asks questions:

1. **Where are we?** The market strip above every tab: 3M, 2Y, 5Y, 10Y, 30Y levels with 1-day changes, 2s10s,
   5s30s, 10Y real, 10Y breakeven, fed funds and the odds for the next FOMC.
2. **What happened to the curve?** The executive summary is three to five sentences, ready to paste to a head of
   trading. The first reads "Treasuries sold off with a bear-flattening bias on rising inflation concerns, driven by
   an oil shock"; the second says why that driver matters for this part of the curve; then the numbers and what is
   next. Beside it, the key moves with their size in σ. The detail lives in the narrative below the curve. The
   collapsible tape underneath gives the numbers: a headline with the size
   of the move in σ and in history ("2Y +134bp (1.5σ), largest 1-year rise since Sep 2023"), the 10Y level in
   context ("highest since Jul 2007"), and whether real yields or breakevens did the work. Then the tape (rates and
   cross-asset, each with its σ) and up to four bullets: Priced, Drivers, Cross-asset and Surveys. Surveys appear only
   when a survey printed inside the window, with its change over the window. Moves under 1σ are called noise and
   pointed back to the 1-year regime.
3. **Show me.** The yield curve today versus then, the bp change by tenor, and beside it the numbers: the 10Y move
   split into growth and the Fed (real yield) versus inflation expectations, price impact, shape and spreads.
3b. **The narrative**, directly below the curve: what happened, what the curve is pricing, whether surveys back it,
   the long view, and the pain trade.
4. **Tell me the whole story.** The full story: five chapters (the long view, what happened, what the curve says,
   checking the thesis, what would change the story), key numbers, risks and three story cards.
5. **How does it compare?** Every window (1D to 1Y, plus a custom date) on one table. Selecting a row reloads the page.
6. **Prove it.** The survey check (business and consumer surveys against their averages since 2000), the dated
   timeline of the window, then the macro indicators with release lags respected.
7. **Sources.** Verified headlines tagged by theme, and the slope history.

**Story first.** Bond yields are anchored on what is happening in the economy, so every window is told as a story
about the economy: events and data, local and global, then what the curve's shape says investors expect, then a
check against what businesses and consumers report. Model jargon stays out of the story. Numbers appear where they
carry the story (oil from $60 to $96, factory outlook 53 against an average of 32), not as decompositions.

**Interpretation scales with the window; the layout does not.** Up to 2 years the story is the current one, built
from the data and verified news in the window. From 2 to 20 years it is told through the episodes in between (COVID
lockdowns, the inflation shock, the AI investment boom). Only at 20 years or more does the secular story lead: four
decades of falling inflation and rates, now being tested. The cards, section labels and order stay the same in every
mode; only their content adapts.

**Same layout for every window.** 1D, 1W, 1M, 3M, 1Y and custom dates render identically: one thesis template, the
same five summary bullets and five chapters with fixed labels, three key-number lines, at least one risk and three
story cards.

Supply and Fed follow the same summary-first pattern: tiles, then the decision table, then context, then sources.

Supporting rules:
- Numbers lead and words explain. Each claim in the story carries the figure behind it.
- One color grammar on every screen: red pushes yields up (bear), blue pushes them down (bull), gray is neutral.
  Series colors (today, then, a third period) never carry direction.
- Basis points for changes and percent for levels, everywhere, in tabular figures.
- Dates carry the year only when it isn't the current year.
- Defaults are the ones a PM asks for first. The curve tab opens on 1Y, the window where macro themes show.

## Rule 3. Every number explains itself

A number the reader has to decode is a defect.

- **Every number has a source on hover.** Hovering any figure shows its publisher and series, how US Treasuries Dashboard
  transformed it (for example, year-over-year or the prior-six average), its reading date, and a link to the original.
  Numbers inside sentences take the source named closest before them. Charts carry a source line and a source footer
  in their tooltips. Implementation: `static/sources.js`.
- **Date every reading.** Market levels name their close ("Oct 14, 2026 close"). Economic data names the period it
  covers ("3.7% (Sep 2026)").
  Changes name both ends ("Oct 14, 2025 → Oct 14, 2026").
- **Say what a number means.** Market-implied figures are translated: "+8.5bp" becomes "34% chance of a 25bp hike
  (+8.5bp = 34% × 25bp)", "+68bp" becomes "about 2.7 quarter-point hikes", and "+15bp vs last auction" becomes "should
  clear at a higher yield".
- **Show the computation.** Every computed number shows its arithmetic on hover, under "Calculation", above the
  source: an average lists every input with its date and the sum ("(2.53 + 2.64 + … ) ÷ 6 = 2.65"); a spread shows
  both legs; a Strong / In line / Soft result shows the auction rate, the market yield that day, the security's usual
  gap and the rule. Every theme verdict says which part of the curve moved and whether it moved as the story predicts.
- **Identifiers are searchable.** Every auction shows its ISIN (US + CUSIP + check digit); click to copy.
- **Label in place, details on demand.** Each auction is one row (date, security and ISIN, size, market yield, vs last
  auction, last result vs market) so the whole calendar fits on one screen; clicking a row opens its full detail.
- **Charts print their values.** Yields on both curves, bp on every bar, the latest values on lines, and percentages
  inside the award-mix and probability bars with a text line underneath.
- **Units everywhere.** bp for changes, % for levels, pt for percentage-point changes in economic data, $bn for sizes.

## Rule 4. Clean and elegant

Research behind this rule: Tufte's data-ink ratio (every bit of ink should carry data), Stephen Few's two steps
(remove non-data ink, then emphasize the data that matters), Refactoring UI's hierarchy by de-emphasis and constrained
scales, and Matthew Ström's point that density is about information over time, not crowding. Applied as:

- **One spacing scale** (4, 8, 12, 16, 24, 32, 48px) and **one type scale** (11, 12.5, 14, 16, 20, 24px), as CSS tokens.
- **Hierarchy by de-emphasis.** Section titles are quiet; labels are small uppercase grey; the data and the story carry
  the weight. Three text tones only: ink, secondary, muted.
- **Hairlines, not boxes.** Tables have no header fills or zebra stripes; cards have one 1px border and no shadow.
- **Invisible until asked for.** Source and calculation cues appear on hover; the data status collapses to one line;
  the cross-asset tape and auction details open on demand.
- **Color carries meaning only.** Red for yields up, blue for yields down, ink for interactive states; neutrals are
  warm paper and white.
- **No repetition.** The executive summary says it once; the narrative gives the detail; the deep dive holds only
  what the narrative does not.

- **Type.** IBM Plex Sans for UI, IBM Plex Mono for every number, and Source Serif 4 only for the story headline
  and theme titles. The serif marks the part that is meant to be read rather than scanned.
- **Chrome.** One hairline border per card and no heavy shadows. Uppercase labels are reserved for section labels
  and table headers.
- **Color.** A cool slate neutral with one navy accent. Bear and bull hues are validated for color-vision deficiency
  in both themes. Dark mode is designed, not inverted.
- **Restraint.** No gauges or scores that suggest more precision than the method has. Where the data is thin, the UI
  says so ("model data lags this window", "no new release in the window").
- **Copy.** Plain sentences a PM could repeat. No hedging filler, no jargon the reader has to decode.
