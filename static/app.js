"use strict";
/* Every number rendered here carries a source tag (S(...) or srcify(...) from sources.js): hover it to see where it
   comes from, its reading date or how US Treasuries Dashboard computed it, and a link to the original. */

/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const fx = (v, d = 2) => (v == null ? "–" : Number(v).toFixed(d));
const sgn = (v, d = 0) => (v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toFixed(d)}`);
const dirCls = (v) => (v == null || Math.abs(v) < 0.5 ? "" : v > 0 ? "up" : "down");
const D = (iso) => new Date(iso.slice(0, 10) + "T12:00:00");
const fmtDate = (iso) => (iso ? D(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "–");
const shortDate = (iso) => (iso ? D(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "–");
const pct = (v) => (v == null ? "–" : `${Math.round(v * 100)}%`);
const daysUntil = (iso) => Math.round((D(iso) - new Date()) / 86400000);
const isPreset = (h) => h.length === 2;
const shortSec = (s) => (s || "").split(" (")[0];
const WINDOW_NAME = { "1D": "1 day", "1W": "1 week", "1M": "1 month", "3M": "3 months", "1Y": "1 year" };

// The published site (GitHub Pages) has no server: it reads the JSON files build_static.py saved.
const STATIC = window.UST_STATIC === true;
function staticFile(path) {
  const u = new URL(path, "http://x");
  const h = u.searchParams.get("h");
  return `data/${u.pathname.replace(/^\/api\//, "").replace(/\//g, "-")}${h ? `-${h}` : ""}.json`;
}
async function api(path, opts) {
  if (STATIC) {
    if (path.startsWith("/api/ai/status")) return { available: false, reason: "Claude's sourced read runs on the local version only." };
    if (path.startsWith("/api/ai")) throw new Error("Claude's sourced read runs on the local version only.");
    const r = await fetch(staticFile(path), { cache: "no-cache" });
    if (!r.ok) throw new Error(/[?&]h=/.test(path) ? "This window is available on the local version only." : "This data was not available at the last update.");
    return r.json();
  }
  const r = await fetch(path, opts);
  let j;
  try { j = await r.json(); } catch { throw new Error(`Server returned ${r.status}`); }
  if (!r.ok || j.error) throw new Error(j.error || r.statusText);
  return j;
}
const errBox = (e) => `<p class="err-box">${esc(e.message || e)}</p>`;

const state = { horizon: "1Y", curve: null, story: null, matrix: null, charts: {}, loaded: {}, newsTab: "window", commsTab: "news", aiStatus: null, strip: null };
const redraws = {};

/* ---------- theme ---------- */
const THEMES = ["system", "light", "dark"];
function applyTheme(t) {
  if (t === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
  $("#themeBtn").textContent = `Theme: ${t}`;
  try { localStorage.setItem("cd-theme", t); } catch {}
  Object.values(redraws).forEach((fn) => fn());
}
$("#themeBtn").addEventListener("click", () => applyTheme(THEMES[(THEMES.indexOf(document.documentElement.dataset.theme || "system") + 1) % 3]));
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => Object.values(redraws).forEach((fn) => fn()));

/* ---------- charts ---------- */
// Prints values on the chart itself. opts.sets: [{index, fmt, pos(v,i,chart), only(i,chart), color}]
const ValueLabels = {
  id: "valueLabels",
  afterDatasetsDraw(chart, _a, opts) {
    if (!opts || !opts.sets) return;
    const ctx = chart.ctx;
    ctx.save();
    ctx.font = "500 10.5px 'IBM Plex Mono', monospace";
    ctx.textAlign = "center";
    for (const s of opts.sets) {
      const meta = chart.getDatasetMeta(s.index);
      if (!meta || meta.hidden) continue;
      meta.data.forEach((el, i) => {
        const v = chart.data.datasets[s.index].data[i];
        if (v == null || (s.only && !s.only(i, chart))) return;
        const pos = typeof s.pos === "function" ? s.pos(v, i, chart) : s.pos || "above";
        ctx.fillStyle = s.color || css("--ink-2");
        ctx.textBaseline = pos === "above" ? "bottom" : "top";
        ctx.fillText(s.fmt(v), el.x, el.y + (pos === "above" ? -6 : 6));
      });
    }
    ctx.restore();
  },
};
if (window.Chart) Chart.register(ValueLabels);

function makeChart(id, config) {
  state.charts[id]?.destroy();
  state.charts[id] = new Chart($("#" + id), config);
}
function baseOpts(yFmt, source) {
  const muted = css("--muted"), line = css("--line");
  return {
    responsive: true, maintainAspectRatio: false, layout: { padding: { top: 18, bottom: 4, left: 10, right: 14 } },
    animation: matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 250 },
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: css("--surface"), titleColor: css("--ink"), bodyColor: css("--ink-2"), footerColor: muted, borderColor: line,
        borderWidth: 1, padding: 10, boxPadding: 4, usePointStyle: true,
        titleFont: { family: "IBM Plex Sans", weight: "600" }, bodyFont: { family: "IBM Plex Mono", size: 12 },
        footerFont: { family: "IBM Plex Sans", size: 11, weight: "400" },
        callbacks: source ? { footer: () => `Source: ${source}` } : {},
      },
    },
    scales: {
      x: { grid: { display: false }, border: { color: css("--line-2") }, ticks: { color: muted, font: { family: "IBM Plex Mono", size: 10.5 }, maxRotation: 0, autoSkipPadding: 14 } },
      y: { grace: "8%", grid: { color: css("--grid"), drawTicks: false }, border: { display: false }, ticks: { color: muted, font: { family: "IBM Plex Mono", size: 10.5 }, padding: 8, maxTicksLimit: 6, callback: yFmt } },
    },
  };
}
function niceAxis(vals) {
  const v = vals.filter((x) => x != null);
  const lo = Math.min(0, ...v), hi = Math.max(0, ...v);
  const raw = (hi - lo || 1) / 4, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((x) => x >= raw);
  return { min: Math.floor(lo / step) * step - (lo < 0 ? step : 0), max: Math.ceil(hi / step) * step + (hi > 0 ? step : 0),
           ticks: { ...baseOpts().scales.y.ticks, stepSize: step, callback: (t) => `${t > 0 ? "+" : ""}${t}` } };
}
const legendHTML = (items) => items.map((i) => `<span><i class="${i.dash ? "dash" : ""}${i.sq ? " sq" : ""}" style="${i.sq ? "background" : "border-color"}:${i.color}"></i>${esc(i.label)}</span>`).join("");
function rgba(hex, a) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
function setCallbacks(o, extra) { o.plugins.tooltip.callbacks = { ...o.plugins.tooltip.callbacks, ...extra }; }
function newsList(items, empty, cols = false) {
  if (!items.length) return `<p class="muted">${esc(empty)}</p>`;
  return `<ul class="news${cols ? " cols" : ""}">${items.map((i) => `<li><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a>
    <div class="meta"><span class="src">${esc(i.source || "")}</span><span>${fmtDate(i.date)}</span>${[i.theme, ...(i.tags || [])].filter(Boolean).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div></li>`).join("")}</ul>`;
}

/* ---------- tabs ---------- */
function showTab(name) {
  $$(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  $$(".tab").forEach((s) => (s.hidden = s.id !== `tab-${name}`));
  if (name === "auctions") loadSupply();
  if (name === "fed") loadFed();
  history.replaceState(null, "", name === "curve" ? location.pathname : `#${name}`);
  Object.values(state.charts).forEach((c) => c.resize());
}
$$(".tabs button").forEach((b) => b.addEventListener("click", () => { showTab(b.dataset.tab); window.scrollTo(0, 0); }));

// "Likely hold" plus the full odds in words, for any FOMC meeting.
function fomcOdds(m) {
  const odds = { hold: m.p_hold ?? 1 - m.p_hike - m.p_cut, hike: m.p_hike, cut: m.p_cut };
  const top = Object.keys(odds).reduce((a, b) => (odds[a] >= odds[b] ? a : b));
  const words = { hold: "the Fed holds", hike: "it hikes 25bp", cut: "it cuts 25bp" };
  const others = Object.keys(odds).filter((k) => k !== top && odds[k] >= 0.01);
  return { top, topPct: odds[top], label: `Likely ${top}`,
           sentence: `${pct(odds[top])} chance ${words[top]}` + others.map((k) => `, ${pct(odds[k])} chance ${words[k]}`).join("") };
}

/* =====================================================================
   STRIP: levels at the latest close, change vs the prior close
   ===================================================================== */
async function loadStrip() {
  let s;
  try { s = await api("/api/strip"); } catch { return; }
  state.strip = s;
  const close = `${fmtDate(s.asof)} close; change vs the prior close`;
  const q = (k, v, chg, src, note) => `<div class="q"><span class="k">${k}</span><span class="v">${S(v, src, note)}${chg != null ? `<small class="${dirCls(chg)}">${S(`${sgn(chg)}bp`, src, note)}</small>` : ""}</span></div>`;
  let html = `<div class="cap"><span>${fmtDate(s.asof)} close</span><span>change vs prior close</span></div>`;
  html += s.tenors.map((t) => q(`${t.tenor} yield`, `${fx(t.level)}%`, t.chg, "ust_par", close)).join("");
  html += q("2s10s", `${sgn(s.s2s10s.today)}bp`, s.s2s10s.chg, "ust_par", `10Y minus 2Y par yield, ${close}`);
  html += q("5s30s", `${sgn(s.s5s30s.today)}bp`, s.s5s30s.chg, "ust_par", `30Y minus 5Y par yield, ${close}`);
  if (s.real10) html += q("10Y real (TIPS)", `${fx(s.real10.level)}%`, s.real10.chg, "ust_real", close);
  if (s.be10) html += q("10Y breakeven", `${fx(s.be10.level)}%`, s.be10.chg, "ust_real,ust_par", `10Y nominal minus 10Y real, ${close}`);
  if (s.sofr) html += q("SOFR", `${fx(s.sofr.rate)}%`, s.sofr.chg, "sofr", `${fmtDate(s.sofr.date)} fixing; change vs the prior fixing`);
  if (s.move) html += q("MOVE (rates vol)", `${fx(s.move.level, 1)}`, null, "move", `${fmtDate(s.move.date)}; ${s.move.pctile_1y}th percentile of the past year; ${sgn(s.move.chg_1m, 1)} over a month`);
  if (s.fed) html += q("Fed funds target", `${fx(s.fed.lo)}–${fx(s.fed.hi)}%`, null, "fred:DFEDTARU,effr", `Effective rate ${fx(s.fed.effr)}% on ${fmtDate(s.fed.effr_date)}`);
  if (s.next) {
    const o = fomcOdds(s.next);
    html += q(`FOMC ${shortDate(s.next.date)}`, `${o.label} (${pct(o.topPct)})`, null, "zq,fomc",
      `${o.sentence}. Futures imply ${sgn(s.next.delta_bp, 1)}bp on a probability-weighted basis.`);
  }
  $("#strip").innerHTML = html;
  $("#asof").textContent = `Par yield curve as of the ${fmtDate(s.asof)} close${state.built ? ` · ${state.built}` : ""}`;
}

async function loadHealth() {
  let h;
  try { h = await api("/api/health"); } catch { return; }
  const bad = h.rows.filter((r) => r.status !== "ok");
  const curve = h.rows.find((r) => r.src === "ust_par");
  const head = bad.length ? `${bad.length} of ${h.rows.length} sources need attention` : `All ${h.rows.length} data sources current`;
  $("#health").innerHTML = `<details><summary><span class="dot ${bad.length ? (bad.some((r) => r.status === "failed") ? "failed" : "stale") : ""}"></span>${head}${curve?.asof ? ` · Treasury curve ${fmtDate(curve.asof)}` : ""}</summary>
    <div class="h-list">${h.rows.map((r) => `<span class="h-i" data-src="${r.src}" data-src-note="${esc(r.status === "ok" ? `Latest reading ${r.asof ? fmtDate(r.asof) : ""}; within its normal update cycle` : r.status === "stale" ? `Latest reading ${r.asof ? fmtDate(r.asof) : "unknown"} is older than its normal update cycle` : "The last fetch failed; numbers from this source may be missing")}"><span class="dot ${r.status}"></span>${esc(r.name)} · ${r.asof ? fmtDate(r.asof) : "failed"}</span>`).join("")}</div></details>`;
}
async function loadMoney() {
  let m;
  try { m = await api("/api/money"); } catch (e) { $("#moneyCard").innerHTML = errBox(e); return; }
  const unit = (i) => i.unit === "%" ? `${fx(i.value, 2)}%` : i.unit === "bp" ? `${sgn(i.value)}bp` : i.unit === "$tn" ? `$${fx(i.value, 2)}tn` : `$${fx(i.value, i.value < 10 ? 1 : 0)}bn`;
  const chg = (i) => i.chg_1m == null ? "" : i.unit === "%" ? `${sgn(i.chg_1m * 100)}bp over a month` : i.unit === "$tn" ? `${sgn(i.chg_1m, 2)}tn over a month` : `${sgn(i.chg_1m, i.unit === "$bn" && Math.abs(i.chg_1m) < 10 ? 1 : 0)}${i.unit === "$bn" ? "bn" : ""} over a month`;
  $("#moneyCard").innerHTML = `
    <header class="card-h"><div><h2>Funding and liquidity</h2><p class="hint">Whether front-end yields are trading on the Fed or on the supply of cash. Hover any number for its source and date.</p></div></header>
    <div class="money">
      <ul class="bullets">${m.reading.map((r) => `<li>${srcify(r, "sofr")}</li>`).join("")}</ul>
      <div class="kv">${m.items.map((i) => `<span>${esc(i.label)}<small>${srcify(i.meaning, i.src)}</small></span><span class="v">${S(unit(i), i.src, `${fmtDate(i.date)}${i.chg_1m != null ? "; " + chg(i) : ""}`)}<small style="text-align:right">${fmtDate(i.date)}${i.chg_1m != null ? " · " + S(chg(i), i.src, "Change versus the reading about a month earlier, computed by the dashboard") : ""}</small></span>`).join("")}</div>
    </div>`;
}

/* =====================================================================
   WINDOW SELECTION
   ===================================================================== */
function regimeClass(r) {
  if (/^bear|bear shift/i.test(r || "")) return "bear";
  if (/^bull|bull shift/i.test(r || "")) return "bull";
  return "";
}
function setHorizon(h) {
  state.horizon = h;
  $$("#winSeg button").forEach((b) => b.classList.toggle("on", b.dataset.h === h));
  $$("#matrix tr.click").forEach((tr) => tr.classList.toggle("sel", tr.dataset.h === h));
  loadStory();
  loadCurve();
}
$$("#winSeg button").forEach((b) => b.addEventListener("click", () => setHorizon(b.dataset.h)));
if (STATIC) {
  $("#customForm").hidden = true;
  fetch("data/meta.json", { cache: "no-cache" }).then((r) => r.json()).then((m) => {
    state.built = `site updated ${new Date(m.built_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" })}`;
    if (state.strip) $("#asof").textContent = `Par yield curve as of the ${fmtDate(state.strip.asof)} close · ${state.built}`;
  }).catch(() => {});
}
$("#customForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = $("#customDate").value;
  if (v) setHorizon(v);
});

/* =====================================================================
   EXECUTIVE SUMMARY + FULL STORY
   ===================================================================== */
let storySeq = 0;
async function loadStory() {
  const seq = ++storySeq;
  $("#storyBody").innerHTML = `<p class="muted"><span class="spinner"></span>Building the executive summary…</p>`;
  $("#narrativeCard").innerHTML = `<p class="muted"><span class="spinner"></span>Building the narrative…</p>`;
  $("#fullStoryCard").innerHTML = `<p class="muted"><span class="spinner"></span>Building the full story…</p>`;
  try {
    const v = await api(`/api/story?h=${encodeURIComponent(state.horizon)}`);
    if (seq !== storySeq) return;
    state.story = v;
    if (!state.aiStatus) { try { state.aiStatus = await api("/api/ai/status"); } catch { state.aiStatus = { available: false }; } }
    renderStory(v);
    renderPath(v);
    renderEvidence(v);
    renderScorecard(v);
    renderNews(v);
  } catch (e) {
    if (seq === storySeq) $("#storyBody").innerHTML = errBox(e);
  }
}

const fmtSv = (x, v) => (v == null ? "–" : x.unit === "index" ? fx(v, 1) : `${fx(v, 1)}%`);
const VERDICT_TIP = {
  Priced: "Priced: the part of the curve this theme should move did move that way, by a material amount",
  Partly: "Partly priced: some of the curve moves this theme predicts happened, others did not",
  "Not priced": "Not priced: the curve did not move the way this theme predicts",
  Context: "Consequence: this theme is an effect of higher rates rather than a cause",
};
function renderStory(v) {
  const s = v.story;
  const name = isPreset(v.horizon) ? `${WINDOW_NAME[v.horizon]} window` : "custom window";
  const win = `${fmtDate(v.past)} close to ${fmtDate(v.asof)} close`;
  const shown = new Set(s.themes.map((t) => t.key));
  const ai = state.aiStatus || {};
  const longMode = v.mode && v.mode !== "near";
  const sv = s.survey_verdict || {}, ex = s.exec || {};
  const gr = ex.grade || {};
  const lead = (ex.rates || []).find((r) => r.key === "10Y");
  const chips = `${S(`<span class="chip ${regimeClass(v.regime)}">${longMode ? "Net change: " : ""}${esc(v.regime)}</span>`, "regime", win)}
      ${gr.label && gr.label !== "Long view" ? C(`<span class="chip ${gr.cls || ""}">${esc(gr.label)}</span>`, "fred:DGS2,fred:DGS10",
          ["Move ÷ (daily σ over the prior year × √trading days in the window)", ...(ex.rates || []).filter((r) => r.z != null && ["2Y", "10Y"].includes(r.key)).map((r) => `${r.label}: ${sgn(r.chg_bp)}bp ÷ (${fx(r.sd_daily_bp, 2)}bp × √${r.n_days} = ${fx(r.sigma_bp, 1)}bp) = ${fx(Math.abs(r.z), 2)}σ`),
           "Noise < 1σ · Notable 1–2σ · Big move 2–3σ · Extreme > 3σ"]) : ""}`;

  // 1. Executive summary: size of the move, what is priced, what drove it, the rest of the tape
  const zCell = (z) => (z == null ? "" : `<span class="z ${Math.abs(z) >= 2 ? "hot" : Math.abs(z) >= 1 ? "warm" : ""}">${fx(Math.abs(z), 1)}σ</span>`);
  const rateTile = (r) => {
    const unit = r.key === "2s10s" ? "bp" : "%";
    const lvl = r.now == null ? "" : unit === "bp" ? `${sgn(r.now)}bp` : `${fx(r.now)}%`;
    const calc = r.sigma_bp ? [`${r.label}: ${sgn(r.chg_bp)}bp over ${r.n_days} trading days`, `Daily σ ${fx(r.sd_daily_bp, 2)}bp (prior ${252} days) × √${r.n_days} = ${fx(r.sigma_bp, 1)}bp`, `${sgn(r.chg_bp)} ÷ ${fx(r.sigma_bp, 1)} = ${fx(r.z, 2)}σ`] : [`${r.label}: ${sgn(r.chg_bp)}bp`];
    const src = { "2Y": "ust_par,fred:DGS2", "10Y": "ust_par,fred:DGS10", "30Y": "ust_par,fred:DGS30", "2s10s": "ust_par,fred:DGS10,fred:DGS2", real10: "ust_real,fred:DFII10", be10: "ust_real,fred:T10YIE" }[r.key];
    return `<div class="tp"><span class="k">${esc(r.label)}</span><span class="v ${dirCls(r.chg_bp)}">${C(`${sgn(r.chg_bp)}bp`, src, calc)}</span><span class="s">${lvl ? S(lvl, src.split(",")[0], `${fmtDate(v.asof)} close`) : ""} ${longMode ? "" : zCell(r.z)}</span></div>`;
  };
  const xTile = (c) => {
    const v_ = c.kind === "pct" ? `${sgn(c.chg, 1)}%` : `${sgn(c.chg, 1)}`;
    const calc = [`${c.label}: ${fx(c.then)} (${fmtDate(c.then_date)}) → ${fx(c.now)} (${fmtDate(c.now_date)})`,
      c.kind === "pct" ? `${fx(c.now)} ÷ ${fx(c.then)} − 1 = ${sgn(c.chg, 1)}%` : `${fx(c.now)} − ${fx(c.then)} = ${sgn(c.chg, 1)} pts`,
      ...(c.sigma ? [`Daily σ ${fx(c.sd_daily, 2)}${c.kind === "pct" ? "%" : " pts"} × √${c.n_days} = ${fx(c.sigma, 2)} → ${fx(Math.abs(c.z), 2)}σ`] : [])];
    return `<div class="tp"><span class="k">${esc(c.label)}</span><span class="v">${C(v_, `yahoo:${c.sym}`, calc)}</span><span class="s">${S(fx(c.now, c.now >= 1000 ? 0 : 2), `yahoo:${c.sym}`, fmtDate(c.now_date))} ${longMode ? "" : zCell(c.z)}</span></div>`;
  };
  const rp = s.report || { bottom_line: s.headline, paras: [] };
  const se = s.summary_exec || { headline: s.headline, sentences: [] };
  const keyRows = (ex.rates || []).filter((r) => ["2Y", "10Y", "30Y", "2s10s", "real10", "be10"].includes(r.key));
  const fed = state.fedLite;
  $("#storyBody").innerHTML = `
    <div class="story-top"><span class="eyebrow">Executive summary · ${esc(name)} · ${fmtDate(v.past)} → ${fmtDate(v.asof)}</span>${chips}
      <span class="spacer"></span><button type="button" class="btn quiet sm" id="copyReport" title="Copy the executive summary as plain text">Copy</button></div>
    <div class="exec-grid">
      <div class="exec-text">
        <h2 class="headline">${srcify(se.headline, "ust_par")}</h2>
        <p class="exec-p">${se.sentences.map((x) => srcify(x, "ust_par")).join(" ")}</p>
      </div>
      <aside class="keynums" aria-label="Key moves">
        ${keyRows.map((r) => {
          const lvl = r.now == null ? "" : r.key === "2s10s" ? `${sgn(r.now)}bp` : `${fx(r.now)}%`;
          const calc = r.sigma_bp ? [`${r.label}: ${sgn(r.chg_bp)}bp over ${r.n_days} trading days`, `Daily σ ${fx(r.sd_daily_bp, 2)}bp × √${r.n_days} = ${fx(r.sigma_bp, 1)}bp`, `${sgn(r.chg_bp)} ÷ ${fx(r.sigma_bp, 1)} = ${fx(r.z, 2)}σ`] : [`${r.label}: ${sgn(r.chg_bp)}bp`];
          const src = { "2Y": "ust_par", "10Y": "ust_par", "30Y": "ust_par", "2s10s": "ust_par", real10: "ust_real", be10: "ust_real,ust_par" }[r.key];
          return `<div class="kn"><span class="k">${esc(r.label)}</span><span class="lv">${S(lvl, src, `${fmtDate(v.asof)} close`)}</span>
            <span class="ch ${dirCls(r.chg_bp)}">${C(`${sgn(r.chg_bp)}`, src, calc)}</span><span class="zz">${!longMode && r.z != null ? `${fx(Math.abs(r.z), 1)}σ` : ""}</span></div>`;
        }).join("")}
        <div class="kn-foot">Change in bp${longMode ? "" : " · σ = size vs normal volatility"}</div>
      </aside>
    </div>
    <details class="tape-d"><summary>Cross-asset tape</summary>
    <div class="tape">
      ${(ex.cross || []).length ? `<div class="tape-g"><span class="tape-l">Cross-asset</span>${ex.cross.map(xTile).join("")}</div>` : ""}
      <div class="tape-g"><span class="tape-l">Rates</span>${(ex.rates || []).map(rateTile).join("")}</div>
    </div></details>`;
  $("#copyReport").addEventListener("click", () => {
    const txt = [`UST curve, ${fmtDate(v.past)} → ${fmtDate(v.asof)}`, "", se.headline + " " + se.sentences.join(" ")].join("\n");
    const b = $("#copyReport");
    navigator.clipboard?.writeText(txt).then(() => { b.textContent = "Copied"; setTimeout(() => (b.textContent = "Copy"), 1500); }).catch(() => {});
  });

  // 2. The narrative, below the curve: the detail behind the summary
  const longView = (s.brief || []).find((b) => b.label === "The long view");
  const paras = [...rp.paras, ...(longView ? [{ label: "The long view", text: longView.text }] : [])];
  $("#narrativeCard").innerHTML = `
    <header class="card-h"><div><h2>The narrative</h2><p class="hint">The detail behind the summary, ${esc(win)}.</p></div>
      <div class="actions">${sv.verdict ? C(`<span class="chip ${/^Confirmed|Optimistic/.test(sv.verdict) ? "solid" : ""}">Surveys: ${esc(sv.verdict.toLowerCase())}</span>`, "fred:GAFDFSA066MSFRBPHI,fred:CEFDFSA066MSFRBPHI,fred:NEWORDER,fred:A679RC1Q027SBEA",
          [`${sv.business_strong} of ${sv.business_n} business measures above their average since 2000`, ...(s.surveys || []).filter((x) => x.side !== "consumer").map((x) => `  ${x.label}: ${fmtSv(x, x.now)} vs ${fmtSv(x, x.avg)} → ${x.strong ? "above" : "below"}`),
           "Rule for an economy running hot: ≥ 2/3 above = confirmed, ≥ 1/3 = partly, otherwise not confirmed"]) : ""}
        <button type="button" class="btn quiet sm" id="copyNarr">Copy</button></div></header>
    <div class="narr">${paras.map((p) => `<section><h3>${esc(p.label)}</h3><p>${srcify(p.text, "ust_par")}</p></section>`).join("")}</div>`;
  $("#copyNarr").addEventListener("click", () => {
    const txt = [`UST curve, ${fmtDate(v.past)} → ${fmtDate(v.asof)}`, "", se.headline, "", ...paras.map((p) => `${p.label}: ${p.text}`)].join("\n\n");
    const b = $("#copyNarr");
    navigator.clipboard?.writeText(txt).then(() => { b.textContent = "Copied"; setTimeout(() => (b.textContent = "Copy"), 1500); }).catch(() => {});
  });

  // 3. The full story
  $("#fullStoryCard").innerHTML = `
    <header class="card-h"><div><h2>Deep dive</h2>
      <p class="hint">How the curve's shape reads, the survey check, the risks and the stories behind the move, ${esc(win)}.</p></div>
      ${ai.available ? `<button class="btn quiet" id="aiBtn" type="button">Ask Claude for a sourced read</button>`
        : `<span class="muted" style="font-size:11px" title="${esc(ai.reason || "")}">Claude's sourced read: needs an API key (README)</span>`}</header>
    <div class="story-body">
      <ul class="exec">${s.summary.filter((x) => !["The long view", "What happened"].includes(x.label)).map((x) => `<li><span class="l">${esc(x.label)}<span class="m">${srcify(x.metric || "", "ust_par")}</span></span><span>${srcify(x.text, "ust_par")}</span></li>`).join("")}</ul>
      <aside class="side">
        <div class="label">Key numbers</div>
        <ul class="deck">${s.deck.map((d) => `<li>${srcify(d, "ust_par")}</li>`).join("")}</ul>
        <p class="hint" style="margin-top:6px">Real yield: the 10Y minus expected inflation (from TIPS); it moves with growth and the Fed. Inflation expectations: the inflation rate bond prices imply.</p>
        <div class="label">Risks to the story</div><ul class="risks">${s.risks.map((r) => `<li>${srcify(r, "gnews")}</li>`).join("")}</ul>
      </aside>
    </div>
    <div class="label" style="margin-top:24px">${longMode ? "The chapters that moved yields most" : "The three stories behind the move"}</div>
    <p class="hint">${longMode
      ? (v.mode === "secular" ? "Over 20 years or more, the secular story sets the trend; the two chapters that moved the 10Y most sit on top of it. Each card tells what happened in the economy, how it reached yields, and what yields did." : "Under 20 years, the trend is a sequence of episodes. These are the three that moved the 10Y most: what happened in the economy, how it reached yields, and what yields did.")
      : "The AI investment boom, the major story today, plus the two themes verified outlets (Reuters, Bloomberg, WSJ, FT and others) most often tied to rates in the window. Each card shows the story in the economy, how it reaches the curve, and whether bond investors traded it."}</p>
    <div class="themes" style="margin-top:10px">${s.themes.map((t, i) => `
      <div class="theme">
        <div class="theme-h"><span class="rank">${i + 1}</span><h3>${esc(t.name)}</h3></div>
        <div class="meta">${t.volume == null
            ? S(`<span class="chip ${/up/.test(t.verdict) ? "bear" : /down/.test(t.verdict) ? "bull" : ""}">${esc(t.verdict)}</span>`, "fred:GS10", "What the 10Y did during this chapter, monthly averages")
            : S(`<span class="chip ${t.verdict === "Priced" ? "solid" : ""}">${esc(t.verdict === "Context" ? "Consequence" : t.verdict)}</span>`, "ust_par,ust_real", VERDICT_TIP[t.verdict] || "")}
          <span class="chip" title="How this force reaches Treasury yields">${esc(t.channel)}</span>
          ${t.volume == null ? "" : `<span class="muted" style="font-size:12px">${S(`${t.volume} verified rates stories`, "gnews", `Stories mentioning this theme together with rates, ${win}`)}</span>`}</div>
        ${t.life ? `<p><b>In the economy.</b> ${srcify(t.life)}</p>` : ""}
        <p><b>${t.volume == null ? "What happened." : "How it reaches the curve."}</b> ${srcify(t.mechanism, t.volume == null ? "fred:GS10" : "ust_par")}</p>
        ${t.evidence ? `<p><b>What yields did.</b> ${srcify(t.evidence, t.volume == null ? "fred:GS10" : "ust_par")}</p>` : ""}
        <ul class="heads">${(t.links || []).map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a></li>`).join("")}${t.headlines.slice(0, 2).map((h) => `<li><a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a> <span>· ${esc(h.source)}, ${fmtDate(h.date)}</span></li>`).join("")}</ul>
      </div>`).join("")}</div>
    ${s.all_themes.length ? `<div class="also"><span class="eyebrow">Other themes, verified rates stories in the window</span>${s.all_themes.filter((t) => !shown.has(t.key) && t.volume > 0).map((t) =>
      `<span class="chip">${esc(t.name)}<b>${S(String(t.volume), "gnews", `Stories mentioning this theme together with rates, ${win}`)}</b></span>`).join("")}</div>` : ""}
    ${dalioPanel(v.debt_cycle)}
    <div id="aiOut"></div>`;
  $("#aiBtn")?.addEventListener("click", runAI);
}

function dalioPanel(dc) {
  if (!dc) return "";
  const ind = (r) => {
    const unit = r.unit === "pt" ? "pt" : "%";
    const now = S(`${r.unit === "pt" ? sgn(r.now, 1) : fx(r.now, r.now >= 10 ? 1 : 2)}${unit}`, r.key === "r_g" ? "fred:GDP,fred:GS10" : srcKeyFor(r.key), r.note);
    return `<span>${esc(r.label)}<small class="muted" style="display:block;font-size:11px">${r.then != null ? `${S(`${fx(r.then, r.then >= 10 ? 1 : 2)}${unit}`, srcKeyFor(r.key), `Reading of ${fmtDate(r.then_date)}`)} three years earlier · ` : ""}latest ${fmtDate(r.now_date)}</small></span><span class="v">${now}</span>`;
  };
  return `<div class="dalio">
    <div class="label" style="margin-top:0">The long-term debt cycle · Ray Dalio's framework</div>
    <div class="story-top" style="margin-top:6px">${S(`<span class="chip ${dc.signals_on >= 4 ? "bear" : "solid"}">${esc(dc.stage)}</span>`, "dalio", `${dc.signals_on} of ${dc.signals_total} warning signals on`)}
      <span class="chip">${esc(dc.mp_text)}</span></div>
    <p style="font-size:14px;line-height:1.6;max-width:90ch">${srcify(dc.call, "dalio")}</p>
    <div class="dalio-g">
      <div><div class="label">Warning signals (${dc.signals_on} of ${dc.signals_total} on)</div>
        <ul class="sig">${dc.signals.map((x) => `<li><span class="dot ${x.on ? "on" : ""}" title="${x.on ? "On" : "Off"}"></span><span>${esc(x.signal)}<span class="ev">${srcify(x.evidence, "dalio")}</span></span></li>`).join("")}</ul></div>
      <div><div class="label">Debt-cycle indicators</div><div class="kv">${dc.indicators.map(ind).join("")}</div>
        <p class="hint" style="margin-top:8px">Stages and signals follow Dalio's Principles for Navigating Big Debt Crises and How Countries Go Broke. The thresholds are the dashboard's; this is a framework reading, not a forecast.</p></div>
    </div></div>`;
}
function srcKeyFor(k) {
  return { debt_gdp: "fred:FYGFGDQ188S", int_rev: "fred:A091RC1Q027SBEA,fred:W006RC1Q027SBEA", int_gdp: "fred:FYOIGDA188S", deficit: "fred:FYFSGDA188S",
           fed_share: "fred:TREAST,fred:FYGFDPUN", foreign_share: "fred:FDHBFIN,fred:FYGFDPUN", slope: "fred:GS30,fred:GS2", real10: "fred:DFII10" }[k] || "dalio";
}

// Shades recessions and draws a monetary-policy regime strip under the plot.
const PathBands = {
  id: "pathBands",
  beforeDatasetsDraw(chart, _a, opts) {
    if (!opts || !opts.rows) return;
    const { ctx, chartArea: ar, scales: { x } } = chart, rows = opts.rows;
    const xAt = (i) => x.getPixelForValue(i);
    ctx.save();
    ctx.fillStyle = opts.recColor;
    rows.forEach((r, i) => { if (r.rec) { const x0 = xAt(Math.max(0, i - 0.5)), x1 = xAt(Math.min(rows.length - 1, i + 0.5)); ctx.fillRect(x0, ar.top, x1 - x0, ar.bottom - ar.top); } });
    const col = { MP1: opts.mp1, MP2: opts.mp2, MP3: opts.mp3 };
    let s = 0;
    for (let i = 1; i <= rows.length; i++) {
      if (i === rows.length || rows[i].mp !== rows[s].mp) {
        const x0 = xAt(s), x1 = xAt(i - 1) + 1;
        ctx.fillStyle = col[rows[s].mp] || opts.mp1;
        ctx.fillRect(x0, ar.bottom - 6, Math.max(x1 - x0, 1), 6);
        if (x1 - x0 > 36) { ctx.fillStyle = opts.text; ctx.font = "500 10px 'IBM Plex Mono', monospace"; ctx.textAlign = "left"; ctx.textBaseline = "bottom"; ctx.fillText(rows[s].mp, x0 + 3, ar.bottom - 8); }
        s = i;
      }
    }
    ctx.restore();
  },
};
if (window.Chart) Chart.register(PathBands);

function renderPath(v) {
  const rows = v.path || [], longMode = v.mode !== "near";
  const pivots = new Set((v.legs || []).flatMap((l) => [l.from, l.to]));
  const secularMode = v.mode === "secular";
  $("#histTitle").textContent = secularMode ? "The path in between: chapters and the long-run anchor" : longMode ? "The path in between: the chapters" : "The path in between";
  $("#histHint").innerHTML = `${longMode ? "Monthly averages" : "Daily closes"}, ${fmtDate(v.past)} to ${fmtDate(v.asof)}. Grey bands: recessions. Bottom strip: Dalio's monetary-policy regimes (MP1 rates, MP2 QE at the zero bound, MP3 QE financing large deficits). Labels mark the turning points of each cycle.`;
  const draw = () => {
    const c1 = css("--series-1"), c2 = css("--series-2"), c3 = css("--series-3"), neutral = css("--neutral");
    const labels = rows.map((r) => r.d);
    const o = baseOpts((x) => x.toFixed(1) + "%", longMode ? "FRED (Treasury H.15, Fed funds, NY Fed r*, Cleveland Fed); computed by the dashboard" : "U.S. Treasury par yields; fed funds from FRED");
    o.scales.x.ticks.callback = function (i) { const d = this.getLabelForValue(i); return longMode ? d.slice(0, 4) : shortDate(d); };
    o.scales.x.ticks.maxTicksLimit = 10;
    setCallbacks(o, { title: (it) => (longMode ? D(it[0].label).toLocaleDateString("en-US", { month: "short", year: "numeric" }) : fmtDate(it[0].label)),
                      label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y == null ? "–" : ctx.parsed.y.toFixed(2) + "%"}`,
                      afterBody: (it) => { const r = rows[it[0].dataIndex]; return [r.rec ? "Recession" : "", `Regime: ${r.mp}`].filter(Boolean); } });
    o.plugins.pathBands = { rows, recColor: rgba(neutral, 0.16), mp1: rgba(c1, 0.35), mp2: rgba(c3, 0.55), mp3: rgba(c2, 0.6), text: css("--ink-2") };
    o.plugins.valueLabels = { sets: [
      { index: 0, fmt: (x) => x.toFixed(2), pos: (x, i) => { const p = rows[i - 1]?.y10, n = rows[i + 1]?.y10; return p != null && n != null && x < p && x <= n ? "below" : "above"; }, color: c1,
        only: (i) => pivots.has(rows[i].d) || i === rows.length - 1 },
      ...(secularMode ? [{ index: 3, fmt: (x) => x.toFixed(2), pos: "above", color: c3, only: (i) => i === rows.length - 1 }] : []),
    ] };
    o.elements = { point: { radius: (ctx) => (pivots.has(rows[ctx.dataIndex]?.d) ? 3 : 0) } };
    makeChart("histChart", {
      type: "line",
      data: { labels, datasets: [
        { label: "10Y", data: rows.map((r) => r.y10), borderColor: c1, backgroundColor: c1, borderWidth: 2, pointHoverRadius: 4, tension: 0.15 },
        { label: "2Y", data: rows.map((r) => r.y2), borderColor: c2, backgroundColor: c2, borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 3, tension: 0.15 },
        { label: "Fed funds", data: rows.map((r) => r.ff), borderColor: neutral, borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 3, stepped: true },
        ...(secularMode ? [{ label: "Long-run anchor", data: rows.map((r) => r.anchor), borderColor: c3, backgroundColor: c3, borderWidth: 2, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 3, tension: 0.15 }] : []),
      ] },
      options: o,
    });
    $("#histLegend").innerHTML = legendHTML([{ label: "10Y", color: c1 }, { label: "2Y", color: c2 }, { label: "Fed funds", color: neutral }, ...(secularMode ? [{ label: "Long-run anchor (neutral rate + expected inflation)", color: c3, dash: true }] : [])]);
  };
  redraws.hist = draw;
  draw();

  const legs = v.legs || [];
  $("#legsBox").innerHTML = `<div class="label" style="margin-top:0">Turning points (${legs.length})</div>
    <div class="tbl-wrap"><table class="legs"><thead><tr><th>From → to</th><th class="r">10Y</th><th class="r">Change</th><th>The story</th></tr></thead><tbody>
    ${legs.map((l) => `<tr><td class="num">${longMode ? `${D(l.from).toLocaleDateString("en-US", { month: "short", year: "numeric" })} → ${D(l.to).toLocaleDateString("en-US", { month: "short", year: "numeric" })}` : `${shortDate(l.from)} → ${shortDate(l.to)}`}</td>
      <td class="r num">${S(`${fx(l.y_from)}% → ${fx(l.y_to)}%`, longMode ? "fred:GS10" : "ust_par", longMode ? "Monthly averages" : "Daily closes")}</td>
      <td class="r num ${dirCls(l.chg_bp)}">${S(`${sgn(l.chg_bp)}bp`, longMode ? "fred:GS10" : "ust_par", "Change computed by the dashboard")}</td>
      <td>${srcify((l.history || [])[0] || "–", "fred:DFEDTARU")}${l.mp && l.mp.length ? ` <span class="muted">· ${esc(l.mp.join(", "))}</span>` : ""}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">No turning point in this window.</td></tr>`}
    </tbody></table></div>`;

  const d = v.decomposition || {}, st = d.start || {}, en = d.end || {}, ch = d.chg_bp || {};
  const mo = (iso) => (iso ? D(iso).toLocaleDateString("en-US", { month: "short", year: "numeric" }) : "–");
  $(".path-grid").classList.toggle("one", !secularMode);
  if (!secularMode) { $("#secBox").innerHTML = ""; return; }
  const row = (k, label, src, then, now) => ({ k: label, v: ch[k] ?? null, src, note: then != null && now != null ? `${fx(then)}% (${mo(st.date)}) → ${fx(now)}% (${mo(en.date)})` : "" });
  const rest = ch.y10 != null && ch.rstar != null && ch.einf != null ? ch.y10 - ch.rstar - ch.einf : null;
  $("#secBox").innerHTML = `<div class="label" style="margin-top:0">The long-run anchor · ${mo(st.date)} → ${mo(en.date)} (monthly averages)</div>
    <div class="bridge">${bridgeRows([
      { k: "10Y yield", v: ch.y10 ?? null, total: true, src: "fred:GS10", note: `${fx(st.y10)}% → ${fx(en.y10)}%` },
      row("rstar", "Neutral real rate (r*)", "rstar", st.rstar, en.rstar),
      row("einf", "Expected inflation", "fred:EXPINF10YR", st.einf, en.einf),
      { k: "Everything else", v: rest, src: "calc", tip: "The Fed cycle and the extra pay investors want for lending long", note: "10Y change minus the neutral-rate and expected-inflation changes" },
    ])}</div>
    <p class="hint" style="margin-top:8px">${en.anchor != null ? `Long-run anchor now ${C(`${fx(en.anchor)}%`, "rstar,fred:EXPINF10YR", [`Neutral real rate ${fx(en.rstar)}% + expected inflation ${fx(en.einf)}% = ${fx(en.anchor)}% (${mo(en.date)})`])} vs a ${S(`${fx(en.y10)}%`, "fred:GS10", `${mo(en.date)} monthly average`)} 10Y. ` : ""}The anchor is where yields settle when the Fed is neither stimulating nor slowing the economy.</p>`;
}

/* ---------- Claude ---------- */
function md(text) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const sections = [];
  let cur = null, list = null;
  const flush = () => { if (list) { cur.body.push(`<ul>${list.join("")}</ul>`); list = null; } };
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const h = line.match(/^#{1,4}\s+(.*)/);
    if (h) { if (cur) flush(); cur = { title: h[1], body: [] }; sections.push(cur); continue; }
    if (!cur) { cur = { title: "", body: [] }; sections.push(cur); }
    if (/^[-*] /.test(line)) { (list ||= []).push(`<li>${inline(line.slice(2))}</li>`); continue; }
    flush();
    if (line) cur.body.push(`<p>${inline(line)}</p>`);
  }
  if (cur) flush();
  return sections.map((s) => `<div class="${/story|theme/i.test(s.title) ? "full" : ""}">${s.title ? `<h4>${inline(s.title)}</h4>` : ""}${s.body.join("")}</div>`).join("");
}
async function runAI() {
  const h = state.horizon, btn = $("#aiBtn"), out = $("#aiOut");
  btn.disabled = true;
  out.className = "ai-out";
  out.innerHTML = `<p class="muted full"><span class="spinner"></span>Claude is checking verified sources and writing the story (about a minute)…</p>`;
  try {
    const r = await api(`/api/ai?h=${encodeURIComponent(h)}`, { method: "POST" });
    if (state.horizon !== h) return;
    out.innerHTML = `<div class="full"><span class="eyebrow">Claude's read · ${esc(r.model)}${r.cached ? " · cached" : ""}</span></div>` + md(r.text) +
      (r.sources.length ? `<div class="full"><h4>Sources</h4><ol style="padding-left:18px;font-size:12.5px;margin:0">${r.sources.map((s) => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a></li>`).join("")}</ol></div>` : "");
  } catch (e) {
    out.innerHTML = `<div class="full">${errBox(e)}</div>`;
  } finally {
    btn.disabled = false;
  }
}

/* =====================================================================
   CURVE + THE NUMBERS
   ===================================================================== */
let curveSeq = 0;
async function loadCurve() {
  const seq = ++curveSeq;
  $("#attrCard").innerHTML = `<p class="muted"><span class="spinner"></span>Loading…</p>`;
  try {
    const a = await api(`/api/curve?h=${encodeURIComponent(state.horizon)}`);
    if (seq !== curveSeq) return;
    state.curve = a;
    $("#customDate").max = a.asof;
    redraws.curve = () => drawCurve(a);
    drawCurve(a);
    renderAttr(a);
    renderMatrix();
  } catch (e) {
    if (seq === curveSeq) $("#attrCard").innerHTML = errBox(e);
  }
}

function drawCurve(a) {
  const c1 = css("--series-1"), c2 = css("--series-2");
  const labels = a.tenors.map((t) => t.tenor);
  const today = `${fmtDate(a.asof)} close`, then = `${fmtDate(a.past)} close`;
  $("#curveTitle").textContent = "Treasury yield curve";
  $("#curveHint").innerHTML = `Par yield by maturity, ${fmtDate(a.past)} close vs ${fmtDate(a.asof)} close (${S("U.S. Treasury", "ust_par")}). Shading: red where yields rose, blue where they fell.`;
  const o = baseOpts((v) => v.toFixed(2) + "%", "U.S. Treasury, Daily Par Yield Curve Rates");
  setCallbacks(o, {
    label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}%`,
    afterBody: (items) => { const t = a.tenors[items[0].dataIndex]; return t.chg_bp == null ? "" : `Change: ${sgn(t.chg_bp)}bp`; },
  });
  const above = (i) => (a.tenors[i].today ?? 0) >= (a.tenors[i].past ?? 0);
  const apart = (i, chart) => Math.abs(chart.getDatasetMeta(0).data[i].y - chart.getDatasetMeta(1).data[i].y) > 16;
  o.plugins.valueLabels = { sets: [
    { index: 0, fmt: (v) => v.toFixed(2), pos: (v, i) => (above(i) ? "above" : "below"), color: c1 },
    { index: 1, fmt: (v) => v.toFixed(2), pos: (v, i) => (above(i) ? "below" : "above"), color: c2, only: (i, ch) => apart(i, ch) },
  ] };
  makeChart("curveChart", {
    type: "line",
    data: { labels, datasets: [
      { label: today, data: a.tenors.map((t) => t.today), borderColor: c1, backgroundColor: c1, borderWidth: 2, pointRadius: 3, pointHoverRadius: 6, tension: 0.25 },
      { label: then, data: a.tenors.map((t) => t.past), borderColor: c2, backgroundColor: c2, borderWidth: 2, borderDash: [6, 4], pointRadius: 3, pointHoverRadius: 6, tension: 0.25,
        fill: { target: 0, above: rgba(css("--bull"), 0.08), below: rgba(css("--bear"), 0.08) } },
    ] },
    options: o,
  });
  $("#curveLegend").innerHTML = legendHTML([{ label: today, color: c1 }, { label: then, color: c2, dash: true }]);

  const vals = a.tenors.map((t) => t.chg_bp);
  const ob = baseOpts(null, "U.S. Treasury par yields; change computed by the dashboard");
  setCallbacks(ob, { label: (ctx) => ` ${sgn(ctx.parsed.y)}bp`,
    afterLabel: (ctx) => { const t = a.tenors[ctx.dataIndex]; return t.today == null ? "" : ` ≈ ${sgn(parPriceChg(t.today, t.years, t.chg_bp), 1)}% price on a par bond`; } });
  ob.plugins.valueLabels = { sets: [{ index: 0, fmt: (v) => sgn(v), pos: (v) => (v >= 0 ? "above" : "below") }] };
  ob.scales.y.grid.color = (ctx) => (ctx.tick.value === 0 ? css("--muted") : css("--grid"));
  Object.assign(ob.scales.y, niceAxis(vals));
  makeChart("chgChart", {
    type: "bar",
    data: { labels, datasets: [{ data: vals, backgroundColor: vals.map((v) => (v > 0.5 ? css("--bear") : v < -0.5 ? css("--bull") : css("--neutral"))), borderRadius: 4, borderSkipped: "start", barPercentage: 0.7 }] },
    options: ob,
  });
}

// Approximate price change of a par bond of `years` maturity for a yield move of `bp`, from its modified duration.
function parPriceChg(yPct, years, bp) {
  const y = yPct / 100, n = Math.max(1, Math.round(years * 2));
  if (years < 1) return -(bp / 10000) * years * 100;                 // bills: price moves with maturity
  const dur = (1 / y) * (1 - 1 / Math.pow(1 + y / 2, n));          // modified duration of a par bond
  return -dur * (bp / 10000) * 100;
}

function bridgeRows(items) {
  const max = Math.max(1, ...items.filter((i) => i.v != null).map((i) => Math.abs(i.v)));
  return items.map((i) => {
    if (i.head) return `<span class="label" style="grid-column:1/-1;margin:${i.first ? 0 : 10}px 0 2px">${esc(i.head)}</span>`;
    if (i.v == null) return `<span>${esc(i.k)}</span><span class="muted" style="font-size:12px">${esc(i.na || "n/a")}</span><span></span>`;
    const w = (Math.abs(i.v) / max) * 50;
    return `<span class="${i.total ? "total" : ""}" title="${esc(i.tip || "")}">${esc(i.k)}</span>
      <span class="track"><span class="bar ${i.v >= 0 ? "up" : "down"}" style="left:${i.v >= 0 ? 50 : 50 - w}%;width:${Math.max(w, 0.6)}%"></span></span>
      <span class="val ${i.total ? "total" : ""} ${dirCls(i.v)}">${S(`${sgn(i.v)}bp`, i.src, i.note)}</span>`;
  }).join("");
}

function renderAttr(a) {
  const at = a.attribution, t10 = a.tenors.find((t) => t.tenor === "10Y");
  const tipsRange = `${fmtDate(a.past)} → ${fmtDate(at.real_asof || a.asof)}`;
  const spreads = Object.entries(a.spreads).filter(([k]) => ["2s10s", "5s30s", "3m10y"].includes(k))
    .map(([k, v]) => `<span>${k} <span class="muted" style="font-size:11.5px">${k === "3m10y" ? "10Y − 3M" : k === "2s10s" ? "10Y − 2Y" : "30Y − 5Y"}</span></span>
      <span class="v">${S(`${sgn(v.past)} → ${sgn(v.today)}bp`, "ust_par", `${fmtDate(a.past)} close → ${fmtDate(a.asof)} close`)} <span class="${dirCls(v.chg)}">(${S(sgn(v.chg), "ust_par", "Change computed by the dashboard")})</span></span>`).join("");
  const segs = Object.entries(a.segments).map(([k, v]) => `<span>${esc(k)}</span><span>${S(`<span class="chip ${regimeClass(v)}">${esc(v)}</span>`, "regime")}</span>`).join("");
  $("#attrCard").innerHTML = `
    <header class="card-h"><div><h2>The numbers: why the 10Y moved ${S(`${sgn(t10.chg_bp)}bp`, "ust_par", `${fmtDate(a.past)} close → ${fmtDate(a.asof)} close`)}</h2>
      <p class="hint">10Y from ${S(`${fx(t10.past)}%`, "ust_par", `${fmtDate(a.past)} close`)} (${fmtDate(a.past)}) to ${S(`${fx(t10.today)}%`, "ust_par", `${fmtDate(a.asof)} close`)} (${fmtDate(a.asof)}), split into growth and the Fed (real yield) and inflation. Red bars pushed the yield up, blue down.</p></div></header>
    <div class="bridge">${bridgeRows([
      { head: `Growth and the Fed vs inflation · ${tipsRange} (TIPS)`, first: true },
      { k: "10Y yield", v: t10.chg_bp, total: true, src: "ust_par", note: tipsRange },
      { k: "Real yield", v: at.real_bp, tip: "10Y TIPS yield: the inflation-adjusted cost of money; moves with growth and the Fed", src: "ust_real", note: at["10Y"] ? `10Y real yield now ${fx(at["10Y"].real)}%, ${tipsRange}` : "" },
      { k: "Inflation expectations", v: at.be_bp, tip: "Nominal minus real yield (breakeven): the inflation rate bond prices imply", src: "ust_real,ust_par", note: at["10Y"] ? `10Y breakeven now ${fx(at["10Y"].breakeven)}%, ${tipsRange}` : "" },
    ])}</div>
    <div class="label">Price impact of the move (par bond, from duration)</div>
    <div class="kv">${["2Y", "5Y", "10Y", "30Y"].map((tn) => { const t = a.tenors.find((x) => x.tenor === tn); if (!t || t.chg_bp == null) return "";
      const p = parPriceChg(t.today, t.years, t.chg_bp);
      return `<span>${tn} <span class="muted" style="font-size:11.5px">${S(`${sgn(t.chg_bp)}bp`, "ust_par", `${tn} change, ${fmtDate(a.past)} close → ${fmtDate(a.asof)} close`)}</span></span><span class="v ${p < 0 ? "up" : p > 0 ? "down" : ""}">${S(`${sgn(p, 1)}%`, "ust_par", `Approximate price change of a ${tn} par bond for a ${sgn(t.chg_bp)}bp move: minus modified duration × yield change, computed by the dashboard (excludes coupon income and roll-down)`)}</span>`; }).join("")}</div>
    <div class="label">Shape, by segment</div><div class="kv">${segs}</div>
    <p class="hint" style="margin-top:4px">Bear = yields rose; bull = yields fell. Steepener = long end rose more (or fell less) than the short end.</p>
    <div class="label">Spreads, then → now</div><div class="kv">${spreads}</div>`;
}

/* =====================================================================
   MATRIX: every window at once (also a selector)
   ===================================================================== */
const bpTd = (v, src, note, sep = false) => `<td class="r num ${sep ? "sep " : ""}${dirCls(v)}">${v == null ? "–" : S(sgn(v), src, note)}</td>`;
async function loadMatrix() {
  try { state.matrix = await api("/api/matrix"); } catch (e) { $("#matrix").innerHTML = `<tbody><tr><td>${errBox(e)}</td></tr></tbody>`; return; }
  renderMatrix();
}
function renderMatrix() {
  if (!state.matrix) return;
  const rows = [...state.matrix];
  const a = state.curve;
  if (a && !isPreset(a.horizon)) {
    const at = a.attribution, ch = Object.fromEntries(a.tenors.map((t) => [t.tenor, t.chg_bp]));
    rows.push({ horizon: a.horizon, past: a.past, regime: a.regime, chg: ch, s2s10s: a.spreads["2s10s"].chg, s5s30s: a.spreads["5s30s"].chg,
      real_bp: at.real_bp, be_bp: at.be_bp, lead: a.lead });
  }
  const asof = state.strip?.asof || a?.asof;
  if (asof) $("#matrixHint").textContent = `Change in basis points from each start date's close to the ${fmtDate(asof)} close. The last three columns split the 10Y change into growth and the Fed (real yield) and inflation. Select a row to load its story.`;
  const body = rows.map((r) => {
    if (r.error) return `<tr><td>${r.horizon}</td><td colspan="11" class="muted">${esc(r.error)}</td></tr>`;
    const n = `${fmtDate(r.past)} close → ${fmtDate(asof)} close`;
    return `<tr class="click ${r.horizon === state.horizon ? "sel" : ""}" data-h="${r.horizon}" tabindex="0">
      <td>${isPreset(r.horizon) ? WINDOW_NAME[r.horizon] : "Custom"}</td><td class="num">${fmtDate(r.past)}</td>
      ${["2Y", "5Y", "10Y", "30Y"].map((t) => bpTd(r.chg[t], "ust_par", `${t} change, ${n}`)).join("")}
      ${bpTd(r.s2s10s, "ust_par", `2s10s change, ${n}`)}${bpTd(r.s5s30s, "ust_par", `5s30s change, ${n}`)}
      <td>${S(`<span class="chip ${regimeClass(r.regime)}">${esc(r.regime)}</span>`, "regime", n)}</td>
      ${bpTd(r.real_bp, "ust_real", `10Y real yield change, ${n}`, true)}${bpTd(r.be_bp, "ust_real,ust_par", `10Y breakeven change, ${n}`)}
      <td>${esc(r.lead)}</td></tr>`;
  }).join("");
  $("#matrix").innerHTML = `<thead>
    <tr><th colspan="2"></th><th colspan="4" class="grp">Yield change, bp</th><th colspan="2" class="grp">Spread change, bp</th><th></th><th colspan="3" class="grp sep">What moved the 10Y, bp</th></tr>
    <tr><th>Window</th><th>Start (close)</th><th class="r">2Y</th><th class="r">5Y</th><th class="r">10Y</th><th class="r">30Y</th>
    <th class="r" title="10Y minus 2Y">2s10s</th><th class="r" title="30Y minus 5Y">5s30s</th><th>Curve regime</th>
    <th class="r sep" title="10Y TIPS real yield: growth and the Fed">Real yield</th><th class="r" title="10Y breakeven: inflation expectations">Inflation exp.</th><th>Led by</th></tr></thead><tbody>${body}</tbody>`;
  $$("#matrix tr.click").forEach((tr) => {
    const go = () => { setHorizon(tr.dataset.h); $("#storyCard").scrollIntoView({ behavior: "smooth" }); };
    tr.addEventListener("click", go);
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
  });
}

/* =====================================================================
   EVIDENCE, SCORECARD, NEWS
   ===================================================================== */
function renderEvidence(v) {
  const s = v.story, sv = s.surveys || [], vd = s.survey_verdict || {};
  const win = `${fmtDate(v.past)} → ${fmtDate(v.asof)}`;
  const rows = sv.map((x) => {
    const src = `fred:${x.series}`;
    return `<tr><td>${esc(x.label)}<small>${esc(x.meaning)}</small></td>
      <td class="r num">${S(fmtSv(x, x.now), src, `${x.now_period} reading`)}<small>${esc(x.now_period)}</small></td>
      <td class="r num">${C(fmtSv(x, x.avg), src, [`Average of all ${x.avg_n} readings since ${x.avg_from}`, `Latest ${fmtSv(x, x.now)} − average ${fmtSv(x, x.avg)} = ${sgn(x.now - x.avg, 1)}${x.unit === "index" ? "" : "pt"}`])}</td>
      <td class="r num">${x.then != null ? S(fmtSv(x, x.then), src, `${x.then_period} reading, the latest published by ${fmtDate(v.past)}`) : "–"}<small>${esc(x.then_period || "")}</small></td>
      <td><span class="chip ${x.side === "consumer" ? (x.strong === (x.key !== "infl_exp") ? "bull" : "bear") : x.strong ? "bull" : "bear"}">${x.side === "consumer" ? (x.key === "infl_exp" ? (x.strong ? "Worried" : "Calm") : (x.strong ? "Upbeat" : "Gloomy")) : x.strong ? "Upbeat" : "Cautious"}</span></td></tr>`;
  }).join("");
  $("#monCard").innerHTML = `<header class="card-h"><div><h2>Checking the thesis: what businesses and consumers say</h2>
      <p class="hint">${esc(vd.verdict || "")}${vd.detail ? ". " : ""}${srcify(vd.detail || "", "fred:UMCSENT")} Each reading is compared with its average since 2000; hover the average for the calculation.</p></div></header>
    <div class="tbl-wrap"><table><thead><tr><th>Measure</th><th class="r">Latest</th><th class="r">Avg since 2000</th><th class="r">At window start</th><th>Reads</th></tr></thead><tbody>${rows || `<tr><td colspan="5" class="muted">Survey data unavailable.</td></tr>`}</tbody></table></div>`;
  const tl = s.timeline || [];
  const kind = { episode: "Chapter", fed: "Fed", news: "News" };
  $("#fisCard").innerHTML = `<header class="card-h"><div><h2>What happened, in order</h2><p class="hint">${win}. Chapters of the story, Fed decisions${v.mode === "near" ? " and the first verified headline for each story" : ""}. Each item links to or names its source.</p></div></header>
    <ul class="events">${tl.map((e) => `<li><span class="d">${e.kind === "episode" ? D(e.date).toLocaleDateString("en-US", { month: "short", year: "numeric" }) : fmtDate(e.date)}</span>
      <span><span class="chip">${kind[e.kind] || ""}</span> ${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.text)}</a> <span class="muted">· ${esc(e.source || "")}</span>` : e.kind === "fed" ? S(esc(e.text), "fred:DFEDTARU", fmtDate(e.date)) : esc(e.text)}</span></li>`).join("") || `<li class="muted">No dated events in this window.</li>`}</ul>`;
}
function fmtVal(r, x) {
  if (x == null) return "–";
  const v = Number(x).toFixed(r.decimals);
  return { "%": `${v}%`, "% y/y": `${v}%`, "% saar": `${v}%`, "$tn": `$${v}tn`, "$/bbl": `$${v}`, "$/gal": `$${v}`, "k/mo": `${v}k`, k: `${v}k` }[r.unit] ?? v;
}
const UNIT_NOTE = { index: "index", "% y/y": "year over year", "% saar": "annualized", "k/mo": "jobs per month", k: "thousands", "$tn": "trillions", "$/bbl": "per barrel", "$/gal": "per gallon", "%": "" };
function fmtChg(r) {
  if (r.change == null) return "–";
  if (r.then && r.then.period === r.now.period) return `<span class="muted">no new reading</span>`;
  const pt = r.unit.startsWith("%");
  const u = pt ? "pt" : r.unit === "$tn" ? "tn" : r.unit.startsWith("k") ? "k" : "";
  return C(`${sgn(r.change, r.decimals)}${u}`, `fred:${r.series}`, [`${fmtVal(r, r.now.value)} (${r.now.period}) − ${fmtVal(r, r.then.value)} (${r.then.period}) = ${sgn(r.change, r.decimals)}${u}`]);
}
function renderScorecard(v) {
  const body = (groups) => groups.map((g) => {
    const rows = v.scorecard.filter((r) => r.group === g);
    if (!rows.length) return "";
    return `<tr class="group"><td colspan="4">${esc(g)}</td></tr>` + rows.map((r) => `<tr>
      <td>${esc(r.label)}${UNIT_NOTE[r.unit] ? `<small>${esc(UNIT_NOTE[r.unit])}</small>` : ""}</td>
      <td class="r num">${r.then ? S(fmtVal(r, r.then.value), `fred:${r.series}`, `${r.then.period} reading, the latest published by ${fmtDate(v.past)}`) : "–"}<small>${r.then ? esc(r.then.period) : ""}</small></td>
      <td class="r num">${S(fmtVal(r, r.now.value), `fred:${r.series}`, `${r.now.period} reading, the latest published`)}<small>${esc(r.now.period)}</small></td>
      <td class="r num">${fmtChg(r)}</td></tr>`).join("");
  }).join("");
  $("#scoreCard").innerHTML = `
    <header class="card-h"><div><h2>Macro indicators</h2><p class="hint">"At start" is the latest reading published by ${fmtDate(v.past)}; "Latest" is the newest published reading. The small date under each value is the period the data covers (for example, Sep 2026 CPI). pt = percentage points. Hover any value for its source.</p></div></header>
    <div class="score-grid">${[v.groups.slice(0, 3), v.groups.slice(3)].map((gs) => `<div class="tbl-wrap"><table>
      <thead><tr><th>Indicator</th><th class="r">At start</th><th class="r">Latest</th><th class="r">Change</th></tr></thead>
      <tbody>${body(gs)}</tbody></table></div>`).join("")}</div>`;
}
function renderNews(v) {
  if (v.mode && v.mode !== "near") {
    $("#newsCard").innerHTML = `
      <header class="card-h"><div><h2>The chapters in the window</h2><p class="hint">Over windows longer than two years, today's headlines are no guide to what moved yields. These are the episodes of the period, each told as a story; chapters after 2025 are described from the data only.</p></div></header>
      <div class="scroll"><ul class="events">${v.events.map((e) => `<li><span class="d">${D(e.from + "-01").toLocaleDateString("en-US", { month: "short", year: "numeric" })}${e.to !== e.from ? ` – ${D(e.to + "-01").toLocaleDateString("en-US", { month: "short", year: "numeric" })}` : ""}</span><span>${srcify(e.text, "fred:GS10")}</span></li>`).join("") || `<li class="muted">No documented events in this window.</li>`}</ul></div>`;
    return;
  }
  const tab = state.newsTab === "since" && v.since.length ? "since" : "window";
  $("#newsCard").innerHTML = `
    <header class="card-h"><div><h2>Headlines behind the story</h2><p class="hint">${tab === "window" ? `Verified outlets, ${fmtDate(v.past)} to ${fmtDate(v.asof)}, tagged by theme. Each headline links to its source.` : `Published after the ${fmtDate(v.asof)} close; context for what comes next, not causes of this move.`}</p></div>
      <div class="subtabs" role="group" aria-label="Headline window">
        <button type="button" data-nt="window" class="${tab === "window" ? "on" : ""}">In window (${v.headlines.length})</button>
        <button type="button" data-nt="since" class="${tab === "since" ? "on" : ""}">Since close (${v.since.length})</button>
      </div></header>
    <div class="scroll">${newsList(tab === "window" ? v.headlines : v.since, "No verified headlines matched this window.")}</div>`;
  $$("#newsCard [data-nt]").forEach((b) => b.addEventListener("click", () => { state.newsTab = b.dataset.nt; renderNews(v); }));
}

async function loadHistory() {
  let h;
  try { h = await api("/api/history"); } catch { return; }
  const draw = () => {
    const c1 = css("--series-1"), c2 = css("--series-2"), n = h.dates.length - 1;
    const o = baseOpts((v) => `${v > 0 ? "+" : ""}${v}`, "U.S. Treasury par yields; spreads computed by the dashboard");
    o.scales.x.ticks.callback = function (v) { return shortDate(this.getLabelForValue(v)); };
    o.scales.x.ticks.maxTicksLimit = 7;
    o.scales.y.grid.color = (ctx) => (ctx.tick.value === 0 ? css("--muted") : css("--grid"));
    setCallbacks(o, { title: (it) => fmtDate(it[0].label), label: (ctx) => ` ${ctx.dataset.label}: ${sgn(ctx.parsed.y)}bp` });
    o.plugins.valueLabels = { sets: [
      { index: 0, fmt: (v) => `${sgn(v)}bp`, pos: "above", color: c1, only: (i) => i === n || i === 0 },
      { index: 1, fmt: (v) => `${sgn(v)}bp`, pos: "below", color: c2, only: (i) => i === n || i === 0 },
    ] };
    makeChart("slopeChart", {
      type: "line",
      data: { labels: h.dates, datasets: [
        { label: "2s10s (10Y − 2Y)", data: h["2s10s"], borderColor: c1, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.2 },
        { label: "3m10y (10Y − 3M)", data: h["3m10y"], borderColor: c2, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.2 },
      ] },
      options: o,
    });
    $("#slopeLegend").innerHTML = legendHTML([{ label: "2s10s (10Y − 2Y)", color: c1 }, { label: "3m10y (10Y − 3M)", color: c2 }]);
  };
  redraws.slope = draw;
  draw();
}

/* =====================================================================
   SUPPLY: bills, notes and bonds ahead, each against its last equivalent auction
   ===================================================================== */
const MIX = [["indirect_pct", "Indirect", "var(--series-1)"], ["direct_pct", "Direct", "var(--series-2)"], ["dealer_pct", "Dealers", "var(--series-3)"]];
const mixLegend = legendHTML(MIX.map(([, l, c]) => ({ label: l, color: c, sq: true })));
function mixBar(m) {
  if (!m || m.indirect_pct == null) return "–";
  const note = `Share of competitive awards, auction of ${fmtDate(m.auction_date)}`;
  return S(`<div class="mix" role="img" aria-label="${MIX.map(([k, l]) => `${l} ${Math.round(m[k])}%`).join(", ")}">
    ${MIX.map(([k, l, c]) => `<span style="width:${m[k]}%;background:${c}">${m[k] >= 12 ? Math.round(m[k]) + "%" : ""}</span>`).join("")}</div>
    <div class="mix-l">${MIX.map(([k, l]) => `${l} ${Math.round(m[k])}%`).join(" · ")}</div>`, "td", note, m.results_pdf);
}
const rateFmt = (v, kind) => (v == null ? "–" : kind === "discount margin" ? `${fx(v * 100, 1)}bp` : `${fx(v, 3)}%`);
const bpS = (v, d = 1) => `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toFixed(d)}bp`;
const avgLine = (vals, d = 2) => `(${vals.map((v) => (v < 0 ? `(−${fx(-v, d)})` : fx(v, d))).join(" + ")}) ÷ ${vals.length} = ${fx(vals.reduce((s, v) => s + v, 0) / vals.length, d)}`;

// Prior-six average with its arithmetic: every auction used, then the sum.
function avgCalc(avg, field, label, d = 2, unit = "") {
  const pr = (avg?.prior || []).filter((p) => p[field] != null);
  if (!pr.length) return [];
  return [`${label}, prior ${pr.length} equivalent auctions:`, ...pr.map((p) => `  ${fmtDate(p.date)}   ${fx(p[field], d)}${unit}`),
          `${avgLine(pr.map((p) => p[field]), d)}${unit}`];
}
// How Strong / In line / Soft was decided, line by line.
function qualityCalc(m, avg) {
  if (!avg || !avg.basis) return [];
  if (avg.basis === "market") {
    const k = avg.mkt, pr = (avg.prior || []).filter((p) => p.gap != null), t = avg.threshold;
    return [`${k.rate_kind[0].toUpperCase() + k.rate_kind.slice(1)} ${fx(k.rate, 3)}% (auction of ${fmtDate(k.date)})`,
      `− ${k.par_label} at the ${shortDate(k.date)} close ${fx(k.par, 3)}%`,
      `= ${bpS(k.gap_bp)} vs the market that day`,
      `− usual gap for this security ${bpS(avg.usual_gap)}`,
      `   ${avgLine(pr.map((p) => p.gap), 1)}bp`,
      `   (${pr.map((p) => `${shortDate(p.date)} ${bpS(p.gap)}`).join(", ")})`,
      `= ${bpS(avg.tail_bp)} ${avg.tail_bp > 0 ? "cheaper" : "richer"} than the market expected`,
      `Rule: ≥ +${fx(t, 1)}bp Soft (tailed) · ≤ −${fx(t, 1)}bp Strong (stopped through) · otherwise In line`,
      "The closing yield stands in for the when-issued yield at the 1pm deadline, which is not free."];
  }
  return [`No same-day market yield for this security, so demand decides:`,
    `score = (bid-to-cover ${fx(m.btc)} − ${fx(avg.btc)}) ÷ 0.10`,
    `      + (dealers ${fx(avg.dealer, 1)}% − ${fx(m.dealer_pct, 1)}%) ÷ 3`,
    `      + (indirect ${fx(m.indirect_pct, 1)}% − ${fx(avg.indirect, 1)}%) ÷ 3 = ${fx(avg.score, 1)}`,
    "Rule: ≥ +1.5 Strong · ≤ −1.5 Soft · otherwise In line (averages are the prior six auctions)"];
}
const resultChip = (q, m, avg) => (q ? C(`<span class="chip ${q === "Strong" ? "bull" : q === "Soft" ? "bear" : ""}">${q}</span>`, "td,ust_par", qualityCalc(m, avg)) : "–");
const vsMarket = (avg) => (avg && avg.basis === "market" ? `priced ${fx(Math.abs(avg.tail_bp), 1)}bp ${avg.tail_bp > 0 ? "cheaper" : "richer"} than expected` : avg && avg.basis === "demand" ? "demand vs prior 6" : "");
const isinTag = (isin) => (isin ? `<span class="isin" data-isin="${esc(isin)}" title="Click to copy">${C(esc(isin), "isin", [`US + CUSIP ${isin.slice(2, 11)} + check digit ${isin.slice(-1)}`])}</span>` : "");

async function loadSupply() {
  if (state.loaded.supply) return;
  state.loaded.supply = true;
  const [au, tn] = await Promise.allSettled([api("/api/auctions"), api("/api/treasury-news")]);
  if (au.status === "fulfilled") renderSupply(au.value);
  else { $("#supplyStats").innerHTML = errBox(au.reason); state.loaded.supply = false; }
  if (tn.status === "fulfilled") renderDebt(tn.value);
  else $("#buybackCard").innerHTML = `<div class="pad">${errBox(tn.reason)}</div>`;
}

const aucId = (u) => `auc-${u.auction_date}-${shortSec(u.security).replace(/\W+/g, "-")}`;
function openState() { try { return JSON.parse(localStorage.getItem("ustd-supply-open") || "{}"); } catch { return {}; } }
function saveOpen() { try { localStorage.setItem("ustd-supply-open", JSON.stringify(Object.fromEntries($$(".auc-sec").map((d) => [d.dataset.group, d.open])))); } catch {} }

function auctionTable(group, rows, curveDate) {
  const bills = group === "Bills";
  const title = { Bills: "Bills ahead (4 to 52 weeks)", Notes: "Notes ahead (2 to 10 years, incl. TIPS and FRNs)", Bonds: "Bonds ahead (20 and 30 years)" }[group];
  const kv = (k, v, sub = "") => `<div class="akv"><span class="k">${k}</span><span class="v">${v}${sub ? `<small>${sub}</small>` : ""}</span></div>`;
  const mktSrcOf = (u) => (u.tips ? "ust_real" : "ust_par");
  const vsLast = (u) => {
    const l = u.last;
    if (u.now_vs_last_bp == null || !l) return "–";
    const lastR = bills ? l.investment_rate : l.stop;
    return `<span class="${dirCls(u.now_vs_last_bp)}">${C(`${sgn(u.now_vs_last_bp)}bp`, `${mktSrcOf(u)},td`,
      [`Market now: ${u.secondary_label} ${fx(u.secondary, 3)}% (${fmtDate(u.secondary_date || curveDate)} close)`,
       `− last auction's ${bills ? "investment rate" : "high yield"} ${fx(lastR, 3)}% (${fmtDate(l.auction_date)})`,
       `= ${sgn(u.now_vs_last_bp)}bp: ${u.now_vs_last_bp > 0 ? "should clear at a higher yield than last time" : u.now_vs_last_bp < 0 ? "should clear at a lower yield than last time" : "same level"}`])}</span>`;
  };
  const row = (u) => {
    const l = u.last;
    const annNote = `Announcement of ${fmtDate(u.announcement_date)}`;
    const resNote = l ? `Results of the ${fmtDate(l.auction_date)} auction` : "";
    const lastRate = !l ? "–" : bills ? `${rateFmt(l.stop)} discount` : rateFmt(l.stop, l.stop_kind);
    const lastRateSub = !l ? "" : bills ? `${S(`${fx(l.investment_rate, 3)}%`, "td", resNote, l.results_pdf)} investment rate` : (l.stop_kind === "yield" ? "" : l.stop_kind);
    const mktNote = `${u.secondary_label || ""}, ${fmtDate(u.secondary_date || curveDate)} close`;
    const size = u.offering_bn ? S(`$${fx(u.offering_bn, 0)}bn`, "td_upcoming", annNote, u.announcement_pdf) : `<span class="muted">TBA ${shortDate(u.announcement_date)}</span>`;
    const sizeChg = u.offering_bn && l && l.offering_bn ? (Math.abs(u.offering_bn - l.offering_bn) < 0.5 ? "same as last" :
      `${C(`${sgn(u.offering_bn - l.offering_bn)}bn`, "td_upcoming,td", [`$${fx(u.offering_bn, 0)}bn now − $${fx(l.offering_bn, 0)}bn on ${fmtDate(l.auction_date)}`])} vs last`) : "";
    const avg = u.last_avg || {};
    return `<details class="auc" id="${aucId(u)}">
      <summary class="auc-row">
        <span class="d">${shortDate(u.auction_date)}<small>${D(u.auction_date).toLocaleDateString("en-US", { weekday: "short" })}</small></span>
        <span class="n">${esc(shortSec(u.security))}${u.reopening ? ` <span class="chip">Reopening</span>` : ""}<small>${isinTag(u.isin) || "ISIN when announced"}</small></span>
        <span class="r num">${size}</span>
        <span class="r num">${u.secondary != null ? S(`${fx(u.secondary, 2)}%`, mktSrcOf(u), mktNote) : "–"}</span>
        <span class="r num">${vsLast(u)}</span>
        <span>${l ? resultChip(u.last_quality, l, avg) : "–"}<small>${l ? `${shortDate(l.auction_date)} · ${esc(vsMarket(avg))}` : "no prior auction"}</small></span>
        <span class="tog" aria-hidden="true"></span>
      </summary>
      <div class="auc-g">
        <div><div class="label">Upcoming auction</div>
          ${kv("Size", u.offering_bn ? S(`$${fx(u.offering_bn, 0)}bn`, "td_upcoming", annNote, u.announcement_pdf) : "To be announced", u.offering_bn ? sizeChg : fmtDate(u.announcement_date))}
          ${u.closing_time ? kv("Bids close", S(esc(u.closing_time) + " ET", "td_upcoming", annNote, u.announcement_pdf)) : ""}
          ${kv("Settles", S(fmtDate(u.issue_date), "td_upcoming"), u.maturity_date ? `matures ${fmtDate(u.maturity_date)}` : "")}
          ${kv("ISIN", u.isin ? isinTag(u.isin) : "–", u.cusip ? `CUSIP ${esc(u.cusip)}` : "")}
        </div>
        <div><div class="label">Market now · ${shortDate(curveDate)} close</div>
          ${kv("Trading at", u.secondary != null ? S(`${fx(u.secondary, 2)}%`, mktSrcOf(u), mktNote) : "n/a", esc(u.secondary_label || ""))}
          ${bills && u.secondary != null && state.strip?.sofr ? kv("vs SOFR", C(`${sgn((u.secondary - state.strip.sofr.rate) * 100)}bp`, `${mktSrcOf(u)},sofr`,
              [`Bill yield ${fx(u.secondary, 3)}% − SOFR ${fx(state.strip.sofr.rate, 3)}% (${fmtDate(state.strip.sofr.date)}) = ${sgn((u.secondary - state.strip.sofr.rate) * 100)}bp`]), "carry over overnight funding") : ""}
          ${kv("vs last auction", vsLast(u), u.now_vs_last_bp == null ? "" : u.now_vs_last_bp > 2 ? "should clear at a higher yield" : u.now_vs_last_bp < -2 ? "should clear at a lower yield" : "about the same level")}
        </div>
        <div class="wide"><div class="label">Last equivalent auction${l ? ` · ${fmtDate(l.auction_date)}` : ""}${l && l.isin ? ` · ${isinTag(l.isin)}` : ""}</div>
          ${l ? `<div class="akv-row">
            ${kv("Size", S(`$${fx(l.offering_bn, 0)}bn`, "td", resNote, l.results_pdf))}
            ${kv(bills ? "High rate" : "High yield", S(lastRate, "td", resNote, l.results_pdf), lastRateSub)}
            ${kv("Bid-to-cover", S(fx(l.btc), "td", resNote, l.results_pdf), avg.btc != null ? `avg ${C(fx(avg.btc), "td", avgCalc(avg, "btc", "Bid-to-cover"))} (prior ${avg.n})` : "")}
            ${kv("vs market", resultChip(u.last_quality, l, avg), esc(vsMarket(avg)))}
          </div>
          ${kv("Award mix", mixBar(l))}
          ${avg.dealer != null ? `<p class="why" style="margin:2px 0 6px">Prior-${avg.n} averages: dealers ${C(`${fx(avg.dealer, 1)}%`, "td", avgCalc(avg, "dealer", "Dealer share", 1, "%"))}, indirect ${C(`${fx(avg.indirect, 1)}%`, "td", avgCalc(avg, "indirect", "Indirect share", 1, "%"))}. Fewer bonds left with dealers means more end-investor demand.</p>` : ""}
          ${l.results_pdf ? `<a class="small" href="${esc(l.results_pdf)}" target="_blank" rel="noopener">Official results (PDF)</a>` : ""}` : `<p class="muted">No equivalent auction in the past year.</p>`}
        </div>
      </div>
      <p class="take"><b>Setup.</b> ${srcify(u.takeaway, "td")}</p>
    </details>`;
  };
  const isOpen = openState()[group] ?? true;
  const sized = rows.reduce((s, u) => s + (u.offering_bn || 0), 0);
  const summary = rows.length ? `${rows.length} auction${rows.length > 1 ? "s" : ""} · next ${shortDate(rows[0].auction_date)}${sized ? ` · $${fx(sized, 0)}bn sized` : ""}` : "None announced";
  const head = `<div class="auc-row auc-head"><span>Date</span><span>Security · ISIN</span><span class="r">Size</span><span class="r">${bills ? "Market yield" : "Trading at"}</span><span class="r">vs last auction</span><span>Last auction vs market</span><span></span></div>`;
  return `<details class="auc-sec" data-group="${group}" ${isOpen ? "open" : ""}>
    <summary class="card-h sum"><div><h2>${title}</h2><p class="hint">${summary}. Click a row for size, award mix and the last auction's full result.</p></div><span class="tog" aria-hidden="true"></span></summary>
    <div class="auc-list">${rows.length ? head + rows.map(row).join("") : `<p class="muted pad">No ${group.toLowerCase()} auctions announced for the coming week. Treasury's <a href="https://home.treasury.gov/system/files/221/Tentative-Auction-Schedule.pdf" target="_blank" rel="noopener">tentative schedule</a> lists later dates.</p>`}</div>
  </details>`;
}

function renderSupply(v) {
  const sm = v.summary;
  const mt = sm.metrics || {};
  const nc = mt.net_cash, du = mt.duration, bs = mt.bill_share, de = mt.demand;
  const demandCalc = de ? [`Each coupon auction: its rate minus that day's closing market yield, minus the security's usual gap (prior six). ±${fx(de.threshold, 1)}bp decides.`,
    ...de.reads.map((r) => `${shortDate(r.date)} ${r.security.padEnd(13)} ${r.basis === "market" ? `${bpS(r.gap)} − usual ${bpS(r.usual)} = ${bpS(r.tail)}` : `demand score ${fx(r.score, 1)}`} → ${r.quality}`)] : [];
  $("#supplyStats").innerHTML = `
    <div class="stat"><span class="eyebrow">Net new cash, announced auctions</span>
      <div class="v ${nc ? (nc.net_bn > 0 ? "up" : "down") : ""}">${nc ? C(`${nc.net_bn > 0 ? "+" : "−"}$${fx(Math.abs(nc.net_bn), 0)}bn`, "td_upcoming", [`$${fx(nc.gross_bn, 1)}bn offered (${nc.auctions} sized auctions)`, `− $${fx(nc.maturing_bn, 1)}bn publicly held securities maturing on the same settlement dates`, `= ${nc.net_bn > 0 ? "+" : "−"}$${fx(Math.abs(nc.net_bn), 1)}bn`]) : "–"}</div>
      <div class="s">${nc ? `${S(`$${fx(nc.gross_bn, 0)}bn`, "td_upcoming")} sold vs ${S(`$${fx(nc.maturing_bn, 0)}bn`, "td_upcoming", "Publicly held securities maturing on the settlement date")} maturing, settling ${nc.settle.map(shortDate).join(", ")}. ${nc.net_bn < 0 ? "A paydown returns cash to investors." : "A raise drains cash from money markets."}${nc.unsized ? ` ${nc.unsized} more not yet sized.` : ""}` : "No sized auctions with maturity data yet."}</div></div>
    <div class="stat"><span class="eyebrow">Duration supply ahead</span>
      <div class="v">${du ? C(`$${fx(du.eq10_bn, 0)}bn`, "td_upcoming,ust_par", [`10-year equivalent = size × duration ÷ 10Y duration (${fx(du.d10, 2)} at ${fx(du.y10, 2)}%)`, ...du.parts.map((p) => `${p.security}: $${fx(p.size_bn, 0)}bn × ${fx(p.dur, 2)} ÷ ${fx(du.d10, 2)} = $${fx(p.eq10_bn, 1)}bn${p.estimated ? " (size est.)" : ""}`), `Total = $${fx(du.eq10_bn, 1)}bn`]) : "–"}</div>
      <div class="s">${du ? `in 10-year equivalents: ${du.parts.map((p) => `${esc(p.security)} ${S(`$${fx(p.size_bn, 0)}bn`, "td", p.estimated ? "Size not yet announced: last equivalent auction's size used" : "Announced size")}${p.estimated ? " (est.)" : ""}`).join(", ")}. This is the rate risk the market has to absorb.` : "No coupon auctions ahead."}</div></div>
    <div class="stat"><span class="eyebrow">Bills share of marketable debt</span>
      <div class="v">${bs ? C(`${fx(bs.pct, 1)}%`, "mspd", [`Bills $${fx(bs.bills_tn, 2)}tn ÷ marketable debt $${fx(bs.total_tn, 2)}tn = ${fx(bs.pct, 1)}% (${fmtDate(bs.date)})`]) : "–"}</div>
      <div class="s">${bs ? `${fmtDate(bs.date)}${bs.pct_1y != null ? `, vs ${S(`${fx(bs.pct_1y, 1)}%`, "mspd", fmtDate(bs.date_1y))} a year earlier` : ""}. The Treasury Borrowing Advisory Committee has long recommended ${S("about 20%", "tbac", "TBAC's longstanding guidance for the bill share of marketable debt")}; more bills means less duration for the market to absorb, but more rollover risk.` : ""}</div></div>
    <div class="stat"><span class="eyebrow">Coupon auctions vs market, last 10</span>
      <div class="v words">${de ? C(`${de.soft} soft · ${de.strong} strong`, "td,ust_par", demandCalc) : "–"}</div>
      <div class="s">${de ? `Soft = priced at least ${fx(de.threshold, 1)}bp cheaper than the market expected (a tail); strong = at least ${fx(de.threshold, 1)}bp richer. Soft: ${de.reads.filter((r) => r.quality === "Soft").map((r) => `${esc(r.security.replace(/-Year (Note|Bond)/, "Y"))} ${shortDate(r.date)}`).join(", ") || "none"}. Strong: ${de.reads.filter((r) => r.quality === "Strong").map((r) => `${esc(r.security.replace(/-Year (Note|Bond)/, "Y"))} ${shortDate(r.date)}`).join(", ") || "none"}. Hover the count for each auction's calculation.` : ""}</div></div>`;
  ["Bills", "Notes", "Bonds"].forEach((g) => { $(`#${g.toLowerCase()}Card`).innerHTML = auctionTable(g, v.groups[g], v.curve_date); });
  const all = ["Bills", "Notes", "Bonds"].flatMap((g) => v.groups[g].map((u) => ({ ...u, g }))).sort((a, b) => a.auction_date.localeCompare(b.auction_date));
  $("#jumpBar").innerHTML = `<span class="eyebrow">Jump to</span>${all.filter((u) => u.g !== "Bills").map((u) =>
    `<button type="button" class="chip jump" data-jump="${aucId(u)}" data-group="${u.g}">${shortDate(u.auction_date)} · ${esc(shortSec(u.security).replace(" Note", "").replace(" Bond", ""))}</button>`).join("")}
    <span class="spacer"></span><button type="button" class="btn quiet" id="expandAll">Expand all</button><button type="button" class="btn quiet" id="collapseAll">Collapse all</button>`;
  $$("#jumpBar [data-jump]").forEach((b) => b.addEventListener("click", () => {
    const sec = $(`#${b.dataset.group.toLowerCase()}Card details`); sec.open = true; saveOpen();
    const el = document.getElementById(b.dataset.jump); el.open = true; el.scrollIntoView({ behavior: "smooth", block: "start" }); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1600);
  }));
  $("#expandAll").addEventListener("click", () => { $$(".auc-sec, .auc").forEach((d) => (d.open = true)); saveOpen(); });
  $("#collapseAll").addEventListener("click", () => { $$(".auc").forEach((d) => (d.open = false)); saveOpen(); });
  $$(".auc-sec").forEach((d) => d.addEventListener("toggle", saveOpen));

  $("#resultsCard").innerHTML = `
    <header class="card-h"><div><h2>Note and bond results, past 45 days</h2><p class="hint">"vs market" compares each auction's yield with where the same maturity closed that day, adjusted for that security's usual gap: ${fx(de?.threshold ?? 2, 1)}bp or more cheaper is soft (it tailed), ${fx(de?.threshold ?? 2, 1)}bp or more richer is strong. Hover any result to see the calculation.</p></div><div class="legend">${mixLegend}</div></header>
    <div class="tbl-wrap"><table><thead><tr><th>Auction date</th><th>Security · ISIN</th><th class="r">Size</th><th class="r">High yield</th><th class="r">vs market</th><th class="r">Bid-to-cover</th><th>Award mix</th><th>Result</th><th></th></tr></thead>
    <tbody>${v.recent_coupons.map((m) => {
      const n = `Results of the ${fmtDate(m.auction_date)} auction`, a = m.avg || {};
      return `<tr>
      <td class="num">${fmtDate(m.auction_date)}</td><td class="sec">${esc(shortSec(m.security))}<small>${isinTag(m.isin)} · ${m.reopening ? "Reopening" : "New issue"}${m.coupon != null && m.stop_kind !== "discount margin" ? ` · coupon ${S(`${fx(m.coupon, 3)}%`, "td", n, m.results_pdf)}` : ""}</small></td>
      <td class="r num">${S(`$${fx(m.offering_bn, 0)}bn`, "td", n, m.results_pdf)}</td><td class="r num">${S(rateFmt(m.stop, m.stop_kind), "td", n, m.results_pdf)}<small>${esc(m.stop_kind === "yield" ? "" : m.stop_kind)}</small></td>
      <td class="r num ${a.basis === "market" ? dirCls(a.tail_bp) : ""}">${a.basis === "market" ? C(bpS(a.tail_bp), "td,ust_par", qualityCalc(m, a)) : "–"}<small>${a.basis === "market" ? (a.tail_bp > 0 ? "cheaper" : "richer") : ""}</small></td>
      <td class="r num">${S(fx(m.btc), "td", n, m.results_pdf)}<small>avg ${C(fx(m.avg_btc), "td", avgCalc(a, "btc", "Bid-to-cover"))}</small></td><td>${mixBar(m)}</td>
      <td>${resultChip(m.quality, m, a)}</td>
      <td>${m.results_pdf ? `<a href="${esc(m.results_pdf)}" target="_blank" rel="noopener">Results</a>` : ""}</td></tr>`;
    }).join("") || `<tr><td colspan="9" class="muted">No note or bond results in the past 45 days.</td></tr>`}</tbody></table></div>`;
}

// Copy an ISIN without toggling the row it sits in.
document.addEventListener("click", (e) => {
  const el = e.target.closest && e.target.closest(".isin");
  if (!el) return;
  e.preventDefault(); e.stopPropagation();
  navigator.clipboard?.writeText(el.dataset.isin).then(() => { el.classList.add("copied"); setTimeout(() => el.classList.remove("copied"), 1200); }).catch(() => {});
}, true);

function renderDebt(t) {
  const today = new Date().toISOString().slice(0, 10);
  $("#buybackCard").innerHTML = `
    <header class="card-h"><div><h2>Treasury buybacks</h2><p class="hint">Treasury buying back older bonds. "Offered / max": how much holders offered vs the most Treasury would buy; above 1x means more sellers than Treasury needed.</p></div><a style="font-size:12.5px" href="https://fiscaldata.treasury.gov/datasets/treasury-securities-buybacks/" target="_blank" rel="noopener">Fiscal Data</a></header>
    <div class="tbl-wrap"><table><thead><tr><th>Operation date · maturities</th><th class="r">Max to buy</th><th class="r">Bought</th><th class="r">Offered / max</th></tr></thead>
    <tbody>${t.buybacks.slice(0, 10).map((b) => {
      const n = `Buyback operation of ${fmtDate(b.date)}`;
      return `<tr>
      <td class="sec">${fmtDate(b.date)} · ${esc(b.bucket || "")}${b.date >= today && b.accepted_bn == null ? ` <span class="chip solid">Scheduled</span>` : ""}<small>${esc(b.type || "")} · ${esc(b.security_type || "")}</small></td>
      <td class="r num">${b.max_bn ? S("$" + fx(b.max_bn, 1) + "bn", "fiscal_bb", n) : "–"}</td>
      <td class="r num">${b.accepted_bn ? S("$" + fx(b.accepted_bn, 2) + "bn", "fiscal_bb", n) : "–"}</td>
      <td class="r num">${b.offered_bn && b.max_bn ? S(fx(b.offered_bn / b.max_bn, 1) + "x", "fiscal_bb", `$${fx(b.offered_bn, 1)}bn offered / $${fx(b.max_bn, 1)}bn maximum, ${n}`) : "–"}</td></tr>`;
    }).join("") || `<tr><td colspan="4" class="muted">No buyback operations returned.</td></tr>`}</tbody></table></div>`;
  $("#debtNewsCard").innerHTML = `
    <header class="card-h"><div><h2>Debt management news</h2><p class="hint">Buybacks, refunding and issuance, from Treasury and verified outlets. Each headline links to its source.</p></div>
      <a style="font-size:12.5px" href="https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding" target="_blank" rel="noopener">Quarterly refunding</a></header>
    <div class="scroll">${newsList(t.news, "No recent debt-management headlines from verified sources.")}</div>`;
}

/* =====================================================================
   FED
   ===================================================================== */
async function loadFed() {
  if (state.loaded.fed) return;
  state.loaded.fed = true;
  loadMoney();
  try { renderFed(await api("/api/fed")); }
  catch (e) { $("#fedStats").innerHTML = errBox(e); state.loaded.fed = false; }
}
function probBar(m, note) {
  const seg = (cls, p) => (p > 0.005 ? `<span class="${cls}" style="width:${p * 100}%">${p >= 0.1 ? pct(p) : ""}</span>` : "");
  return S(`<div class="prob" role="img" aria-label="Cut ${pct(m.p_cut)}, hold ${pct(m.p_hold)}, hike ${pct(m.p_hike)}">${seg("cut", m.p_cut)}${seg("hold", m.p_hold)}${seg("hike", m.p_hike)}</div>
    <div class="mix-l">cut ${pct(m.p_cut)} · hold ${pct(m.p_hold)} · hike ${pct(m.p_hike)}</div>`, "zq", note);
}
function renderFed(f) {
  const m = f.meetings, c = f.context, nxt = m[0], last = m[m.length - 1];
  const six = m.reduce((best, x) => (Math.abs(daysUntil(x.date) - 182) < Math.abs(daysUntil(best.date) - 182) ? x : best), m[0] || {});
  const pce = c.indicators.find((r) => r.key === "core_pce");
  const futDate = f.futures_time ? fmtDate(f.futures_time.slice(0, 10)) : "latest";
  const fut = `Futures prices as of ${futDate}`;
  const w1 = f.history["1W"].date, m1 = f.history["1M"].date;
  const hikes = (bp) => `about ${fx(Math.abs(bp) / 25, 1)} quarter-point ${bp >= 0 ? "hikes" : "cuts"}`;
  // "Priced by <meeting>": the expected rate, how it is computed, and what markets expected a month ago.
  const pricedTile = (x, withHistory = false) => {
    const then = withHistory ? f.history["1M"]?.post?.[x.date] : null;
    const calc = [`Expected EFFR after the ${fmtDate(x.date)} meeting ${fx(x.post, 2)}% (from futures)`,
      `− EFFR today ${fx(f.effr, 2)}% (${fmtDate(f.effr_date)})`, `= ${sgn(x.cum_bp)}bp ÷ 25bp = ${fx(Math.abs(x.cum_bp) / 25, 1)} quarter-point ${x.cum_bp >= 0 ? "hikes" : "cuts"}`];
    const thenTxt = then != null
      ? `A month ago (${fmtDate(m1)}), markets expected ${C(`${fx(then, 2)}%`, "zq", [`Futures prices on ${fmtDate(m1)} run through the same method: expected EFFR after the ${fmtDate(x.date)} meeting = ${fx(then, 2)}%`])} by then; now ${S(`${fx(x.post, 2)}%`, "zq", fut)}, ${C(`${Math.abs(x.post - then) < 0.005 ? "unchanged" : `${fx(Math.abs((x.post - then) * 100), 0)}bp ${x.post > then ? "higher" : "lower"}`}`, "zq", [`${fx(x.post, 2)}% now − ${fx(then, 2)}% on ${fmtDate(m1)} = ${sgn((x.post - then) * 100)}bp`, x.post > then ? "Markets now expect more tightening than a month ago." : "Markets now expect less tightening than a month ago."])}.`
      : `Expected rate ${S(`${fx(x.post, 2)}%`, "zq", fut)} vs ${S(`${fx(f.effr, 2)}%`, "effr", fmtDate(f.effr_date))} now.`;
    return `<div class="stat"><span class="eyebrow">Priced by ${fmtDate(x.date)}</span><div class="v ${dirCls(x.cum_bp)}">${C(`${sgn(x.cum_bp)}bp`, "zq,effr", calc, fut)}</div>
      <div class="s">${hikes(x.cum_bp)} from today's ${S(`${fx(f.effr, 2)}%`, "effr", fmtDate(f.effr_date))}. ${thenTxt}</div></div>`;
  };
  $("#fedStats").innerHTML = `
    <div class="stat"><span class="eyebrow">Fed funds target</span><div class="v">${S(`${fx(f.target_lo)}–${fx(f.target_hi)}%`, "fred:DFEDTARU,effr", `Target range as of ${fmtDate(f.effr_date)}`)}</div>
      <div class="s">Effective rate ${S(`${fx(f.effr)}%`, "effr", fmtDate(f.effr_date))} (${fmtDate(f.effr_date)})${c.real_policy_rate != null && pce ? `; real ${S(`${sgn(c.real_policy_rate, 2)}%`, "effr,fred:PCEPILFE", `EFFR ${fx(f.effr)}% minus core PCE ${fx(pce.now.value, 1)}% (${pce.now.period}), computed by the dashboard`)} after ${S(`${fx(pce.now.value, 1)}%`, "fred:PCEPILFE", `${pce.now.period} reading`)} core PCE (${esc(pce.now.period)})` : ""}</div></div>
    ${nxt ? `<div class="stat"><span class="eyebrow">Next FOMC · ${fmtDate(nxt.date)}, in ${daysUntil(nxt.date)} days</span>
      <div class="v words">${S(`${fomcOdds(nxt).label}`, "zq,fomc", fut)}</div>
      <div class="s">${S(fomcOdds(nxt).sentence, "zq,fomc", `${fut}; probabilities computed by the dashboard with the CME FedWatch method`)}${nxt.p_hold >= 0.01 ? ` (target stays at ${S(`${fx(f.target_lo)}–${fx(f.target_hi)}%`, "fred:DFEDTARU", "Current target range")})` : ""}.</div></div>
    ${pricedTile(six)}
    ${pricedTile(last, true)}` : ""}`;

  $("#meetingsCard").innerHTML = `
    <header class="card-h"><div><h2>Rate expectations by FOMC meeting</h2>
      <p class="hint">From ${S("CBOT 30-day fed funds futures", "zq", fut)} (prices as of ${futDate}), using the CME FedWatch method in 25bp steps. Read the first row as: ${nxt ? fomcOdds(nxt).sentence.replace(/^./, (c) => c.toLowerCase()) : "–"}. "Priced move" weights those odds: ${nxt ? `${pct(nxt.p_hike || nxt.p_cut)} × 25bp = ${sgn(nxt.delta_bp, 1)}bp` : "–"}. It is not a forecast of a partial move. Rates are the effective fed funds rate (EFFR), today ${S(`${fx(f.effr)}%`, "effr", fmtDate(f.effr_date))}.</p></div>
      <div class="legend">${legendHTML([{ label: "Cut", color: "var(--bull)", sq: true }, { label: "Hold", color: "var(--neutral)", sq: true }, { label: "Hike", color: "var(--bear)", sq: true }])}</div></header>
    <div class="tbl-wrap"><table><thead>
      <tr><th>Meeting</th><th class="r" title="Effective fed funds rate the market expects after this meeting">Expected rate</th><th class="r" title="Expected change at this meeting = probability of a move x 25bp">Priced move</th><th class="r" title="Expected rate after this meeting minus today's effective rate">Total vs today</th><th>Odds: cut / hold / hike</th><th title="Fed funds target range with the highest probability after this meeting">Most likely range</th>
      <th class="r sep" title="Change in the expected rate after this meeting since ${fmtDate(w1)}">Since ${shortDate(w1)}</th><th class="r" title="Change since ${fmtDate(m1)}">Since ${shortDate(m1)}</th></tr></thead>
    <tbody>${m.map((x) => {
      const n = `${fmtDate(x.date)} meeting; ${fut}`;
      return `<tr>
      <td class="num">${S(`<b>${fmtDate(x.date)}</b>`, "fomc")}${x.sep ? ` <span class="chip" title="Includes the Summary of Economic Projections (dot plot)">SEP</span>` : ""}</td>
      <td class="r num">${S(`${fx(x.post, 2)}%`, "zq", n)}</td><td class="r num ${dirCls(x.delta_bp)}">${S(`${sgn(x.delta_bp, 1)}bp`, "zq", n)}</td><td class="r num ${dirCls(x.cum_bp)}">${S(`${sgn(x.cum_bp, 1)}bp`, "zq,effr", n)}</td>
      <td>${probBar(x, n)}</td><td class="num">${x.most_likely ? `${S(`${esc(x.most_likely.range)}%`, "zq", n)}<small>${S(`${pct(x.most_likely.p)} probability`, "zq", n)}</small>` : "–"}</td>
      <td class="r num sep ${dirCls(x.shift_1W_bp)}">${x.shift_1W_bp == null ? "–" : S(sgn(x.shift_1W_bp, 0) + "bp", "zq", `Expected rate now minus the expected rate implied on ${fmtDate(w1)}`)}</td>
      <td class="r num ${dirCls(x.shift_1M_bp)}">${x.shift_1M_bp == null ? "–" : S(sgn(x.shift_1M_bp, 0) + "bp", "zq", `Expected rate now minus the expected rate implied on ${fmtDate(m1)}`)}</td></tr>`;
    }).join("") || `<tr><td colspan="8" class="muted">Futures prices unavailable.</td></tr>`}</tbody></table></div>
    <p class="hint pad" style="padding-top:8px">"Since" columns: how much the expected rate after each meeting has changed. Positive = markets now expect more hikes than they did then.</p>`;

  $("#watchCard").innerHTML = `
    <header class="card-h"><div><h2>What the Fed is reacting to</h2><p class="hint">The pricing above, read against the data the FOMC targets.</p></div></header>
    <ul class="bullets">${c.summary.map((l) => `<li>${srcify(l, "zq")}</li>`).join("")}</ul>
    <div class="label">The FOMC's dashboard (latest reading · a year earlier)</div>
    <div class="kv">${c.indicators.map((r) => `<span>${esc(r.label)}<small class="muted" style="display:block;font-size:11px">${esc(r.now.period)}${r.then && r.then.period !== r.now.period ? ` · ${S(fmtVal(r, r.then.value), `fred:${r.series}`, `${r.then.period} reading`)} in ${esc(r.then.period)}` : ""}</small></span><span class="v">${S(fmtVal(r, r.now.value), `fred:${r.series}`, `${r.now.period} reading`)}</span>`).join("")}</div>`;

  redraws.path = () => drawPath(f);
  drawPath(f);
  renderComms(c);
}
function renderComms(c) {
  const tab = state.commsTab;
  const lists = { news: c.news, speeches: c.speeches, press: c.press };
  $("#commsCard").innerHTML = `
    <header class="card-h"><h2>Fed communication</h2>
      <div class="subtabs" role="group" aria-label="Source">${[["news", "Coverage, past 7 days"], ["speeches", "Speeches"], ["press", "Press releases"]].map(([k, l]) => `<button type="button" data-ct="${k}" class="${tab === k ? "on" : ""}">${l}</button>`).join("")}</div></header>
    ${newsList(lists[tab] || [], "Nothing to show.", true)}`;
  $$("#commsCard [data-ct]").forEach((b) => b.addEventListener("click", () => { state.commsTab = b.dataset.ct; renderComms(c); }));
}
function drawPath(f) {
  const m = f.meetings, c1 = css("--series-1"), c2 = css("--series-2"), c3 = css("--series-3"), neutral = css("--neutral"), n = m.length - 1;
  const w1 = fmtDate(f.history["1W"].date), m1 = fmtDate(f.history["1M"].date);
  const o = baseOpts((v) => v.toFixed(2) + "%", "CBOT fed funds futures; implied rates computed by the dashboard");
  setCallbacks(o, { label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}%` });
  o.plugins.valueLabels = { sets: [
    { index: 0, fmt: (v) => v.toFixed(2), pos: "above", color: c1 },
    { index: 2, fmt: (v) => v.toFixed(2), pos: "below", color: c3, only: (i) => i === n },
  ] };
  makeChart("pathChart", {
    type: "line",
    data: { labels: m.map((x) => shortDate(x.date)), datasets: [
      { label: "Priced today", data: m.map((x) => x.post), borderColor: c1, backgroundColor: c1, borderWidth: 2, pointRadius: 3, pointHoverRadius: 6, tension: 0.2 },
      { label: `Priced ${w1}`, data: m.map((x) => f.history["1W"].post[x.date] ?? null), borderColor: c2, backgroundColor: c2, borderWidth: 2, borderDash: [6, 4], pointRadius: 3, pointHoverRadius: 6, tension: 0.2 },
      { label: `Priced ${m1}`, data: m.map((x) => f.history["1M"].post[x.date] ?? null), borderColor: c3, backgroundColor: c3, borderWidth: 2, borderDash: [2, 3], pointRadius: 3, pointHoverRadius: 6, tension: 0.2 },
      { label: "EFFR today", data: m.map(() => f.effr), borderColor: neutral, borderWidth: 1.5, borderDash: [3, 3], pointRadius: 0, pointHoverRadius: 0 },
    ] },
    options: o,
  });
  $("#pathLegend").innerHTML = legendHTML([{ label: "Priced today", color: c1 }, { label: `Priced ${w1}`, color: c2, dash: true }, { label: `Priced ${m1}`, color: c3, dash: true }, { label: `EFFR today, ${fx(f.effr)}%`, color: neutral, dash: true }]);
}

/* ---------- boot ---------- */
(function boot() {
  let t = "system";
  try { t = localStorage.getItem("cd-theme") || "system"; } catch {}
  if (t !== "system") document.documentElement.dataset.theme = t;
  $("#themeBtn").textContent = `Theme: ${t}`;
  loadStrip();
  loadHealth();
  loadStory();
  loadCurve();
  loadMatrix();
  loadHistory();
  const start = location.hash.slice(1);
  if (start === "auctions" || start === "fed") showTab(start);
  setTimeout(() => { loadSupply(); loadFed(); }, 3000);
  // Chart.js sizes axis labels with whatever font is loaded at draw time; redraw once the web fonts arrive.
  document.fonts?.ready.then(() => Object.values(redraws).forEach((fn) => fn()));
})();

/* ---------- contact: the address is assembled in the browser so simple scrapers don't harvest it ---------- */
(function contact() {
  const addr = ["jayveenmp", "gmail.com"].join("@");
  const a = $("#contactMail"), b = $("#copyMail");
  if (!a) return;
  a.textContent = addr;
  a.href = `mailto:${addr}?subject=${encodeURIComponent("US Treasuries Dashboard")}`;
  b.addEventListener("click", () => {
    navigator.clipboard?.writeText(addr).then(() => { b.textContent = "Copied"; setTimeout(() => (b.textContent = "Copy email"), 1500); })
      .catch(() => { const r = document.createRange(); r.selectNodeContents(a); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); });
  });
})();
