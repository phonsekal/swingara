/* IDX Swing Scanner frontend — vanilla JS, Tailwind classes. */
"use strict";

// ---------------------------------------------------------------- helpers
const $ = (id) => document.getElementById(id);

const IDR = new Intl.NumberFormat("id-ID", {
  style: "currency", currency: "IDR", maximumFractionDigits: 0,
});
const NUM = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

const VERDICT_STYLE = {
  MAXIMUM_CONVICTION_BUY: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  STRONG_BUY: "bg-teal-500/15 text-teal-300 border-teal-500/40",
  NEUTRAL_HOLD: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  WATCHLIST: "bg-sky-500/15 text-sky-300 border-sky-500/40",
  REJECTED: "bg-slate-600/15 text-slate-400 border-slate-600/40",
};

const GLOSSARY = [
  { term: "EMA20 / SMA50", def: "Rata-rata harga 20 & 50 hari terakhir. Harga > EMA20 > SMA50 artinya tren sedang naik." },
  { term: "Bollinger Band (20, 2σ)", def: "Pita di sekitar rata-rata harga. Lower band = area 'murah' relatif 20 hari; menyentuhnya = zona diskon." },
  { term: "RSI(14)", def: "Skala 0–100. >70 = overbought (mahal, rawan koreksi), <30 = oversold (murah)." },
  { term: "ATR(14)", def: "Rata-rata pergerakan harga harian. Dipakai untuk stop loss (2×ATR dari harga masuk)." },
  { term: "Nilai transaksi 20 hari", def: "Rata-rata Rp saham × volume 20 hari = likuiditas. Makin besar, makin mudah jual-beli." },
  { term: "Anchor / VWAP", def: "Rata-rata harga tertimbang volume selama lookback — proxy harga beli rata-rata broker. Harga ≤ anchor × 1,03 = masih dekat zona akumulasi." },
  { term: "nval (net value)", def: "Nilai beli − nilai jual sebuah broker dalam Rp. Positif = net buy (akumulasi), negatif = net sell (distribusi)." },
  { term: "TP1 / TP2 / SL", def: "Target profit 1 (+10%, jual 50% lot), target profit 2 (+20%, jual semua), stop loss (batas rugi)." },
  { term: "Lot", def: "Satuan transaksi IDX: 1 lot = 100 lembar saham." },
  { term: "Pullback", def: "Koreksi wajar dari harga tertinggi. Strategi ini membeli saat pullback ke zona diskon, bukan mengejar harga yang sudah naik." },
];

// verdict filter state
let verdictFilter = null;

function renderGlossary() {
  $("sc-glossary").innerHTML = GLOSSARY.map((g) =>
    `<div><span class="font-semibold text-slate-200">${g.term}</span> — ${g.def}</div>`).join("");
}
renderGlossary();

function renderFilterChips(counts) {
  const bar = $("sc-filter");
  const order = ["MAXIMUM_CONVICTION_BUY", "STRONG_BUY", "NEUTRAL_HOLD", "WATCHLIST", "REJECTED"];
  const chips = [`<button class="vfilter rounded-full border px-3 py-1 font-bold ${verdictFilter === null ? "border-cyan-400 bg-cyan-500/15 text-cyan-300" : "border-slate-700 text-slate-400 hover:text-slate-200"}" data-v="">Semua (${Object.values(counts).reduce((a, b) => a + b, 0)})</button>`];
  order.forEach((v) => {
    if (!counts[v]) return;
    const active = verdictFilter === v;
    chips.push(`<button class="vfilter rounded-full border px-3 py-1 font-bold ${active ? "border-cyan-400 bg-cyan-500/15 text-cyan-300" : "border-slate-700 text-slate-400 hover:text-slate-200"}" data-v="${v}">${v.replace(/_/g, " ")} (${counts[v]})</button>`);
  });
  bar.innerHTML = chips.join(" ");
  bar.classList.remove("hidden");
  bar.classList.add("flex");
  bar.querySelectorAll(".vfilter").forEach((b) => {
    b.addEventListener("click", () => {
      verdictFilter = b.dataset.v || null;
      renderFilterChips(counts);
      applyVerdictFilter();
    });
  });
}

function applyVerdictFilter() {
  document.querySelectorAll(".vcard").forEach((el) => {
    const show = !verdictFilter || el.dataset.verdict === verdictFilter;
    el.classList.toggle("hidden", !show);
  });
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

function fmt(n, digits = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(digits) + " M";
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(digits) + " jt";
  return NUM.format(n);
}

function setErr(id, msg) {
  const el = $(id);
  if (msg) { el.textContent = msg; el.classList.remove("hidden"); }
  else el.classList.add("hidden");
}

function badge(text, cls) {
  return `<span class="rounded-full border px-2.5 py-0.5 text-xs font-bold ${cls}">${text}</span>`;
}

function card(title, rows) {
  return `
    <div class="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
      <h4 class="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">${title}</h4>
      <div class="grid grid-cols-2 gap-x-3 gap-y-1.5 text-sm">
        ${rows.map(([k, v]) => `<div class="text-slate-500">${k}</div><div class="font-mono text-right">${v}</div>`).join("")}
      </div>
    </div>`;
}

// ---------------------------------------------------------------- tabs
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => {
      b.className = "tab-btn rounded-lg px-4 py-2 font-semibold " +
        (b === btn ? "bg-cyan-500/15 text-cyan-300" : "text-slate-400 hover:text-slate-200");
    });
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    $("tab-" + btn.dataset.tab).classList.remove("hidden");
  });
});

// ---------------------------------------------------------------- status + universe
async function loadStatus() {
  try {
    const h = await api("/health");
    const key = h.api_key_present ? "API key ✓" : "API key ✗";
    $("status-pills").innerHTML =
      `<span class="rounded-full border border-slate-700 bg-slate-900 px-3 py-1">${key}</span>` +
      `<span class="rounded-full border border-slate-700 bg-slate-900 px-3 py-1">Arjum: ${h.arjum_usage.remaining}/${h.arjum_usage.budget}</span>`;
  } catch (e) { /* ignore */ }
}
loadStatus();

const SC_DEFAULTS = {
  universe: "watchlist",
  tickers: "BBRI,BMRI,TINS,BUMI,HRUM,BBCA,ASII,TLKM,ANTM,ADRO",
  brokers: "",
  lookback: 15, topn: 3, liq: 5, rsi: 60, pull: 3, minprice: 100, anchor: 3,
  retail: "YP,CC,NI", season: false, news: false,
};
const BT_DEFAULTS = {
  tickers: "TINS,ANTM", lookback: 15, rsi: 60, tp1: 5, tp2: 10, sl: 5, hold: 15, capital: 100, fee: 0.25,
};

function resetScanner() {
  $("sc-universe").value = SC_DEFAULTS.universe;
  $("sc-tickers").value = SC_DEFAULTS.tickers;
  $("sc-brokers").value = SC_DEFAULTS.brokers;
  $("sc-lookback").value = SC_DEFAULTS.lookback;
  $("sc-topn").value = SC_DEFAULTS.topn;
  $("sc-liq").value = SC_DEFAULTS.liq;
  $("sc-rsi").value = SC_DEFAULTS.rsi;
  $("sc-pull").value = SC_DEFAULTS.pull;
  $("sc-minprice").value = SC_DEFAULTS.minprice;
  $("sc-anchor").value = SC_DEFAULTS.anchor;
  $("sc-retail").value = SC_DEFAULTS.retail;
  $("sc-season").checked = SC_DEFAULTS.season;
  $("sc-news").checked = SC_DEFAULTS.news;
  updateUniverseNote();
}
$("sc-reset").addEventListener("click", resetScanner);

function resetBacktest() {
  Object.entries(BT_DEFAULTS).forEach(([k, v]) => { $("bt-" + k).value = v; });
}
$("bt-reset").addEventListener("click", resetBacktest);

async function loadUniverse() {
  try {
    const u = await api("/api/universe");
    const sel = $("sc-universe");
    sel.innerHTML =
      `<option value="custom">📝 Manual (ketik ticker)</option>` +
      `<option value="watchlist">⭐ Watchlist default</option>` +
      `<option value="all">🌐 Semua Saham (top market cap, ${u.universe_size})</option>` +
      u.groups.map((g) => `<option value="${g.key}">${g.label} (${g.count})</option>`).join("");
    sel.value = "watchlist";
  } catch (e) { /* ignore */ }
  updateUniverseNote();
}
function updateUniverseNote() {
  const v = $("sc-universe").value;
  const el = $("sc-universe-note");
  if (v === "all") el.textContent = "Scan saham paling likuid (cap market cap minimum, dibatasi 300 ticker) — bisa lambat.";
  else if (v === "watchlist") el.textContent = "Daftar default dari env WATCHLIST.";
  else if (v === "custom") el.textContent = "Gunakan isian ticker manual di bawah.";
  else el.textContent = "Hanya saham pada sektor ini yang di-scan.";
}
$("sc-universe").addEventListener("change", updateUniverseNote);
loadUniverse();

// ---------------------------------------------------------------- scanner (streaming)
function scanBody() {
  const universe = $("sc-universe").value;
  const sector = ["custom", "watchlist", "all"].includes(universe) ? null : universe;
  return {
    tickers: universe === "custom"
      ? ($("sc-tickers").value || SC_DEFAULTS.tickers).split(",").map((t) => t.trim().toUpperCase()).filter(Boolean)
      : [],
    brokers: ($("sc-brokers").value || "").split(",").map((b) => b.trim().toUpperCase()).filter(Boolean) || null,
    universe: universe === "custom" ? "watchlist" : universe === "all" ? "all" : "sector",
    sector,
    lookback_days: +$("sc-lookback").value || 15,
    top_n_brokers: +$("sc-topn").value || 3,
    min_liquidity_idr: (+$("sc-liq").value || 5) * 1e9,
    rsi_max: +$("sc-rsi").value || 0,
    pullback_pct: +$("sc-pull").value || 0,
    min_price: +$("sc-minprice").value || 0,
    price_anchor_pct: +$("sc-anchor").value || 3,
    retail_brokers: ($("sc-retail").value || "YP,CC,NI").split(",").map((b) => b.trim().toUpperCase()).filter(Boolean),
    include_seasonality: $("sc-season").checked,
    include_news: $("sc-news").checked,
  };
}

const trendState = { total: 0, done: 0, counts: {}, rsis: [], pulls: [], vals: [], aPass: 0, group: "" };

function updateTrend() {
  const t = trendState;
  if (!t.total) return;
  $("sc-trend").classList.remove("hidden");
  $("sc-trend-title").textContent = `📊 Trend Kelompok — ${t.group || ""}`;
  $("sc-trend-progress").textContent = `${t.done}/${t.total}`;
  $("sc-trend-bar").style.width = (t.done / t.total * 100) + "%";
  const order = ["MAXIMUM_CONVICTION_BUY", "STRONG_BUY", "NEUTRAL_HOLD", "WATCHLIST", "REJECTED"];
  $("sc-trend-chips").innerHTML = order
    .filter((v) => t.counts[v])
    .map((v) => badge(`${v.replace(/_/g, " ")}: ${t.counts[v]}`, VERDICT_STYLE[v]))
    .join("");
  const avg = (arr) => arr.length ? (arr.reduce((a, b) => a + b, 0) / arr.length) : null;
  const stat = (label, val) => `
    <div class="rounded-lg bg-slate-950/70 p-2 text-center">
      <div class="text-[10px] uppercase text-slate-500">${label}</div>
      <div class="mt-0.5 font-mono font-bold">${val}</div>
    </div>`;
  $("sc-trend-stats").innerHTML =
    stat("RSI rata-rata", avg(t.rsis) != null ? avg(t.rsis).toFixed(1) : "—") +
    stat("Pullback rata-rata", avg(t.pulls) != null ? avg(t.pulls).toFixed(1) + "%" : "—") +
    stat("Lulus Layer A", t.aPass) +
    stat("Nilai 20d rata-rata", avg(t.vals) != null ? fmt(avg(t.vals)) : "—");
}

async function runScan() {
  const btn = $("sc-run");
  btn.disabled = true; btn.textContent = "⏳ Scanning…";
  setErr("sc-err", null);
  $("sc-results").innerHTML = "";
  $("sc-summary").innerHTML = "";
  $("sc-empty").classList.add("hidden");
  Object.assign(trendState, { total: 0, done: 0, counts: {}, rsis: [], pulls: [], vals: [], aPass: 0, group: "" });
  $("sc-trend").classList.add("hidden");

  try {
    const res = await fetch("/scan/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scanBody()),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, idx); buf = buf.slice(idx + 1);
        if (line.trim()) handleStreamLine(JSON.parse(line));
      }
    }
  } catch (e) {
    setErr("sc-err", e.message);
  } finally {
    btn.disabled = false; btn.textContent = "▶ Jalankan Scan";
  }
}

function handleStreamLine(line) {
  if (line.type === "meta") {
    trendState.total = line.total;
    trendState.group = line.group;
    updateTrend();
    $("sc-trend-title").textContent = `📊 Trend Kelompok — ${line.group || ""}`;
    return;
  }
  if (line.type === "result") {
    const r = line.result;
    trendState.done++;
    trendState.counts[r.verdict] = (trendState.counts[r.verdict] || 0) + 1;
    const t = r.technicals || {};
    if (t.rsi14 != null) trendState.rsis.push(t.rsi14);
    if (t.pullback_from_20d_high_pct != null) trendState.pulls.push(t.pullback_from_20d_high_pct);
    if (t.avg_20d_value_idr != null) trendState.vals.push(t.avg_20d_value_idr);
    if ((r.layers.a || {}).status === "pass") trendState.aPass++;
    $("sc-results").insertAdjacentHTML("beforeend", verdictCard(r));
    renderFilterChips(trendState.counts);
    applyVerdictFilter();
    updateTrend();
    return;
  }
  if (line.type === "done") {
    const chips = Object.entries(line.summary.by_verdict)
      .map(([v, c]) => badge(`${v.replace(/_/g, " ")}: ${c}`, VERDICT_STYLE[v]))
      .join("");
    const usage = line.arjum_usage
      ? badge(`Arjum: ${line.arjum_usage.calls_used} dipakai · ${line.arjum_usage.remaining} sisa`, "border-slate-700 bg-slate-900 text-slate-400")
      : "";
    $("sc-summary").innerHTML = chips + usage;
    const warn = (line.warnings || []).map((w) =>
      `<div class="w-full rounded-lg bg-amber-500/10 p-2 text-xs text-amber-300">⚠️ ${w}</div>`).join("");
    if (warn) $("sc-summary").insertAdjacentHTML("beforeend", warn);
  }
}

function seasonalityHtml(season) {
  if (!season || !season.months) return "";
  const maxAbs = Math.max(...season.months.map((m) => Math.abs(m.avg_return_pct || 0)), 1);
  const bars = season.months.map((m) => {
    const v = m.avg_return_pct;
    const h = v == null ? 2 : Math.max(4, Math.abs(v) / maxAbs * 56);
    const color = v == null ? "bg-slate-700" : v >= 0 ? "bg-emerald-500" : "bg-rose-500";
    return `
      <div class="flex flex-1 flex-col items-center gap-1" title="${MONTHS[m.month - 1]}: rata-rata ${v != null ? v + "%" : "—"} · win rate ${m.win_rate_pct != null ? m.win_rate_pct + "%" : "—"} · n=${m.n}">
        <div class="flex h-14 items-end">
          <div class="w-4 rounded-sm ${color}" style="height:${h}px"></div>
        </div>
        <span class="text-[9px] text-slate-500">${MONTHS[m.month - 1]}</span>
      </div>`;
  }).join("");
  return `
    <div class="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
      <h4 class="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">
        Musiman (${season.years_analyzed} tahun) — naik di <span class="text-emerald-300">${MONTHS[season.best_month - 1]}</span> (${season.best_avg_pct}%), turun di <span class="text-rose-300">${MONTHS[season.worst_month - 1]}</span> (${season.worst_avg_pct}%)
      </h4>
      <div class="flex gap-1">${bars}</div>
    </div>`;
}

function newsHtml(news, corp) {
  let html = "";
  if (corp && corp.length) {
    html += `<div class="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
      <h4 class="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">📋 Corp Action</h4>
      <div class="space-y-1 text-sm">` +
      corp.map((c) => `<div class="flex justify-between gap-2"><span class="text-slate-400">${c.date}</span>
        <span class="font-mono text-right">${c.dividend ? "Div " + NUM.format(c.dividend) : ""}${c.split ? " Split " + c.split : ""}</span></div>`).join("") +
      `</div></div>`;
  }
  if (news && news.length) {
    html += `<div class="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
      <h4 class="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">📰 Berita Terkini</h4>
      <ul class="space-y-1.5 text-xs">` +
      news.map((n) => `<li><a class="text-cyan-300 hover:underline" href="${n.url || "#"}" target="_blank" rel="noopener">${n.title}</a>
        <span class="ml-1 text-slate-600">${n.publisher} · ${n.date || ""}</span></li>`).join("") +
      `</ul></div>`;
  }
  return html;
}

function explanationHtml(ex) {
  if (!ex || !ex.points) return "";
  const marker = { pass: "✅", fail: "❌", info: "ℹ️" };
  const color = { pass: "text-emerald-300", fail: "text-rose-300", info: "text-slate-300" };
  const points = ex.points.map((p) =>
    `<li class="flex gap-2"><span>${marker[p.kind] || "•"}</span><span class="${color[p.kind] || ""}">${p.text}</span></li>`).join("");
  return `
    <div class="mt-3 rounded-lg border border-slate-700/60 bg-slate-950/80 p-3">
      <h4 class="text-xs font-bold uppercase tracking-wide text-cyan-400">💡 Kenapa ${ex.verdict.replace(/_/g, " ")}?</h4>
      <p class="mt-1 text-sm text-slate-200">${ex.summary}</p>
      <ul class="mt-2 space-y-1.5 text-sm">${points}</ul>
    </div>`;
}

function verdictCard(r) {
  const t = r.technicals || {};
  const bf = r.broker_flow || {};
  const matched = (bf.layer_b && bf.layer_b.details && bf.layer_b.details.matched_brokers) || [];
  const matchedTxt = matched.length
    ? matched.map((m) => `<span class="rounded bg-emerald-500/20 px-1.5 py-0.5 font-bold text-emerald-300">${m.broker_code}</span>`).join(" ")
    : '<span class="text-slate-500">—</span>';
  const plan = r.plan;
  const bStatus = (r.layers.b || {}).status;
  const cStatus = (r.layers.c || {}).status;

  const aRows = [
    ["Close", fmt(t.close)], ["EMA20 / SMA50", `${fmt(t.ema20)} / ${fmt(t.sma50)}`],
    ["Lower BB", fmt(t.lower_band)], ["RSI(14)", t.rsi14],
    ["Nilai 20d", fmt(t.avg_20d_value_idr)], ["Pullback", t.pullback_from_20d_high_pct != null ? t.pullback_from_20d_high_pct + "%" : "—"],
    ["ATR(14)", fmt(t.atr14)],
  ];
  const bDetail = (bf.layer_b && bf.layer_b.details) || {};
  const bRows = [
    ["Top Buyer", ((bf.layer_b && bf.layer_b.details && bf.layer_b.details.top_buyers) || []).slice(0, 3).map((b) => b.broker_code).join(", ") || "—"],
    ["Matched", matchedTxt],
    ["Anchor (VWAP)", fmt(bDetail.buy_avg_anchor)],
    ["Buffer", bDetail.anchor_buffer_pct != null ? bDetail.anchor_buffer_pct + "%" : "—"],
    ["Status B", bStatus],
  ];
  const cRows = [
    ["Top Seller", ((bf.layer_c && bf.layer_c.details && bf.layer_c.details.top_sellers) || []).slice(0, 3).map((b) => b.broker_code).join(", ") || "—"],
    ["Retail share", bf.layer_c && bf.layer_c.details && bf.layer_c.details.retail_share_of_net_sell != null
      ? (bf.layer_c.details.retail_share_of_net_sell * 100).toFixed(1) + "%" : "—"],
    ["Status C", cStatus],
  ];
  const planRows = plan ? [
    ["Entry", `${fmt(plan.entry_zone.from)} – ${fmt(plan.entry_zone.to)}`],
    ["TP1 (+" + plan.tp1_pct + "%)", fmt(plan.tp1_price)],
    ["TP2 (+" + plan.tp2_pct + "%)", fmt(plan.tp2_price)],
    ["SL", fmt(plan.stop_loss)],
    ["Lot", plan.suggested_lots],
  ] : [["—", "Layer A gagal / data kurang"]];

  return `
    <div class="vcard rounded-xl border ${VERDICT_STYLE[r.verdict].split(" ").slice(-1)[0]} bg-slate-900/50 p-4" data-verdict="${r.verdict}">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-3">
          <span class="font-mono text-lg font-bold">${r.ticker}</span>
          ${badge(r.verdict.replace(/_/g, " "), VERDICT_STYLE[r.verdict])}
        </div>
        <div class="text-xs text-slate-500">${(r.reasons || []).join(" · ")}</div>
      </div>
      <div class="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        ${card("Layer A — Teknikal", aRows)}
        ${card("Layer B — Bandarmologi", bRows)}
        ${card("Layer C — Retail", cRows)}
        ${card("Rencana Trading", planRows)}
      </div>
      ${explanationHtml(r.explanation)}
      <div class="mt-3 grid gap-3 lg:grid-cols-2">
        ${seasonalityHtml(r.seasonality)}
        ${newsHtml(r.news, r.corp_actions)}
      </div>
    </div>`;
}

$("sc-run").addEventListener("click", runScan);
document.querySelectorAll(".chip").forEach((c) => {
  c.addEventListener("click", () => { $("sc-brokers").value = c.dataset.broker; });
});
resetScanner();

// ---------------------------------------------------------------- broker
async function runBroker() {
  const code = $("br-ticker").value.trim().toUpperCase() || "BBRI";
  const filter = $("br-filter").value.trim().toUpperCase();
  const topN = +$("br-topn").value || 15;
  const q = new URLSearchParams({ top_n: topN });
  if (filter) q.set("brokers", filter);
  setErr("br-err", null);
  try {
    const d = await api(`/brokers/${code}?${q}`);
    const rows = d.brokers || [];
    const head = ["Broker", "Nama", "Buy (Rp)", "Sell (Rp)", "Net (Rp)", "Net Vol", "Matched?"];
    const trs = rows.map((b) => {
      const net = b.nval || 0;
      const cls = net > 0 ? "text-emerald-300" : net < 0 ? "text-rose-300" : "text-slate-400";
      return `<tr class="border-b border-slate-800 hover:bg-slate-800/40">
        <td class="px-3 py-2 font-mono font-bold">${b.broker_code}</td>
        <td class="px-3 py-2 text-slate-400">${b.broker_name || ""}</td>
        <td class="px-3 py-2 font-mono text-right">${fmt(b.bval)}</td>
        <td class="px-3 py-2 font-mono text-right">${fmt(b.sval)}</td>
        <td class="px-3 py-2 font-mono text-right font-bold ${cls}">${net > 0 ? "+" : ""}${fmt(net)}</td>
        <td class="px-3 py-2 font-mono text-right">${fmt(b.nvol)}</td>
        <td class="px-3 py-2 text-center">${filter && filter.split(",").includes(b.broker_code) ? "✓" : ""}</td>
      </tr>`;
    }).join("");
    $("br-table-wrap").innerHTML = `
      <table class="w-full text-sm">
        <thead><tr class="text-left text-xs uppercase text-slate-500">${head.map((h) => `<th class="px-3 py-2">${h}</th>`).join("")}</tr></thead>
        <tbody>${trs || `<tr><td colspan="7" class="px-3 py-4 text-center text-slate-500">Tidak ada data</td></tr>`}</tbody>
      </table>`;
    $("br-meta").innerHTML =
      `${d.stock_code} · ${d.broker_start || "?"} → ${d.broker_end || "?"} · filter: ${d.filter.brokers ? d.filter.brokers.join(",") : "semua"} · ` +
      (d.matched ? badge("MATCHED", "bg-emerald-500/15 text-emerald-300 border-emerald-500/40") : "") +
      ` · kuota arjum: ${d.arjum_usage ? d.arjum_usage.remaining : "?"}`;
  } catch (e) {
    setErr("br-err", e.message);
    $("br-table-wrap").innerHTML = "";
  }
}
$("br-run").addEventListener("click", runBroker);

// ---------------------------------------------------------------- backtest
async function runBacktest() {
  const body = {
    tickers: ($("bt-tickers").value || "TINS").split(",").map((t) => t.trim().toUpperCase()).filter(Boolean),
    lookback_days: +$("bt-lookback").value || 15,
    rsi_max: +$("bt-rsi").value || 0,
    tp1_pct: +$("bt-tp1").value || 10,
    tp2_pct: +$("bt-tp2").value || 20,
    sl_pct: +$("bt-sl").value || 6,
    max_hold_days: +$("bt-hold").value || 30,
    start_capital: (+$("bt-capital").value || 100) * 1e6,
    fee_pct: +$("bt-fee").value || 0.25,
  };
  const btn = $("bt-run");
  btn.disabled = true; btn.textContent = "⏳ Backtest…";
  setErr("bt-err", null);
  try {
    const d = await api("/backtest", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    $("bt-results").innerHTML = backtestCombinedCard(d.combined) + d.results.map(backtestCard).join("");
  } catch (e) {
    setErr("bt-err", e.message);
  } finally {
    btn.disabled = false; btn.textContent = "📈 Jalankan Backtest";
  }
}

function backtestCombinedCard(c) {
  if (!c || c.n_trades === 0) return `
    <div class="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-300">
      📊 Agregat: 0 sinyal di periode ini — tidak ada data untuk menilai optimalitas strategi.
    </div>`;
  const m = (label, val, good) => `
    <div class="rounded-lg border border-slate-800 bg-slate-950/70 p-3 text-center">
      <div class="text-xs text-slate-500">${label}</div>
      <div class="mt-1 font-mono text-lg font-bold ${good === undefined ? "text-slate-100" : good ? "text-emerald-300" : "text-rose-300"}">${val}</div>
    </div>`;
  return `
    <div class="rounded-xl border border-cyan-500/40 bg-cyan-500/5 p-4">
      <div class="flex items-center justify-between">
        <h3 class="font-bold text-cyan-300">📊 Agregat Semua Ticker</h3>
        <span class="text-xs text-slate-500">${c.note || ""}</span>
      </div>
      <div class="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3">
        ${m("Total Trade", c.n_trades)}
        ${m("Win Rate", c.win_rate_pct + "%", c.win_rate_pct >= 50)}
        ${m("Avg Return/Trade", (c.avg_return_pct >= 0 ? "+" : "") + c.avg_return_pct + "%", c.avg_return_pct > 0)}
        ${m("Profit Factor", c.profit_factor ?? "—", (c.profit_factor ?? 0) >= 1)}
        ${m("Avg Hold", c.avg_hold_days + " hari")}
        ${m("Max DD", "-" + c.max_drawdown_pct + "%", (c.max_drawdown_pct ?? 99) < 15)}
      </div>
    </div>`;
}

function backtestCard(b) {
  if (b.error) return `<div class="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-300">${b.ticker}: ${b.error}</div>`;
  const m = b.metrics || {};
  const metric = (label, val, good) => `
    <div class="rounded-lg border border-slate-800 bg-slate-950/70 p-3 text-center">
      <div class="text-xs text-slate-500">${label}</div>
      <div class="mt-1 font-mono text-lg font-bold ${good === undefined ? "text-slate-100" : good ? "text-emerald-300" : "text-rose-300"}">${val}</div>
    </div>`;
  const trades = (b.trades || []).map((t) => `
    <tr class="border-b border-slate-800">
      <td class="px-3 py-1.5 font-mono">${t.entry_date}</td>
      <td class="px-3 py-1.5 font-mono">${fmt(t.entry_price)}</td>
      <td class="px-3 py-1.5 font-mono">${t.exit_date}</td>
      <td class="px-3 py-1.5 font-mono">${t.exit_price}</td>
      <td class="px-3 py-1.5">${t.reason}</td>
      <td class="px-3 py-1.5 font-mono text-right font-bold ${t.return_pct >= 0 ? "text-emerald-300" : "text-rose-300"}">${t.return_pct >= 0 ? "+" : ""}${t.return_pct}%</td>
      <td class="px-3 py-1.5 font-mono text-right">${t.lots}</td>
    </tr>`).join("");
  return `
    <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div class="flex items-center justify-between">
        <span class="font-mono text-lg font-bold">${b.ticker}</span>
        <span class="text-xs text-slate-500">${b.start_date} → ${b.end_date} · ${b.n_bars} bar</span>
      </div>
      <div class="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
        ${metric("Total Return", (m.total_return_pct >= 0 ? "+" : "") + m.total_return_pct + "%", m.total_return_pct >= 0)}
        ${metric("Trades", m.n_trades)}
        ${metric("Win Rate", (m.win_rate_pct ?? "—") + "%", (m.win_rate_pct ?? 0) >= 50)}
        ${metric("Max DD", "-" + m.max_drawdown_pct + "%", (m.max_drawdown_pct ?? 99) < 15)}
        ${metric("Profit Factor", m.profit_factor ?? "—", (m.profit_factor ?? 0) >= 1)}
        ${metric("Avg Return", (m.avg_return_pct >= 0 ? "+" : "") + m.avg_return_pct + "%", m.avg_return_pct >= 0)}
        ${metric("Avg Hold", (m.avg_hold_days ?? "—") + " hari")}
        ${metric("Final Equity", fmt(m.final_equity), m.final_equity >= m.start_capital)}
      </div>
      <div class="mt-4">${equitySvg(b.equity_curve || [])}</div>
      <details class="mt-3">
        <summary class="cursor-pointer text-xs font-semibold text-slate-400 hover:text-slate-200">Daftar trade (${(b.trades || []).length})</summary>
        <div class="mt-2 max-h-72 overflow-auto">
          <table class="w-full text-xs">
            <thead><tr class="text-left uppercase text-slate-500">
              <th class="px-3 py-1.5">Masuk</th><th class="px-3 py-1.5">Harga</th><th class="px-3 py-1.5">Keluar</th>
              <th class="px-3 py-1.5">Harga</th><th class="px-3 py-1.5">Alasan</th><th class="px-3 py-1.5 text-right">Return</th><th class="px-3 py-1.5 text-right">Lot</th>
            </tr></thead>
            <tbody>${trades || `<tr><td colspan="7" class="px-3 py-3 text-center text-slate-500">Tidak ada sinyal</td></tr>`}</tbody>
          </table>
        </div>
      </details>
    </div>`;
}

function equitySvg(curve) {
  if (!curve || curve.length < 2) return '<p class="text-xs text-slate-500">Data equity tidak cukup.</p>';
  const W = 640, H = 180, P = 8;
  const pts = curve.length > 250 ? curve.filter((_, i) => i % Math.ceil(curve.length / 250) === 0) : curve;
  const vals = pts.map((p) => p[1]);
  const min = Math.min(...vals), max = Math.max(...vals);
  const span = max - min || 1;
  const coords = pts.map((p, i) => {
    const x = P + (i / (pts.length - 1)) * (W - 2 * P);
    const y = H - P - ((p[1] - min) / span) * (H - 2 * P);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const area = `${P},${H - P} ${coords.join(" ")} ${W - P},${H - P}`;
  return `
    <svg viewBox="0 0 ${W} ${H}" class="w-full rounded-lg border border-slate-800 bg-slate-950">
      <polygon points="${area}" fill="rgba(34,211,238,0.08)" />
      <polyline points="${coords.join(" ")}" fill="none" stroke="#22d3ee" stroke-width="1.8" />
      <text x="${P}" y="${H - P - 4}" class="fill-slate-500" font-size="10">${fmt(min)}</text>
      <text x="${W - 60}" y="${P + 10}" class="fill-slate-500" font-size="10">${fmt(max)}</text>
    </svg>`;
}
$("bt-run").addEventListener("click", runBacktest);

// ---------------------------------------------------------------- alerts
async function runAlerts() {
  const btn = $("al-run");
  btn.disabled = true; btn.textContent = "⏳ Menjalankan…";
  setErr("al-err", null);
  $("al-status").innerHTML = "";
  try {
    const d = await api("/api/alerts/run", { method: "POST" });
    $("al-status").innerHTML = `
      <div class="text-sm">Summary: <span class="font-mono">${JSON.stringify(d.summary.by_verdict)}</span></div>
      <div class="text-sm">Telegram: <span class="font-mono">${d.sent.telegram}</span></div>
      <div class="text-sm">Webhook: <span class="font-mono">${d.sent.webhook}</span></div>
      <div class="text-xs text-slate-500">Kuota arjum: ${d.arjum_usage.remaining}/${d.arjum_usage.budget}</div>`;
    $("al-preview").textContent = d.alert_preview || "";
  } catch (e) {
    setErr("al-err", e.message);
  } finally {
    btn.disabled = false; btn.textContent = "▶ Jalankan Alert Sekarang";
  }
}
$("al-run").addEventListener("click", runAlerts);