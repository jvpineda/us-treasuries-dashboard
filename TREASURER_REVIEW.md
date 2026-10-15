# US Treasuries Dashboard, reviewed by the Treasurer of a global bank

October 14, 2026. The Treasurer runs the bank's balance sheet: funding, liquidity buffers (HQLA), the investment
portfolio and interest-rate risk in the banking book. This review asks only whether the **market-facing** dashboard
gives that seat what it needs from the Treasury market. As agreed, no bank-specific view (balance sheet, NII or EVE)
was added.

## Verdict

**Useful for the "why", thin on the "so what for funding and risk".** The story, attribution and auction setups are
board-pack quality. Before this round, three things a treasurer checks first were missing: the cost and availability
of overnight funding, the volatility regime, and how fresh each number is. Long windows also produced misleading
reads, which matters because ALCO discussions are about secular regimes, not last week's move.

## Findings and what changed

| # | Finding | Why a treasurer cares | Change made |
|---|---|---|---|
| 1 | Comparisons over decades were nonsense: point-to-point, today's headlines applied to 26 years, "the front end has priced easing". | Strategic decisions (portfolio duration, funding tenor) rest on the secular view. | Tiered interpretation: up to 2 years keeps the near-term story; 2–10 years leads with Fed and business cycles over a secular backdrop; over 10 years leads with secular forces and splits the path into cycles. The secular lens decomposes the 10Y into the neutral rate (NY Fed r*), expected inflation (Cleveland Fed), term premium (Kim-Wright) and a policy gap. Long windows show dated history instead of headlines. |
| 2 | No long-run debt or fiscal frame. | Sovereign supply and fiscal credibility set the term premium the bank pays and earns. | A Dalio long-term debt cycle panel on every window: debt and debt-service indicators, MP1/MP2/MP3 regimes, eight warning signals with evidence, and an explicit stage call. Today the call is late stage, without bond-market stress so far. |
| 3 | No funding-market read. | Whether front-end yields trade on the Fed or on the supply of cash decides funding costs and bill reinvestment. | A "Funding and liquidity" panel on the Fed tab: SOFR (with percentiles and volume), EFFR, IORB, SOFR minus IORB, ON RRP, bank reserves and the TGA, each with its one-month change and a plain reading. SOFR added to the top bar. |
| 4 | "Fed path" was the Kim-Wright expected short rate averaged over ten years, not the FOMC path. | A label that invites the wrong conclusion fails a model-risk review. | Renamed "expected short rates (10-year average)" everywhere, with a definition in the hover source. |
| 5 | No rates-volatility gauge. | Volatility drives hedge costs, VaR and limit usage. | MOVE added to the top bar with its 1-year percentile and one-month change. |
| 6 | Yield moves were not translated into price. | ALCO reads moves as mark-to-market on the securities book. | Price impact of the move for 2Y, 5Y, 10Y and 30Y par bonds (from modified duration) in "The numbers", and in the change-chart tooltip. |
| 7 | Bills had no carry read against funding. | Liquidity buffers sit in bills; their spread to SOFR is the carry. | Each bill in Supply shows its spread to SOFR. |
| 8 | Data freshness was invisible. | A treasurer will not act on a number without knowing its as-of date. | A data-status bar on every tab: each source's latest reading and whether it is within its normal update cycle. |
| 9 | Some figures on the new panels had no source. | Audit trail. | All 640 numbers on screen carry a hover source, including the new panels and the theory references (Bank of England r* research, the FOMC's 2% goal). |

## Still open

These need either a bank view (deferred, as agreed) or paid data:

- **Balance-sheet impact**: NII and EVE under the BCBS six shocks, securities-portfolio marks, deposit betas. Deferred by
  design.
- **Swap spreads, SOFR OIS curve, cross-currency basis**: paid (Bloomberg, ICE, Tradeweb). These are the next
  most-asked items from a treasury seat.
- **Term-premium cross-check**: the NY Fed ACM model is published only as a legacy Excel file the app cannot read
  without an extra library; Kim-Wright remains the single model.
- **Release calendar** (CPI, payrolls, refunding dates): the BLS blocks automated access; FRED's release calendar
  needs an API key.
- **Non-USD funding** (EUR, JPY): out of scope by choice.
