"use strict";
/* Source attribution for every number on screen.
   Mark an element with data-src="key[,key]" (optional data-src-note, data-src-url) and hovering it shows where the
   number comes from. Prose is handled by srcify(): each number is tagged with the source named closest before it. */

const FRED_NAMES = {
  CPIAUCSL: ["Consumer Price Index, all items (BLS)", "Year-over-year change computed by the dashboard"],
  CPILFESL: ["CPI less food and energy, i.e. core CPI (BLS)", "Year-over-year and 3-month annualized changes computed by the dashboard"],
  CUSR0000SACL1E: ["CPI commodities less food and energy, i.e. core goods (BLS)", "Year-over-year change computed by the dashboard"],
  PCEPILFE: ["PCE price index excluding food and energy, i.e. core PCE (BEA)", "Year-over-year change computed by the dashboard"],
  CES0500000003: ["Average hourly earnings, total private (BLS)", "Year-over-year change computed by the dashboard"],
  MICH: ["University of Michigan: inflation expectation, 1 year ahead", ""],
  T5YIFR: ["5-year, 5-year forward inflation expectation rate (St. Louis Fed)", ""],
  UNRATE: ["Unemployment rate (BLS)", ""],
  PAYEMS: ["Total nonfarm payrolls (BLS)", "3-month average monthly change computed by the dashboard"],
  A191RL1Q225SBEA: ["Real GDP, % change at annual rate (BEA)", ""],
  IC4WSA: ["Initial jobless claims, 4-week average (Department of Labor)", ""],
  DFEDTARU: ["Federal funds target range, upper limit (Federal Reserve)", ""],
  THREEFYTP10: ["Term premium on a 10-year zero-coupon bond, Kim-Wright model (Federal Reserve Board)", "Published weekly. Expected short rates (10-year average) = 10Y yield change minus term-premium change, computed by the dashboard"],
  MTSDS133FMS: ["Federal surplus or deficit, Monthly Treasury Statement (U.S. Treasury)", "12-month rolling sum computed by the dashboard"],
  DCOILWTICO: ["Crude oil prices: WTI, Cushing (EIA)", ""],
  GASREGW: ["U.S. regular gasoline price, weekly (EIA)", ""],
  MORTGAGE30US: ["30-year fixed mortgage average (Freddie Mac)", ""],
  IRLTLT01JPM156N: ["Japan long-term government bond yield, 10-year, monthly average (OECD)", ""],
  IRLTLT01GBM156N: ["UK long-term government bond yield, 10-year, monthly average (OECD)", ""],
  IRLTLT01DEM156N: ["Germany long-term government bond yield, 10-year, monthly average (OECD)", ""],
  GS10: ["10-year Treasury constant maturity rate, monthly average (Federal Reserve H.15)", ""],
  GS2: ["2-year Treasury constant maturity rate, monthly average (Federal Reserve H.15)", ""],
  GS30: ["30-year Treasury constant maturity rate, monthly average (Federal Reserve H.15)", ""],
  DGS10: ["10-year Treasury constant maturity rate, daily (Federal Reserve H.15)", "Daily volatility, history of past moves and level context computed by the dashboard"],
  DGS2: ["2-year Treasury constant maturity rate, daily (Federal Reserve H.15)", "Daily volatility, history of past moves and level context computed by the dashboard"],
  DGS30: ["30-year Treasury constant maturity rate, daily (Federal Reserve H.15)", "Daily volatility computed by the dashboard"],
  T10YIE: ["10-year breakeven inflation rate, daily (St. Louis Fed)", "Daily volatility computed by the dashboard"],
  FEDFUNDS: ["Effective federal funds rate, monthly average (Federal Reserve)", ""],
  EXPINF10YR: ["10-year expected inflation (Federal Reserve Bank of Cleveland model)", ""],
  FYGFGDQ188S: ["Federal debt held by the public as % of GDP (OMB, Federal Reserve Bank of St. Louis)", ""],
  FYOIGDA188S: ["Federal outlays: interest as % of GDP (OMB)", ""],
  FYFSGDA188S: ["Federal surplus or deficit as % of GDP (OMB)", ""],
  A091RC1Q027SBEA: ["Federal government interest payments (BEA)", "Divided by federal current receipts (W006RC1Q027SBEA) by the dashboard"],
  W006RC1Q027SBEA: ["Federal government current tax receipts (BEA)", ""],
  TREAST: ["Treasury securities held outright by the Federal Reserve (H.4.1)", "Divided by debt held by the public (FYGFDPUN) by the dashboard"],
  FYGFDPUN: ["Federal debt held by the public (U.S. Treasury)", ""],
  FDHBFIN: ["Federal debt held by foreign and international investors (Treasury TIC)", "Divided by debt held by the public (FYGFDPUN) by the dashboard"],
  DTWEXBGS: ["Nominal broad U.S. dollar index (Federal Reserve)", "12-month change computed by the dashboard"],
  WALCL: ["Federal Reserve total assets (H.4.1)", "Year-over-year growth used to classify QE regimes"],
  DFII10: ["10-year TIPS yield, daily (Federal Reserve H.15)", ""],
  USREC: ["NBER-based recession indicator", ""],
  GDP: ["Nominal gross domestic product (BEA)", "Year-over-year growth computed by the dashboard"],
  IORB: ["Interest rate on reserve balances (Federal Reserve)", ""],
  RRPONTSYD: ["Overnight reverse repurchase agreements, Treasury securities sold by the Fed (New York Fed)", ""],
  WRESBAL: ["Reserve balances with Federal Reserve Banks, weekly (H.4.1)", ""],
  UMCSENT: ["University of Michigan: consumer sentiment index", "Survey of US households; long-run average about 85"],
  CEFDFSA066MSFRBPHI: ["Philadelphia Fed Manufacturing Business Outlook Survey: future capital expenditures (diffusion index)", "Share of firms planning more capex in six months minus share planning less"],
  GAFDFSA066MSFRBPHI: ["Philadelphia Fed Manufacturing Business Outlook Survey: future general activity (diffusion index)", "Share of firms expecting better business in six months minus share expecting worse"],
  NEWORDER: ["Manufacturers' new orders: nondefense capital goods excluding aircraft, i.e. core capex orders (Census)", "Year-over-year change computed by the dashboard"],
  A679RC1Q027SBEA: ["Private fixed investment in information processing equipment and software (BEA)", "Year-over-year change computed by the dashboard"],
  PNRESCONS: ["Private nonresidential construction spending (Census)", "Year-over-year change computed by the dashboard"],
};

const SOURCES = {
  history: { name: "Dated economic history (BLS, BEA, Federal Reserve, Treasury H.15)", note: "Documented episodes through 2025, written into the dashboard. Episodes after 2025 are described only from live data.",
             url: "https://fred.stlouisfed.org/series/DGS10" },
  calc: { name: "Computed by the dashboard", note: "From the inputs shown in the calculation above; each input's own source is on its own hover.", url: "" },
  isin: { name: "ISIN derived from the CUSIP (ISO 6166)", note: "US + the 9-character CUSIP from TreasuryDirect + a check digit (Luhn on the letters-to-numbers expansion), computed by the dashboard.", url: "https://www.treasurydirect.gov/auctions/upcoming/" },
  ust_par: { name: "U.S. Treasury, Daily Treasury Par Yield Curve Rates", note: "End-of-day par yields by maturity. Changes and spreads computed by the dashboard.",
             url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve" },
  ust_real: { name: "U.S. Treasury, Daily Treasury Par Real Yield Curve Rates (TIPS)", note: "Breakeven inflation = nominal par yield minus real par yield, computed by the dashboard.",
              url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_real_yield_curve" },
  sofr: { name: "Federal Reserve Bank of New York, Secured Overnight Financing Rate (SOFR)", note: "Daily rate with 1st and 99th percentiles and volume.", url: "https://www.newyorkfed.org/markets/reference-rates/sofr" },
  fiscal_dts: { name: "U.S. Treasury, Daily Treasury Statement: operating cash balance (TGA)", note: "", url: "https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/operating-cash-balance" },
  move: { name: "ICE BofA MOVE index (Treasury implied volatility), via Yahoo Finance", note: "1-year percentile and 1-month change computed by the dashboard.", url: "https://finance.yahoo.com/quote/%5EMOVE" },
  effr: { name: "Federal Reserve Bank of New York, Effective Federal Funds Rate", note: "", url: "https://www.newyorkfed.org/markets/reference-rates/effr" },
  zq: { name: "CBOT 30-day fed funds futures (ZQ), via Yahoo Finance", note: "Meeting probabilities and implied rates computed by the dashboard with the CME FedWatch method (25bp steps).",
        url: "https://www.cmegroup.com/markets/interest-rates/stirs/30-day-federal-fund.html" },
  fomc: { name: "Federal Reserve, FOMC meeting calendar", note: "", url: "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm" },
  td: { name: "TreasuryDirect, auction announcements and results", note: "Award shares and averages over the prior six equivalent auctions computed by the dashboard.",
        url: "https://www.treasurydirect.gov/auctions/auction-query/" },
  td_upcoming: { name: "TreasuryDirect, upcoming auctions", note: "", url: "https://www.treasurydirect.gov/auctions/upcoming/" },
  tbac: { name: "Treasury Borrowing Advisory Committee, quarterly refunding reports", note: "TBAC has long treated a bill share of about 20% of marketable debt as the norm.",
          url: "https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding" },
  mspd: { name: "U.S. Treasury, Monthly Statement of the Public Debt (table 1), via Fiscal Data", note: "Bills share = marketable bills ÷ total marketable debt, computed by the dashboard.",
          url: "https://fiscaldata.treasury.gov/datasets/monthly-statement-public-debt/" },
  fiscal_bb: { name: "U.S. Treasury Fiscal Data, Treasury Securities Buybacks", note: "", url: "https://fiscaldata.treasury.gov/datasets/treasury-securities-buybacks/" },
  gnews: { name: "Google News, filtered to verified outlets", note: "Story counts and hotter/cooler tallies computed by the dashboard from Reuters, Bloomberg, WSJ, FT, CNBC, AP and other verified outlets.",
           url: "https://news.google.com/" },
  boe_rs: { name: "Rachel and Smith, Secular drivers of the global real interest rate (Bank of England Staff Working Paper 571, 2015)", note: "Attributes about 400bp of the ~450bp fall in global real rates over 30 years to secular forces.",
            url: "https://www.bankofengland.co.uk/working-paper/2015/secular-drivers-of-the-global-real-interest-rate" },
  fomc_goals: { name: "FOMC Statement on Longer-Run Goals and Monetary Policy Strategy", note: "The Fed's 2% inflation objective, measured by PCE prices.",
                url: "https://www.federalreserve.gov/monetarypolicy/guidance.htm" },
  rstar: { name: "New York Fed, Laubach-Williams estimate of the natural rate of interest (r*)", note: "One-sided (real-time) quarterly estimates.",
           url: "https://www.newyorkfed.org/research/policy/rstar" },
  dalio: { name: "Dashboard reading of Ray Dalio's long-term debt cycle framework", note: "Framework from Principles for Navigating Big Debt Crises (2018) and How Countries Go Broke (2025); indicators and thresholds chosen by the dashboard.",
           url: "https://www.economicprinciples.org/" },
  regime: { name: "Dashboard classification", note: "Bull/bear = direction of the average 2Y and 10Y change; steepener/flattener = sign of the 2s10s change. Inputs: U.S. Treasury par yields.",
            url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve" },
};

function srcInfo(key) {
  if (key.startsWith("fred:")) {
    const id = key.slice(5), [name, note] = FRED_NAMES[id] || [id, ""];
    return { name: `${name}, via FRED (${id})`, note, url: `https://fred.stlouisfed.org/series/${id}` };
  }
  if (key.startsWith("yahoo:")) {
    const sym = key.slice(6);
    return { name: `Yahoo Finance quote: ${sym}`, note: "Change over the window and its size in standard deviations of daily moves computed by the dashboard.", url: `https://finance.yahoo.com/quote/${encodeURIComponent(sym)}` };
  }
  return SOURCES[key] || { name: key, note: "", url: "" };
}

// Tag a value: S("4.82%", "ust_par", "Oct 14, 2026 close")
function S(html, key, note = "", url = "") {
  if (!key) return html;
  return `<span data-src="${escAttr(key)}"${note ? ` data-src-note="${escAttr(note)}"` : ""}${url ? ` data-src-url="${escAttr(url)}"` : ""}>${html}</span>`;
}
// Tag a computed value with its arithmetic: calc is an array of lines shown under "Calculation" in the hover card.
function C(html, key, calc, note = "", url = "") {
  const lines = (Array.isArray(calc) ? calc : [calc]).filter(Boolean);
  const tagged = S(html, key || "calc", note, url);
  return lines.length ? tagged.replace("<span ", `<span data-calc="${escAttr(lines.join("\n"))}" `) : tagged;
}
function escAttr(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Keyword → source. More specific rules first; the keyword closest before a number wins.
const SRC_RULES = [
  [/Bank of England research/g, "boe_rs"],
  [/Fed's credibility|2% target|Fed's 2%|the 2% target/gi, "fomc_goals"],
  [/secular fair value|fair value|policy gap|secular anchor|from the neutral rate, expected inflation and term premium/gi, "rstar,fred:EXPINF10YR,fred:THREEFYTP10,fred:GS10"],
  [/neutral rate|neutral real rate|r\*|Laubach-Williams/gi, "rstar"],
  [/expected 10-year inflation|expected inflation|Cleveland Fed/gi, "fred:EXPINF10YR"],
  [/debt held by the public|of GDP|Debt is high|debt is elevated/gi, "fred:FYGFGDQ188S"],
  [/interest payments|of federal receipts|share of receipts|Interest takes|debt service/gi, "fred:A091RC1Q027SBEA"],
  [/Foreign holdings|foreign share|Foreign share|foreign buyers/gi, "fred:FDHBFIN"],
  [/Fed holdings/gi, "fred:TREAST"],
  [/dollar index|broad dollar|dollar/gi, "fred:DTWEXBGS"],
  [/nominal GDP growth|r − g|r > g/gi, "fred:GDP,fred:GS10"],
  [/fed funds rate, monthly|Effective fed funds rate/gi, "fred:FEDFUNDS"],
  [/warning signals?|signals are on|Late stage|Mid stage|Early stage/gi, "dalio"],
  [/Kim-Wright|term premium|expected short rates|Rate expectations|Exp\. short rates/gi, "fred:THREEFYTP10"],
  [/factory outlook|Factory managers|6-month outlook/gi, "fred:GAFDFSA066MSFRBPHI"],
  [/capex plans|plans to invest/gi, "fred:CEFDFSA066MSFRBPHI"],
  [/orders for business equipment|core capex|equipment orders/gi, "fred:NEWORDER"],
  [/computers, software|data-center|technology was growing|tech spending/gi, "fred:A679RC1Q027SBEA"],
  [/consumer sentiment|Consumer sentiment|sentiment is/gi, "fred:UMCSENT"],
  [/business measures/gi, "fred:GAFDFSA066MSFRBPHI,fred:CEFDFSA066MSFRBPHI,fred:NEWORDER,fred:A679RC1Q027SBEA"],
  [/30Y minus 2Y/gi, "fred:GS30,fred:GS2"],
  [/record low of|peaked near|climbed to about|10Y from about|to 0\.5%/gi, "fred:DGS10"],
  [/raised rates \d|raised rates nine|17 times|cut from|cut rates from|doubled rates|percentage points in 16/gi, "fred:DFEDTARU,history"],
  [/real yield|breakeven|TIPS/gi, "ust_real"],
  [/core PCE|PCE/gi, "fred:PCEPILFE"],
  [/percentile|volume \$/gi, "sofr"],
  [/core goods/gi, "fred:CUSR0000SACL1E"],
  [/core CPI|core over the last 3 months|core held|core eased|core\b/gi, "fred:CPILFESL"],
  [/CPI|consumer price/gi, "fred:CPIAUCSL"],
  [/hourly earnings|wage/gi, "fred:CES0500000003"],
  [/expect inflation|1-year expectation|inflation expectation, 1|expected inflation, next 12/gi, "fred:MICH"],
  [/5y5y/gi, "fred:T5YIFR"],
  [/unemployment/gi, "fred:UNRATE"],
  [/payroll/gi, "fred:PAYEMS"],
  [/GDP/gi, "fred:A191RL1Q225SBEA"],
  [/claims/gi, "fred:IC4WSA"],
  [/WTI|crude|oil/gi, "fred:DCOILWTICO"],
  [/gasoline/gi, "fred:GASREGW"],
  [/mortgage/gi, "fred:MORTGAGE30US"],
  [/deficit/gi, "fred:MTSDS133FMS"],
  [/Japan/gi, "fred:IRLTLT01JPM156N"],
  [/\bUK\b/g, "fred:IRLTLT01GBM156N"],
  [/Germany/gi, "fred:IRLTLT01DEM156N"],
  [/futures|odds|chance of|priced|quarter-point|hike\b|hikes\b|FOMC/gi, "zq"],
  [/fed funds|the Fed (?:cut|raised|left)|rates \d+bp|EFFR|policy rate/gi, "fred:DFEDTARU"],
  [/buyback/gi, "fiscal_bb"],
  [/auction|bid-to-cover|dealers|indirect|stop\b/gi, "td"],
  [/headlines|stories|hotter|cooler/gi, "gnews"],
  [/Chip stocks|SMH/gi, "yahoo:SMH"],
  [/Software stocks|IGV/gi, "yahoo:IGV"],
  [/Gold/gi, "yahoo:GC=F"],
  [/S&amp;P 500|S&P 500/gi, "yahoo:^GSPC"],
  [/σ|sigma|standard deviation/gi, "fred:DGS2,fred:DGS10"],
  [/DXY|Dollar \(DXY\)/gi, "yahoo:DX-Y.NYB"],
  [/VIX/g, "yahoo:^VIX"],
  [/MOVE/g, "yahoo:^MOVE"],
  [/\b(?:2Y|5Y|10Y|20Y|30Y|3M|1M|2s10s|5s30s|3m10y|yields?|curve)\b/gi, "ust_par"],
];
const MONTH_BEFORE = /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s$/;
const NUM_RX = /(?<![A-Za-z\d.#&;])([+\-−±]?\$?\d[\d,]*(?:\.\d+)?)(%|bp|pt|tn|bn|k|x)?(?![A-Za-z\d]|-[A-Za-z])/g;

function sourceFor(prefix) {
  let best = null;
  SRC_RULES.forEach(([rx, key], i) => {
    rx.lastIndex = 0;
    let m;
    while ((m = rx.exec(prefix))) {
      const end = m.index + m[0].length;
      if (!best || end > best.end || (end === best.end && i < best.i)) best = { end, i, key };
    }
  });
  return best ? best.key : null;
}

// Escape the text, then wrap every number with the source named nearest before it in the same clause.
function srcify(text, fallback = "") {
  const html = escAttr(text);
  return html.replace(NUM_RX, (match, num, unit, offset) => {
    const before = html.slice(Math.max(0, offset - 12), offset);
    if (!unit && /^(19|20)\d\d$/.test(num)) return match;          // a year
    if (MONTH_BEFORE.test(before)) return match;                    // a day of a date
    if (/S&amp;P $/.test(before)) return match;                      // the index name "S&P 500"
    const clauseStart = Math.max(html.lastIndexOf(";", offset), html.lastIndexOf(". ", offset), html.lastIndexOf(" · ", offset));
    const key = sourceFor(html.slice(clauseStart + 1, offset)) || sourceFor(html.slice(0, offset)) || fallback;
    return key ? `<span data-src="${key}">${match}</span>` : match;
  });
}

/* ---------- hover card ---------- */
(function sourceTooltip() {
  const tip = document.createElement("div");
  tip.className = "src-tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);
  let hideTimer = null, current = null;

  function show(el) {
    clearTimeout(hideTimer);
    if (el === current && !tip.hidden) return;
    current = el;
    const keys = el.dataset.src.split(",").map((k) => k.trim()).filter(Boolean);
    const extraNote = el.dataset.srcNote, extraUrl = el.dataset.srcUrl, calc = el.dataset.calc;
    const calcHTML = calc ? `<div class="src-h">Calculation</div><div class="src-calc">${calc.split("\n").map((l) => `<div>${escAttr(l)}</div>`).join("")}</div>` : "";
    tip.innerHTML = calcHTML + `<div class="src-h">Source</div>` + keys.map((k, i) => {
      const s = srcInfo(k);
      const url = i === 0 && extraUrl ? extraUrl : s.url;
      return `<div class="src-i"><div class="src-n">${escAttr(s.name)}</div>${s.note ? `<div class="src-d">${escAttr(s.note)}</div>` : ""}
        ${url ? `<a href="${escAttr(url)}" target="_blank" rel="noopener">Open source ↗</a>` : ""}</div>`;
    }).join("") + (extraNote ? `<div class="src-note">${escAttr(extraNote)}</div>` : "");
    tip.hidden = false;
    const r = el.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = Math.min(Math.max(8, r.left + r.width / 2 - tw / 2), window.innerWidth - tw - 8);
    let top = r.bottom + 6;
    if (top + th > window.innerHeight - 8) top = Math.max(8, r.top - th - 6);
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  }
  function hideSoon() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => { tip.hidden = true; current = null; }, 220);
  }
  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest && e.target.closest("[data-src]");
    if (el) show(el);
    else if (!tip.contains(e.target)) hideSoon();
  });
  document.addEventListener("focusin", (e) => {
    const el = e.target.closest && e.target.closest("[data-src]");
    if (el) show(el);
  });
  tip.addEventListener("mouseenter", () => clearTimeout(hideTimer));
  tip.addEventListener("mouseleave", hideSoon);
  window.addEventListener("scroll", () => { tip.hidden = true; current = null; }, { passive: true });
})();
