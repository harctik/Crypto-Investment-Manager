"use strict";

window.onerror = (msg, src, line) => {
  console.error(`JS ERROR at line ${line}: ${msg}`);
};
window.onunhandledrejection = (e) => {
  console.error("Unhandled promise rejection:", e.reason);
};

const savedTheme = localStorage.getItem("cm-theme") || document.body?.dataset.theme || "dark";
if (document.body) document.body.dataset.theme = savedTheme;

function applyTheme(theme) {
  document.body.dataset.theme = theme;
  localStorage.setItem("cm-theme", theme);
  const btn = document.getElementById("themeToggle");
  if (btn) btn.title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
  fetch("/api/theme", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({theme})
  }).catch(() => {});
}

document.getElementById("themeToggle")?.addEventListener("click", () => {
  applyTheme(document.body.dataset.theme === "dark" ? "light" : "dark");
});

let socket;
try {
  socket = io({ transports: ["polling", "websocket"], reconnectionAttempts: 5 });
  socket.on("connect", () => {
    const lbl = document.getElementById("liveLabel");
    const dot = document.querySelector(".live-dot");
    if (lbl) lbl.textContent = "Live feed active";
    if (dot) dot.style.background = "var(--green)";
  });
  socket.on("disconnect", () => {
    const lbl = document.getElementById("liveLabel");
    const dot = document.querySelector(".live-dot");
    if (lbl) lbl.textContent = "Reconnecting…";
    if (dot) dot.style.background = "var(--amber)";
  });
  socket.on("connect_error", () => {
    const lbl = document.getElementById("liveLabel");
    const dot = document.querySelector(".live-dot");
    if (lbl) lbl.textContent = "Live feed offline";
    if (dot) dot.style.background = "var(--amber)";
  });
  socket.on("price_update",      (coins) => { applyTickerData(coins); countdown = 60; });
  socket.on("alert_update",      (alts)  => { renderAlerts(alts); });
  socket.on("price_alert_fired", (fired) => {
    fired.forEach(a => {
      toast(`${a.symbol} hit $${(+a.target).toLocaleString("en",{maximumFractionDigits:4})} — ${a.condition} alert triggered!`, "warning");
    });
    loadPriceAlerts();
  });
} catch(e) {
  console.warn("SocketIO unavailable:", e);
}

let priceChart = null;
let _chartCoinId = "";
const CHART_COLORS = {
  bitcoin: "#f59e0b", ethereum: "#8b5cf6", solana: "#06b6d4",
  binancecoin: "#f59e0b", cardano: "#10b981", ripple: "#3b82f6",
  "matic-network": "#8b5cf6", chainlink: "#2563eb",
  dogecoin: "#dba53a", harvestai: "#10b981", "usd-coin": "#2775ca",
};

/* ── Crosshair plugin ─────────────────────────────────────────────────── */
const crosshairPlugin = {
  id: "crosshair",
  afterDraw(chart) {
    if (chart.tooltip?._active?.length) {
      const ctx = chart.ctx;
      const pt = chart.tooltip._active[0].element;
      const area = chart.chartArea;
      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(255,255,255,0.15)";
      // vertical line
      ctx.beginPath();
      ctx.moveTo(pt.x, area.top);
      ctx.lineTo(pt.x, area.bottom);
      ctx.stroke();
      // horizontal line
      ctx.beginPath();
      ctx.moveTo(area.left, pt.y);
      ctx.lineTo(area.right, pt.y);
      ctx.stroke();
      ctx.restore();
    }
  }
};

/* ── Smart label formatter ─────────────────────────────────────────── */
function formatChartLabel(dateStr, rangeMinutes) {
  const d = new Date(dateStr.replace(" ", "T") + "Z");
  if (isNaN(d)) return dateStr.slice(11, 16);
  if (rangeMinutes <= 60)    return d.toLocaleTimeString("en", {hour:"2-digit", minute:"2-digit", hour12:false});
  if (rangeMinutes <= 1440)  return d.toLocaleTimeString("en", {hour:"2-digit", minute:"2-digit", hour12:false});
  if (rangeMinutes <= 10080) return d.toLocaleDateString("en", {month:"short", day:"numeric"}) + " " +
                                    d.toLocaleTimeString("en", {hour:"2-digit", minute:"2-digit", hour12:false});
  return d.toLocaleDateString("en", {month:"short", day:"numeric"});
}

/* ── Chart options factory ──────────────────────────────────────────── */
const _chartOptions = (color, rangeMinutes) => ({
  responsive: true, maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    crosshair: {},
    tooltip: {
      backgroundColor: "rgba(10,14,23,0.95)", borderColor: color + "66", borderWidth: 1,
      titleColor: "#f9fafb", bodyColor: "#e5e7eb",
      titleFont: { family: "DM Mono", size: 12, weight: "600" },
      bodyFont:  { family: "DM Mono", size: 12 },
      padding: 12, displayColors: false, cornerRadius: 8,
      callbacks: {
        title: (items) => {
          if (!items.length) return "";
          const raw = items[0].label;
          return raw;
        },
        label: c => `Price: $${c.parsed.y.toLocaleString("en", {maximumFractionDigits: 4})}`,
        afterLabel: (c) => {
          const ds = c.dataset.data;
          const idx = c.dataIndex;
          if (idx > 0) {
            const prev = ds[idx - 1];
            const curr = ds[idx];
            const chg = ((curr - prev) / prev * 100).toFixed(3);
            return `Change: ${chg >= 0 ? "+" : ""}${chg}%`;
          }
          return "";
        }
      }
    }
  },
  scales: {
    x: {
      grid: { color: "rgba(255,255,255,0.03)", drawBorder: false },
      ticks: {
        color: "#6b7280", font: { family: "DM Mono", size: 10 },
        maxTicksLimit: 8, maxRotation: 0, autoSkip: true,
      },
      border: { display: false }
    },
    y: {
      position: "right",
      grid: { color: "rgba(255,255,255,0.03)", drawBorder: false },
      ticks: {
        color: "#6b7280", font: { family: "DM Mono", size: 10 },
        callback: v => `$${v >= 1000 ? (v/1000).toFixed(1)+"k" : v.toFixed(v >= 100 ? 0 : v >= 1 ? 2 : 4)}`,
        maxTicksLimit: 6,
      },
      border: { display: false }
    }
  },
  interaction: { intersect: false, mode: "index" },
  animation: { duration: 500, easing: "easeOutQuart" },
  elements: { point: { hoverRadius: 5, hoverBorderWidth: 2 } }
});

/* ── Build chart ────────────────────────────────────────────────────── */
function buildChart(labels, values, coinId, rangeMinutes) {
  const ctx = document.getElementById("priceChart");
  if (!ctx) return;
  const color = CHART_COLORS[coinId] || "#06b6d4";

  // Update stats bar
  updateChartStats(values, color);

  if (priceChart && _chartCoinId === coinId) {
    priceChart.data.labels = labels;
    priceChart.data.datasets[0].data = values;
    priceChart.options = _chartOptions(color, rangeMinutes);
    priceChart.update("none");
    return;
  }

  if (priceChart) { priceChart.destroy(); priceChart = null; }
  _chartCoinId = coinId;
  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: coinId.toUpperCase(), data: values,
        borderColor: color, borderWidth: 2,
        pointRadius: values.length > 100 ? 0 : 1,
        pointHoverRadius: 5, pointHoverBackgroundColor: color,
        pointHoverBorderColor: "#fff", pointHoverBorderWidth: 2,
        fill: true,
        backgroundColor: (ctx2) => {
          const g = ctx2.chart.ctx.createLinearGradient(0, 0, 0, ctx2.chart.height);
          g.addColorStop(0, color + "25");
          g.addColorStop(0.5, color + "08");
          g.addColorStop(1, color + "00");
          return g;
        },
        tension: 0.35,
      }]
    },
    options: _chartOptions(color, rangeMinutes),
    plugins: [crosshairPlugin]
  });
}

/* ── Chart stats bar ────────────────────────────────────────────────── */
function updateChartStats(values, color) {
  let bar = document.getElementById("chartStatsBar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "chartStatsBar";
    bar.className = "chart-stats-bar";
    const wrap = document.querySelector(".chart-wrap");
    if (wrap) wrap.parentElement.insertBefore(bar, wrap);
  }
  if (!values.length) { bar.innerHTML = ""; return; }
  // Safe high/low/sum for large arrays (spread would blow stack at 10k+)
  let high = -Infinity, low = Infinity, sum = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v > high) high = v;
    if (v < low) low = v;
    sum += v;
  }
  const curr = values[values.length - 1];
  const first = values[0];
  const chg  = ((curr - first) / first * 100);
  const avg  = sum / values.length;
  const fmt  = v => v >= 1000 ? `$${(v/1000).toFixed(2)}k` : `$${v.toFixed(v >= 1 ? 2 : 4)}`;

  bar.innerHTML = `
    <span class="cs-item"><span class="cs-label">High</span><span class="cs-val" style="color:var(--green)">${fmt(high)}</span></span>
    <span class="cs-divider"></span>
    <span class="cs-item"><span class="cs-label">Low</span><span class="cs-val" style="color:var(--red)">${fmt(low)}</span></span>
    <span class="cs-divider"></span>
    <span class="cs-item"><span class="cs-label">Avg</span><span class="cs-val">${fmt(avg)}</span></span>
    <span class="cs-divider"></span>
    <span class="cs-item"><span class="cs-label">Change</span><span class="cs-val" style="color:${chg >= 0 ? "var(--green)" : "var(--red)"}">${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%</span></span>
    <span class="cs-divider"></span>
    <span class="cs-item"><span class="cs-label">Points</span><span class="cs-val">${values.length}</span></span>
  `;
}

/* ── Time range definitions ─────────────────────────────────────────── */
const TIME_RANGES = [
  { label: "ALL", mins: 0 },
  { label: "1H",  mins: 60 },
  { label: "6H",  mins: 360 },
  { label: "12H", mins: 720 },
  { label: "24H", mins: 1440 },
  { label: "7D",  mins: 10080 },
  { label: "30D", mins: 43200 },
  { label: "90D", mins: 129600 },
];

/* ── Dynamic time tab rendering ─────────────────────────────────────── */
function renderTimeTabs(rows) {
  const container = document.getElementById("timeTabs");
  if (!container) return;
  if (!rows.length) return;

  const oldest = new Date(rows[0].fetched_at.replace(" ", "T") + "Z");
  const newest = new Date(rows[rows.length - 1].fetched_at.replace(" ", "T") + "Z");
  const dataSpanMins = (newest - oldest) / 60000;

  container.innerHTML = "";
  TIME_RANGES.forEach(tr => {
    // Show ALL always; others only if data covers >= 50% of the range
    if (tr.mins > 0 && dataSpanMins < tr.mins * 0.3) return;
    const btn = document.createElement("button");
    btn.className = "time-tab" + (tr.mins === _currentMins ? " active" : "");
    btn.dataset.mins = tr.mins;
    btn.textContent = tr.label;
    btn.addEventListener("click", () => {
      _compareRows = [];
      const cmpSel = document.getElementById("compareCoin");
      if (cmpSel) cmpSel.value = "";
      loadChart(undefined, tr.mins);
    });
    container.appendChild(btn);
  });
}

let _currentCoin  = "";
let _currentMins  = 0;
let _allRows      = [];

async function loadChart(coinId, mins) {
  if (coinId !== undefined) _currentCoin = coinId;
  if (mins   !== undefined) _currentMins = mins;

  document.querySelectorAll(".coin-tab").forEach(t =>
    t.classList.toggle("active", t.dataset.coin === _currentCoin));
  document.querySelectorAll(".time-tab").forEach(t =>
    t.classList.toggle("active", +t.dataset.mins === _currentMins));

  try {
    if (!_allRows.length || coinId !== undefined) {
      _allRows = await (await fetch(`/api/history/${_currentCoin}`)).json();
      renderTimeTabs(_allRows);
    }
    let rows = _allRows;
    if (_currentMins > 0 && rows.length) {
      const cutoff = new Date(Date.now() - _currentMins * 60 * 1000);
      const filtered = rows.filter(r => new Date(r.fetched_at.replace(" ", "T") + "Z") >= cutoff);
      if (filtered.length >= 2) {
        rows = filtered;
        document.getElementById("noDataMsg")?.remove();
      } else {
        // Not enough data for this range — show a brief message
        let noDataEl = document.getElementById("noDataMsg");
        if (!noDataEl) {
          const wrap = document.querySelector(".chart-wrap");
          const msg  = document.createElement("div");
          msg.id = "noDataMsg";
          msg.className = "chart-no-data";
          msg.textContent = `Not enough data for this range — showing all available`;
          if (wrap) wrap.after(msg);
        }
      }
    } else {
      document.getElementById("noDataMsg")?.remove();
    }

    if (!rows.length) { buildChart([], [], _currentCoin, _currentMins); return; }

    // Smart labels based on range
    const effectiveMins = _currentMins || Infinity;
    const labels = rows.map(r => formatChartLabel(r.fetched_at, effectiveMins));
    const values = rows.map(r => r.price_usd);
    buildChart(labels, values, _currentCoin, _currentMins);
  } catch (e) { console.error("Chart load error:", e); }
}

function applyTickerData(coins) {
  coins.forEach(c => {
    const el = document.getElementById(`dt-${c.id}`);
    if (!el) return;
    const chg = c.price_change_percentage_24h || 0;
    el.querySelector(".dt-price").textContent =
      `$${c.current_price.toLocaleString("en", {maximumFractionDigits: 4})}`;
    const chgEl = el.querySelector(".dt-chg");
    chgEl.textContent = `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%`;
    chgEl.className = "dt-chg " + (chg >= 0 ? "up" : "down");
  });
  document.getElementById("lastUpdated").textContent =
    "Updated " + new Date().toLocaleTimeString("en", {hour:"2-digit", minute:"2-digit"});
}

async function refreshTicker() {
  try {
    const coins = await (await fetch("/api/prices")).json();
    applyTickerData(coins);
    return coins;
  } catch(_) { return []; }
}

let _overviewLoading = false;
async function loadOverview() {
  if (_overviewLoading) return; // prevent overlapping calls
  _overviewLoading = true;
  try {
    const [portRes, alertRes, priceRes] = await Promise.all([
      fetch("/api/portfolio"), fetch("/api/alerts"), fetch("/api/prices")
    ]);
    const port  = await portRes.json();
    const alts  = await alertRes.json();
    const coins = await priceRes.json();

    animateNumber("mv-total", port.total || 0,
      v => "$" + v.toLocaleString("en", {maximumFractionDigits: 2}));

    if (coins.length) {
      const best = coins.reduce((a, b) =>
        (b.price_change_percentage_24h > a.price_change_percentage_24h) ? b : a);
      document.getElementById("mv-best").textContent = best.symbol;
      const bdEl = document.getElementById("md-best");
      bdEl.textContent =
        `${best.price_change_percentage_24h >= 0 ? "+" : ""}${best.price_change_percentage_24h.toFixed(2)}% today`;
      bdEl.className = "mc-delta " + (best.price_change_percentage_24h >= 0 ? "up" : "down");
      applyTickerData(coins);
    }

    document.getElementById("mv-alerts").textContent = alts.length;
    document.getElementById("mv-alerts").style.color =
      alts.length > 0 ? "var(--red)" : "var(--green)";
    renderAlerts(alts);
    document.getElementById("alertCount").textContent = alts.length;

  } catch (e) { console.error("loadOverview:", e); }
  _overviewLoading = false;
}

function renderAlerts(alts) {
  const list = document.getElementById("alertsList");
  if (!list) return;
  if (!alts.length) {
    list.innerHTML = '<div class="empty-state">No price movements detected yet</div>';
    return;
  }
  list.innerHTML = alts.map(a => {
    const up  = a.direction && a.direction.includes("UP");
    const dir = up ? "up" : "down";
    const chg = a.change_24h != null ? `${a.change_24h >= 0 ? "+" : ""}${(+a.change_24h).toFixed(2)}%` : "";
    // Extract coin name from message (e.g. "Bitcoin moved..." → "Bitcoin")
    const coinName = (a.message || "").split(" ")[0];
    const sym = coinName.substring(0, 3).toUpperCase();
    return `<div class="alert-item ${dir}">
      <div class="alert-dot ${dir}"></div>
      <div style="flex:1;min-width:0;">
        <div class="alert-msg">${a.message}</div>
        <div class="alert-time">
          <span>Just now</span>
          ${chg ? `<span class="alert-change" style="color:${up ? "var(--green)" : "var(--red)"}; margin-left:8px;">${chg}</span>` : ""}
        </div>
      </div>
    </div>`;
  }).join("");
}

let _portfolioLoading = false;
async function loadPortfolio() {
  if (_portfolioLoading) return;
  _portfolioLoading = true;
  try {
    const [portData, notesData] = await Promise.all([
      fetch("/api/portfolio").then(r => r.json()),
      fetch("/api/notes").then(r => r.json()),
    ]);
    const body      = document.getElementById("portfolioBody");
    const positions = portData.positions || [];

    if (!positions.length) {
      body.innerHTML = '<tr><td colspan="11" class="table-empty">No positions yet. Click "Add Position" to get started.</td></tr>';
      ["ps-total","ps-cost","ps-pnl","ps-pnlpct"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = "$0";
      });
      return;
    }

    const totalVal  = positions.reduce((s,p) => s + (p.value  || 0), 0);
    const totalCost = positions.reduce((s,p) => s + ((+p.amount * +p.avg_buy) || 0), 0);
    const totalPnl  = totalVal - totalCost;
    const totalPct  = totalCost ? totalPnl / totalCost * 100 : 0;

    const setEl = (id, text, color) => { const e = document.getElementById(id); if(e){e.textContent=text; if(color) e.style.color=color;} };
    setEl("ps-total",  "$"+totalVal.toLocaleString("en",{maximumFractionDigits:2}));
    setEl("ps-cost",   "$"+totalCost.toLocaleString("en",{maximumFractionDigits:2}));
    setEl("ps-pnl",    `${totalPnl>=0?"+":""}$${Math.abs(totalPnl).toLocaleString("en",{maximumFractionDigits:2})}`,
          totalPnl >= 0 ? "var(--green)" : "var(--red)");
    setEl("ps-pnlpct", `${totalPct>=0?"+":""}${totalPct.toFixed(2)}%`,
          totalPct >= 0 ? "var(--green)" : "var(--red)");

    body.innerHTML = positions.map(p => {
      const note   = (notesData[p.coin_id] || {}).note || "";
      const cost   = (+p.amount) * (+p.avg_buy);
      const pnl    = p.pnl    || 0;
      const pnlPct = p.pnl_pct || 0;
      return `<tr>
        <td class="name-cell">
          <span style="font-weight:600;">${p.symbol}</span>
          <span style="color:var(--text2);font-size:11px;display:block;">${p.coin_id}</span>
        </td>
        <td style="font-family:var(--font-mono,monospace);font-size:12px;">${(+p.amount).toLocaleString("en",{maximumFractionDigits:8})}</td>
        <td>$${(+p.avg_buy).toLocaleString("en",{maximumFractionDigits:4})}</td>
        <td>$${(+p.price).toLocaleString("en",{maximumFractionDigits:4})}</td>
        <td style="font-weight:500;">$${(+(p.value||0)).toLocaleString("en",{maximumFractionDigits:2})}</td>
        <td style="color:var(--text2);">$${cost.toLocaleString("en",{maximumFractionDigits:2})}</td>
        <td class="${pnl>=0?'up':'down'}" style="font-weight:500;">${pnl>=0?"+":""}$${Math.abs(pnl).toLocaleString("en",{maximumFractionDigits:2})}</td>
        <td class="${pnlPct>=0?'up':'down'}">${pnlPct>=0?"+":""}${pnlPct.toFixed(2)}%</td>
        <td>
          <div style="display:flex;align-items:center;gap:6px;">
            <div style="flex:1;height:4px;background:var(--bg4);border-radius:4px;overflow:hidden;min-width:60px;">
              <div style="height:100%;width:${Math.min(p.alloc_pct||0,100)}%;background:var(--cyan);border-radius:4px;transition:width .4s;"></div>
            </div>
            <span style="font-size:11px;color:var(--text1);min-width:40px;">${(p.alloc_pct||0).toFixed(1)}%</span>
          </div>
        </td>
        <td><input class="note-input" data-coin="${p.coin_id}" value="${note.replace(/"/g,'&quot;')}"
          placeholder="Add note…" onblur="saveNote('${p.coin_id}', this.value)"></td>
        <td>
          <button class="pos-delete-btn" onclick="deletePosition('${p.coin_id}','${p.symbol}')" title="Remove position">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
            </svg>
          </button>
        </td>
      </tr>`;
    }).join("");

    document.getElementById("portfolioTotal").innerHTML =
      `Total Value: <strong style="color:var(--text0);">$${totalVal.toLocaleString("en",{maximumFractionDigits:2})}</strong>
       &nbsp;·&nbsp; Cost Basis: <strong style="color:var(--text2);">$${totalCost.toLocaleString("en",{maximumFractionDigits:2})}</strong>
       &nbsp;·&nbsp; P&L: <strong style="color:${totalPnl>=0?'var(--green)':'var(--red)'};">
       ${totalPnl>=0?"+":""}$${Math.abs(totalPnl).toLocaleString("en",{maximumFractionDigits:2})}
       (${totalPct>=0?"+":""}${totalPct.toFixed(2)}%)</strong>`;

  } catch(e) { console.error("loadPortfolio:", e); }
  _portfolioLoading = false;
}

async function deletePosition(coinId, symbol) {
  if (!confirm(`Remove ${symbol} from your portfolio?`)) return;
  try {
    await fetch(`/api/position/${coinId}`, {method: "DELETE"});
    toast(`${symbol} removed`, "info");
    loadPortfolio();
    loadDonut();
  } catch(_) { toast("Failed to remove position", "error"); }
}

async function saveNote(coinId, note) {
  try {
    await fetch(`/api/notes/${coinId}`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({note})
    });
  } catch(_) {}
}

async function loadPredictions() {
  try {
    const data = await (await fetch("/api/predictions")).json();
    const grid = document.getElementById("predGrid");
    if (!data.length) {
      grid.innerHTML = '<div class="empty-state">Not enough price history. Click Refresh first.</div>';
      return;
    }
    grid.innerHTML = data.map(p => {
      // Use .includes() — API returns "BUY  🟢", "SELL 🔴", "HOLD 🟡"
      const rawSig = (p.signal || "").toUpperCase();
      const sig = rawSig.includes("BUY") ? "buy" : rawSig.includes("SELL") ? "sell" : "hold";
      const rawTrn = (p.trend || "").toUpperCase();
      const trn = rawTrn.includes("BULL") ? "bullish" : rawTrn.includes("BEAR") ? "bearish" : "neutral";
      const sigLabel = sig === "buy" ? "BUY 🟢" : sig === "sell" ? "SELL 🔴" : "HOLD 🟡";

      const fcast = (p.linreg_forecast || []).slice(0, 3)
        .map(v => `$${(+v).toLocaleString("en", {maximumFractionDigits: 2})}`).join(" → ");

      // RSI signal display
      const rsi = p.rsi;
      let rsiClass = "neutral", rsiLabel = "—";
      if (rsi != null) {
        if (rsi < 30)      { rsiClass = "buy";  rsiLabel = `${rsi.toFixed(1)} (Oversold 🟢)`; }
        else if (rsi > 70) { rsiClass = "sell"; rsiLabel = `${rsi.toFixed(1)} (Overbought 🔴)`; }
        else               { rsiClass = "hold"; rsiLabel = `${rsi.toFixed(1)} (Neutral)`; }
      }

      // Trend display with proper icon
      const trendIcon = trn === "bullish" ? "BULLISH ↑" : trn === "bearish" ? "BEARISH ↓" : "NEUTRAL ➡";

      // ML method badge
      const method = p.method || "LinReg";
      const methodBadge = method.includes("Ridge") 
        ? '<span style="background:var(--purple-bg,#7c3aed22);color:var(--purple,#a78bfa);padding:2px 8px;border-radius:6px;font-size:10px;font-weight:600;">ML Ridge</span>'
        : '<span style="background:var(--bg3);color:var(--text2);padding:2px 8px;border-radius:6px;font-size:10px;">LinReg</span>';

      return `<div class="pred-card ${sig}">
        <div class="pred-header">
          <div>
            <div class="pred-coin">${p.coin_id}</div>
            <div class="pred-price">$${(+p.current_price).toLocaleString("en", {maximumFractionDigits: 4})}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;">
            <span class="signal-badge ${sig}">${sigLabel}</span>
            ${methodBadge}
          </div>
        </div>

        ${p.ml_prediction ? `<div class="pred-row" style="background:var(--purple-bg,rgba(124,58,237,0.08));border-radius:8px;padding:6px 10px;margin:6px 0;">
          <span style="font-weight:600;">${tip("ML Prediction", "scikit-learn Ridge regression with 14 features: returns, volatility, RSI, MACD, Bollinger bands, momentum. More accurate than simple LinReg.")}</span>
          <span style="font-weight:700;color:var(--text0);">$${(+p.ml_prediction).toLocaleString("en", {maximumFractionDigits: 4})}</span>
        </div>` : ""}

        <div class="pred-row"><span>${tip("LinReg Next", "Linear Regression prediction — fits a straight line through recent prices and projects where the next price should land.")}</span>
          <span>$${(+p.linreg_next).toLocaleString("en", {maximumFractionDigits: 4})}</span></div>
        <div class="pred-row"><span>${tip("Confidence", "±1 standard deviation of prediction error. Smaller = more reliable forecast.")}</span>
          <span>${p.confidence_band}</span></div>
        <div class="pred-row"><span>${tip("MA Next", "Moving Average prediction — average of the last 5 prices.")}</span>
          <span>${p.ma_next_pred ? "$"+p.ma_next_pred.toLocaleString("en",{maximumFractionDigits:4}) : "—"}</span></div>

        ${rsi != null ? `<div class="pred-row"><span>${tip("RSI (14)", "Relative Strength Index — momentum oscillator. Below 30 = oversold (buy signal), above 70 = overbought (sell signal).")}</span>
          <span class="${rsiClass}" style="font-weight:500;">${rsiLabel}</span></div>` : ""}

        ${p.macd != null ? `<div class="pred-row"><span>${tip("MACD", "Moving Average Convergence Divergence — positive histogram = bullish momentum, negative = bearish.")}</span>
          <span style="color:${(p.macd_histogram||0) >= 0 ? 'var(--green)' : 'var(--red)'};">${(+p.macd).toFixed(4)} (hist: ${((p.macd_histogram||0) >= 0 ? "+" : "") + (+p.macd_histogram||0).toFixed(4)})</span></div>` : ""}

        ${p.bb_upper != null && p.bb_lower != null ? `<div class="pred-row"><span>${tip("Bollinger", "Bollinger Bands — price near lower band = potential buy, near upper band = potential sell. Width shows volatility.")}</span>
          <span style="font-size:11px;">$${(+p.bb_lower).toLocaleString("en",{maximumFractionDigits:0})} — $${(+p.bb_upper).toLocaleString("en",{maximumFractionDigits:0})}</span></div>` : ""}

        <div class="pred-row"><span>${tip("Slope/snap", "How fast the LinReg line is rising or falling per snapshot.")}</span>
          <span>${(p.slope_pct_per_snap||0) >= 0 ? "+" : ""}${(p.slope_pct_per_snap||0).toFixed(4)}%</span></div>
        ${fcast ? `<div class="pred-row"><span>${tip("Forecast", "LinReg price projections for the next 5 snapshots.")}</span>
          <span style="font-size:10px;">${fcast}</span></div>` : ""}
        <div class="pred-trend ${trn}" style="margin-top:10px;">${trendIcon}</div>
      </div>`;
    }).join("");
  } catch (e) { console.error("loadPredictions:", e); }
}

function tip(label, explanation) {
  return `<span class="tip">
    ${label}
    <span class="tip-icon" tabindex="0">?</span>
    <span class="tip-box"><span class="tip-label">${label}</span>${explanation}</span>
  </span>`;
}

async function loadRisk() {
  try {
    const data = await (await fetch("/api/risk")).json();
    const grid = document.getElementById("riskGrid");
    if (!data.length) {
      grid.innerHTML = '<div class="empty-state">No risk data. Fetch prices first.</div>';
      return;
    }
    grid.innerHTML = data.map(r => {
      const tier   = (r.risk_tier || "medium").toLowerCase();
      const volPct = Math.min((r["volatility_%"] || 0) / 15 * 100, 100);

      // VaR display
      const varPct  = r["var_%"] != null ? r["var_%"] : null;
      const cvarPct = r["cvar_%"] != null ? r["cvar_%"] : null;
      const sortino = r.sortino != null ? r.sortino : null;
      const calmar  = r.calmar != null ? r.calmar : null;

      return `<div class="risk-card">
        <div class="risk-header">
          <div class="risk-coin">${r.coin_id}</div>
          <span class="tier-badge ${tier}">${r.risk_tier}</span>
        </div>
        <div class="risk-bar-wrap">
          <div class="risk-bar-label">
            <span>${tip("Volatility", "How much the price swings. Under 3% = Low, 3\u20138% = Medium, above 8% = High.")}</span>
            <span>${(r["volatility_%"]||0).toFixed(2)}%</span>
          </div>
          <div class="risk-bar">
            <div class="risk-fill ${tier}" style="width:${volPct}%"></div>
          </div>
        </div>
        <div class="risk-stats">
          <div class="risk-stat">
            <div class="risk-stat-lbl">${tip("Sharpe", "Return earned per unit of risk (includes risk-free rate). Higher is better.")}</div>
            <div class="risk-stat-val">${(r.sharpe||0) >= 0 ? "+" : ""}${(r.sharpe||0).toFixed(3)}</div>
          </div>
          <div class="risk-stat">
            <div class="risk-stat-lbl">${tip("Max DD", "Max Drawdown \u2014 biggest peak-to-trough drop. Shows worst-case loss.")}</div>
            <div class="risk-stat-val">${(r["max_dd_%"]||0).toFixed(2)}%</div>
          </div>
          <div class="risk-stat">
            <div class="risk-stat-lbl">${tip("Mean Ret", "Average return per snapshot. Negative = downtrend.")}</div>
            <div class="risk-stat-val">${(r["mean_ret_%"]||0) >= 0 ? "+" : ""}${(r["mean_ret_%"]||0).toFixed(3)}%</div>
          </div>
          <div class="risk-stat">
            <div class="risk-stat-lbl">${tip("Price", "Latest live price fetched from CoinGecko.")}</div>
            <div class="risk-stat-val">$${(+r.price||0).toLocaleString("en",{maximumFractionDigits:2})}</div>
          </div>
        </div>
        ${varPct != null || sortino != null ? `
        <div style="border-top:1px solid var(--border);margin-top:12px;padding-top:10px;">
          <div style="font-size:11px;color:var(--text2);margin-bottom:6px;font-weight:600;">Advanced Risk Metrics</div>
          <div class="risk-stats">
            ${varPct != null ? `<div class="risk-stat">
              <div class="risk-stat-lbl">${tip("VaR 95%", "Value-at-Risk \u2014 95% chance daily loss won't exceed this percentage. Based on historical returns.")}</div>
              <div class="risk-stat-val" style="color:var(--red);">${varPct.toFixed(2)}%</div>
            </div>` : ""}
            ${cvarPct != null ? `<div class="risk-stat">
              <div class="risk-stat-lbl">${tip("CVaR 95%", "Conditional VaR (Expected Shortfall) \u2014 average loss in the worst 5% of scenarios. More conservative than VaR.")}</div>
              <div class="risk-stat-val" style="color:var(--red);">${cvarPct.toFixed(2)}%</div>
            </div>` : ""}
            ${sortino != null ? `<div class="risk-stat">
              <div class="risk-stat-lbl">${tip("Sortino", "Like Sharpe but only penalises downside volatility. Higher = better risk-adjusted return.")}</div>
              <div class="risk-stat-val" style="color:${sortino >= 0 ? 'var(--green)' : 'var(--red)'};">${sortino >= 999 ? '\u221e' : (sortino >= 0 ? '+' : '') + sortino.toFixed(3)}</div>
            </div>` : ""}
            ${calmar != null ? `<div class="risk-stat">
              <div class="risk-stat-lbl">${tip("Calmar", "Return / Max Drawdown. Higher means the return justifies the risk of large drops.")}</div>
              <div class="risk-stat-val" style="color:${calmar >= 0 ? 'var(--green)' : 'var(--red)'};">${calmar >= 999 ? '\u221e' : (calmar >= 0 ? '+' : '') + calmar.toFixed(3)}</div>
            </div>` : ""}
          </div>
        </div>` : ""}
      </div>`;
    }).join("");
  } catch (e) { console.error("loadRisk:", e); }
}

async function loadMixes() {
  try {
    const data = await (await fetch("/api/mixes")).json();
    const grid = document.getElementById("mixesGrid");
    if (!data.length) {
      grid.innerHTML = '<div class="empty-state">No mixes yet. Click Re-run Calculator.</div>';
      return;
    }
    const classes = ["sharpe", "return", "risk"];
    grid.innerHTML = data.map((mx, i) => {
      const coins   = mx.coin_ids.split(",");
      const weights = mx.weights.split(",").map(Number);
      const bars    = coins.map((c, j) => `
        <div class="mix-alloc-row">
          <div class="mix-coin-name">${c}</div>
          <div class="mix-bar">
            <div class="mix-fill" style="width:${(weights[j]*100).toFixed(1)}%"></div>
          </div>
          <div class="mix-pct">${(weights[j]*100).toFixed(1)}%</div>
        </div>`).join("");
      return `<div class="mix-card ${classes[i] || "sharpe"}">
        <div class="mix-label">${mx.label}</div>
        <div class="mix-stats">
          <div>
            <div class="mix-stat-val">${(+mx.exp_return) >= 0 ? "+" : ""}${(+mx.exp_return).toFixed(4)}%</div>
            <div class="mix-stat-lbl">${tip("Return", "Expected average return per snapshot based on historical data. Negative means the portfolio would have lost value on average.")}</div>
          </div>
          <div>
            <div class="mix-stat-val">${(+mx.exp_risk).toFixed(4)}%</div>
            <div class="mix-stat-lbl">${tip("Risk", "Portfolio volatility — how much the combined value swings. Lower risk = more stable but usually lower return.")}</div>
          </div>
        </div>
        ${bars}
        <div style="font-size:11px;color:var(--text2);margin-top:10px;">
          ${new Date(mx.created_at).toLocaleString()}
        </div>
      </div>`;
    }).join("");
  } catch (e) { console.error("loadMixes:", e); }
}

async function loadRules() {
  try {
    const [stressData, rpData, corrData] = await Promise.all([
      fetch("/api/stress").then(r => r.json()),
      fetch("/api/risk-parity").then(r => r.json()).catch(() => null),
      fetch("/api/correlation").then(r => r.json()).catch(() => null),
    ]);

    // Dynamic rules from risk-parity target vs current allocation
    let rulesHtml = "";
    let violations = 0;

    if (rpData && rpData.target && rpData.current) {
      const coins = rpData.coins || Object.keys(rpData.target);
      rulesHtml += `<div style="font-size:11px;color:var(--text2);margin-bottom:8px;font-weight:600;">Risk-Parity Target vs Current</div>`;
      coins.forEach(cid => {
        const cur = rpData.current[cid] || 0;
        const tgt = rpData.target[cid] || 0;
        const drift = Math.abs(cur - tgt);
        const driftOk = drift < 10;
        if (!driftOk) violations++;
        const driftColor = driftOk ? "var(--green)" : "var(--red)";
        const arrow = cur > tgt ? "↓ reduce" : cur < tgt ? "↑ increase" : "✓ ok";
        rulesHtml += `<div class="rule-row">
          <span class="rule-key">${cid}</span>
          <span class="rule-val" style="display:flex;gap:8px;align-items:center;">
            <span style="color:var(--text2);">${cur.toFixed(1)}%</span>
            <span style="color:var(--text2);">→</span>
            <span style="font-weight:600;">${tgt.toFixed(1)}%</span>
            <span style="color:${driftColor};font-size:11px;">(${drift >= 0.01 ? (cur > tgt ? "+" : "-") + drift.toFixed(1) + "pp" : "ok"}) ${!driftOk ? arrow : ""}</span>
          </span>
        </div>`;
      });
    } else {
      rulesHtml += `
        <div class="rule-row"><span class="rule-key">${tip("Max allocation", "No single coin > this %")}</span><span class="rule-val">40%</span></div>
        <div class="rule-row"><span class="rule-key">${tip("Min allocation", "Every coin ≥ this %")}</span><span class="rule-val">5%</span></div>`;
    }

    // Correlation warnings
    if (corrData && corrData.warnings && corrData.warnings.length) {
      violations += corrData.warnings.length;
      corrData.warnings.forEach(w => {
        rulesHtml += `<div class="rule-row" style="border-left:3px solid var(--amber);padding-left:8px;">
          <span class="rule-key" style="color:var(--amber);font-size:11px;">${w}</span>
        </div>`;
      });
    }

    // Status
    if (violations > 0) {
      rulesHtml += `<div class="rule-row"><span class="rule-key">Status</span>
        <span class="rule-status" style="color:var(--amber);">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          ${violations} issue${violations > 1 ? "s" : ""} detected
        </span>
      </div>`;
    } else {
      rulesHtml += `<div class="rule-row"><span class="rule-key">Status</span>
        <span class="rule-status status-ok">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          All rules satisfied
        </span>
      </div>`;
    }

    document.getElementById("rulesContent").innerHTML = rulesHtml;

    // Stress scenarios
    const base = stressData.base || 0;
    document.getElementById("stressContent").innerHTML = `
      <div style="font-size:12px;color:var(--text2);margin-bottom:12px;font-family:var(--font-mono);">
        ${tip("Portfolio base", "Current total value of all your holdings at live prices. Stress scenarios are applied to this number.")} $${base.toLocaleString("en", {maximumFractionDigits: 2})}
      </div>
      ${Object.entries(stressData.scenarios || {}).map(([name, s]) => `
        <div class="stress-row">
          <div>
            <div class="stress-name">${name.replace(/_/g, " ")}</div>
            <span class="stress-badge"
              style="background:${s.pct > 0 ? "var(--green-bg)" : "var(--red-bg)"};
                     color:${s.pct > 0 ? "var(--green)" : "var(--red)"};">
              ${s.pct > 0 ? "+" : ""}${s.pct}%
            </span>
          </div>
          <div style="text-align:right;">
            <div class="stress-pnl ${s.pnl >= 0 ? "pos" : "neg"}">
              ${s.pnl >= 0 ? "+" : ""}$${Math.abs(s.pnl).toLocaleString("en", {maximumFractionDigits: 0})}
            </div>
            <div style="font-size:11px;color:var(--text2);font-family:var(--font-mono);margin-top:2px;">
              → $${(s.new_val||0).toLocaleString("en", {maximumFractionDigits: 0})}
            </div>
          </div>
        </div>`).join("")}`;
  } catch (e) { console.error("loadRules:", e); }
}

async function loadPriceAlerts() {
  try {
    const [active, history] = await Promise.all([
      fetch("/api/price-alerts").then(r => r.json()),
      fetch("/api/price-alerts/history").then(r => r.json()),
    ]);
    const triggered = history.filter(a => a.triggered);
    const activeEl  = document.getElementById("activeAlertsList");
    if (activeEl) {
      activeEl.innerHTML = !active.length
        ? '<div class="empty-state">No active alerts. Add one above.</div>'
        : active.map(a => `
          <div class="alert-row" id="alert-row-${a.id}">
            <div class="alert-row-coin">
              <span class="alert-symbol">${a.symbol}</span>
              <span class="alert-coin-id">${a.coin_id}</span>
            </div>
            <div class="alert-row-condition">
              <span class="alert-badge ${a.condition}">${a.condition === "above" ? "▲ Above" : "▼ Below"}</span>
              <span class="alert-target">$${(+a.target).toLocaleString("en", {maximumFractionDigits: 6})}</span>
            </div>
            <div class="alert-row-note">${a.note || "—"}</div>
            <div class="alert-row-date">${new Date(a.created_at).toLocaleDateString()}</div>
            <button class="alert-delete-btn" onclick="deleteAlert(${a.id})">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                <path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
              </svg>
            </button>
          </div>`).join("");
    }
    const histEl = document.getElementById("triggeredAlertsList");
    if (histEl) {
      histEl.innerHTML = !triggered.length
        ? '<div class="empty-state">No alerts have triggered yet.</div>'
        : triggered.map(a => `
          <div class="alert-row triggered">
            <div class="alert-row-coin">
              <span class="alert-symbol">${a.symbol}</span>
              <span class="alert-coin-id">${a.coin_id}</span>
            </div>
            <div class="alert-row-condition">
              <span class="alert-badge ${a.condition}">${a.condition === "above" ? "▲ Above" : "▼ Below"}</span>
              <span class="alert-target">$${(+a.target).toLocaleString("en", {maximumFractionDigits: 6})}</span>
            </div>
            <div class="alert-row-note">${a.note || "—"}</div>
            <div class="alert-row-date">${new Date(a.created_at).toLocaleDateString()}</div>
            <span class="alert-fired-badge">Fired</span>
          </div>`).join("");
    }
    const badge = document.getElementById("alertNavBadge");
    if (badge) {
      badge.textContent  = active.length;
      badge.style.display = active.length ? "inline-flex" : "none";
    }
  } catch(e) { console.error("loadPriceAlerts:", e); }
}

async function deleteAlert(id) {
  try {
    await fetch(`/api/price-alerts/${id}`, {method: "DELETE"});
    document.getElementById(`alert-row-${id}`)?.remove();
    toast("Alert deleted", "info");
  } catch(_) { toast("Failed to delete alert", "error"); }
}

async function loadTrades() {
  try {
    const [trades, pnl] = await Promise.all([
      fetch("/api/trades").then(r => r.json()),
      fetch("/api/trades/pnl").then(r => r.json()),
    ]);

    const pnlEl = document.getElementById("pnlSummary");
    if (pnlEl) {
      if (!pnl.length) {
        pnlEl.innerHTML = '<div class="empty-state">No trades logged yet.</div>';
      } else {
        const totalRealised = pnl.reduce((s, p) => s + p.realised_pnl, 0);
        pnlEl.innerHTML = `
          <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;">
            <div class="pnl-summary-card">
              <div class="pnl-label">Total realised P&L</div>
              <div class="pnl-value ${totalRealised >= 0 ? 'up' : 'down'}">
                ${totalRealised >= 0 ? "+" : ""}$${Math.abs(totalRealised).toLocaleString("en",{maximumFractionDigits:2})}
              </div>
            </div>
          </div>
          <table class="data-table">
            <thead><tr>
              <th>Coin</th><th>Total Bought</th><th>Total Sold</th><th>Realised P&L</th>
            </tr></thead>
            <tbody>
              ${pnl.map(p => `<tr>
                <td><strong>${p.symbol}</strong> <span style="color:var(--text2);font-size:11px;">${p.coin_id}</span></td>
                <td>$${p.total_bought.toLocaleString("en",{maximumFractionDigits:2})}</td>
                <td>$${p.total_sold.toLocaleString("en",{maximumFractionDigits:2})}</td>
                <td class="${p.realised_pnl >= 0 ? 'up' : 'down'}">
                  ${p.realised_pnl >= 0 ? "+" : ""}$${Math.abs(p.realised_pnl).toLocaleString("en",{maximumFractionDigits:4})}
                </td>
              </tr>`).join("")}
            </tbody>
          </table>`;
      }
    }

    const logEl = document.getElementById("tradeLog");
    if (logEl) {
      if (!trades.length) {
        logEl.innerHTML = '<div class="empty-state">No trades yet. Log one above.</div>';
      } else {
        logEl.innerHTML = `
          <table class="data-table">
            <thead><tr>
              <th>Date</th><th>Coin</th><th>Side</th><th>Amount</th><th>Price</th><th>Total</th><th>Fee</th><th>Note</th>
            </tr></thead>
            <tbody>
              ${trades.map(t => `<tr>
                <td style="font-size:11px;font-family:var(--font-mono);">${new Date(t.traded_at).toLocaleString()}</td>
                <td><strong>${t.symbol}</strong></td>
                <td><span class="trade-side ${t.side}">${t.side.toUpperCase()}</span></td>
                <td>${(+t.amount).toLocaleString("en",{maximumFractionDigits:6})}</td>
                <td>$${(+t.price).toLocaleString("en",{maximumFractionDigits:4})}</td>
                <td>$${((+t.amount)*(+t.price)).toLocaleString("en",{maximumFractionDigits:2})}</td>
                <td>$${(+t.fee).toFixed(2)}</td>
                <td style="color:var(--text2);font-size:12px;">${t.note||"—"}</td>
              </tr>`).join("")}
            </tbody>
          </table>`;
      }
    }
  } catch(e) { console.error("loadTrades:", e); }
}

async function loadWatchlist() {
  try {
    const data = await fetch("/api/watchlist").then(r => r.json());
    const el   = document.getElementById("watchlistCoins");
    if (!el) return;
    if (!data.length) {
      el.innerHTML = '<div class="empty-state">Your watchlist is empty. Search a coin below to add one.</div>';
      return;
    }
    el.innerHTML = data.map(c => `
      <div class="watchlist-row" id="wl-${c.coin_id}">
        <div>
          <span class="wl-symbol">${c.symbol}</span>
          <span class="wl-name">${c.name || c.coin_id}</span>
        </div>
        <button class="alert-delete-btn" onclick="removeFromWatchlist('${c.coin_id}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
          </svg>
        </button>
      </div>`).join("");
  } catch(e) { console.error("loadWatchlist:", e); }
}

let searchTimeout;
document.getElementById("watchlistSearch")?.addEventListener("input", function() {
  clearTimeout(searchTimeout);
  const q = this.value.trim();
  const resultsEl = document.getElementById("searchResults");
  if (!q) { if (resultsEl) resultsEl.innerHTML = ""; return; }
  searchTimeout = setTimeout(async () => {
    try {
      const results = await fetch(`/api/watchlist/search?q=${encodeURIComponent(q)}`).then(r => r.json());
      if (!resultsEl) return;
      if (!results.length) {
        resultsEl.innerHTML = '<div class="empty-state">No results found.</div>';
        return;
      }
      resultsEl.innerHTML = results.map(c => `
        <div class="search-result-row" onclick="addToWatchlist('${c.id}','${c.symbol}','${(c.name||"").replace(/'/g,"\\'")}')">
          <span class="wl-symbol">${c.symbol}</span>
          <span class="wl-name">${c.name}</span>
          ${c.rank ? `<span style="font-size:11px;color:var(--text2);margin-left:auto;">#${c.rank}</span>` : ""}
        </div>`).join("");
    } catch(_) {}
  }, 400);
});

async function addToWatchlist(coinId, symbol, name) {
  try {
    await fetch("/api/watchlist", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({coin_id: coinId, symbol, name})
    });
    document.getElementById("watchlistSearch").value = "";
    document.getElementById("searchResults").innerHTML = "";
    toast(`${symbol} added to watchlist`, "success");
    loadWatchlist();
  } catch(_) { toast("Failed to add coin", "error"); }
}

async function removeFromWatchlist(coinId) {
  try {
    await fetch(`/api/watchlist/${coinId}`, {method: "DELETE"});
    document.getElementById(`wl-${coinId}`)?.remove();
    toast("Removed from watchlist", "info");
  } catch(_) { toast("Failed to remove coin", "error"); }
}

async function loadFearGreed() {
  try {
    const data = await fetch("/api/fear-greed").then(r => r.json());
    const val   = data.value || 50;
    const label = data.label || "Unknown";
    drawFGGauge(val, label);
    const fgLbl = document.getElementById("fgLabel");
    if (fgLbl) fgLbl.textContent = label;
    const mvFg = document.getElementById("mv-fg");
    const mdFg = document.getElementById("md-fg");
    if (mvFg) mvFg.textContent = val;
    if (mdFg) mdFg.textContent = label;
  } catch(_) {
    const fgLbl2 = document.getElementById("fgLabel");
    if (fgLbl2) fgLbl2.textContent = "Unavailable";
  }
}

function drawFGGauge(value, label) {
  const canvas = document.getElementById("fgGauge");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const cx = W / 2, cy = H - 6;
  const r = Math.min(W / 2, H) - 14;
  const lw = Math.max(10, r * 0.2);
  const toRad = deg => (deg - 180) * Math.PI / 180;

  const segs = [
    { from: 0,  to: 25,  color: "#ef4444" },
    { from: 25, to: 45,  color: "#f97316" },
    { from: 45, to: 55,  color: "#eab308" },
    { from: 55, to: 75,  color: "#84cc16" },
    { from: 75, to: 100, color: "#22c55e" },
  ];
  segs.forEach(s => {
    ctx.beginPath();
    ctx.arc(cx, cy, r, toRad(s.from * 1.8), toRad(s.to * 1.8));
    ctx.lineWidth = lw;
    ctx.strokeStyle = s.color + "55";
    ctx.stroke();
  });

  ctx.beginPath();
  ctx.arc(cx, cy, r, toRad(0), toRad(value * 1.8));
  ctx.lineWidth = lw;
  const activeColor = value >= 75 ? "#22c55e" : value >= 55 ? "#84cc16"
                    : value >= 45 ? "#eab308" : value >= 25 ? "#f97316" : "#ef4444";
  ctx.strokeStyle = activeColor;
  ctx.stroke();

  const needleAngle = (value * 1.8 - 180) * Math.PI / 180;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx + (r - lw - 2) * Math.cos(needleAngle), cy + (r - lw - 2) * Math.sin(needleAngle));
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#fff";
  ctx.lineCap = "round";
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(cx, cy, 4, 0, Math.PI * 2);
  ctx.fillStyle = "#fff";
  ctx.fill();

  ctx.font = `bold ${Math.max(16, r * 0.35)}px monospace`;
  ctx.fillStyle = activeColor;
  ctx.textAlign = "center";
  ctx.fillText(value, cx, cy - Math.max(16, r * 0.3));
}

let donutChartInst = null;
const DONUT_COLORS = [
  "#06b6d4","#8b5cf6","#f59e0b","#10b981","#f43f5e",
  "#3b82f6","#ec4899","#14b8a6","#f97316","#6366f1"
];

async function loadDonut() {
  try {
    const data = await fetch("/api/portfolio").then(r => r.json());
    const positions = (data.positions || []).filter(p => (p.value || 0) > 0);
    if (!positions.length) return;

    const labels  = positions.map(p => p.symbol || p.coin_id);
    const values  = positions.map(p => p.alloc_pct || 0);
    const colors  = positions.map((_, i) => DONUT_COLORS[i % DONUT_COLORS.length]);

    const ctx = document.getElementById("donutChart")?.getContext("2d");
    if (!ctx) return;
    if (donutChartInst) { donutChartInst.destroy(); donutChartInst = null; }

    donutChartInst = new Chart(ctx, {
      type: "doughnut",
      data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0, hoverOffset: 4 }] },
      options: {
        responsive: true,
        cutout: "72%",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: c => ` ${c.label}: ${c.parsed.toFixed(1)}%` },
            backgroundColor: "#111827", titleColor: "#f9fafb", bodyColor: "#9ca3af",
          }
        },
        animation: { duration: 600 }
      }
    });

    const legend = document.getElementById("donutLegend");
    if (legend) {
      legend.innerHTML = positions.map((p, i) => `
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="width:10px;height:10px;border-radius:50%;background:${colors[i]};flex-shrink:0;"></span>
          <span style="color:var(--text1);flex:1;">${p.symbol || p.coin_id}</span>
          <span style="color:var(--text2);font-family:monospace;">${(p.alloc_pct||0).toFixed(1)}%</span>
        </div>`).join("");
    }
  } catch(_) {}
}

let _compareRows = [];

async function loadCompareChart() {
  const compareCoin = document.getElementById("compareCoin")?.value;
  if (!compareCoin || compareCoin === _currentCoin) {
    const cmpEl = document.getElementById("compareCoin");
    if (cmpEl) cmpEl.value = "";
    return;
  }
  try {
    _compareRows = await fetch(`/api/history/${compareCoin}`).then(r => r.json());
    buildCompareChart(_allRows, _compareRows, _currentCoin, compareCoin);
  } catch(_) {}
}

function buildCompareChart(rowsA, rowsB, labelA, labelB) {
  const ctx = document.getElementById("priceChart");
  if (!ctx) return;
  if (priceChart) { priceChart.destroy(); priceChart = null; }

  const norm = rows => {
    if (!rows.length) return [];
    const base = rows[0].price_usd || 1;
    return rows.map(r => +((r.price_usd / base - 1) * 100).toFixed(4));
  };

  const labelsA  = rowsA.map(r => r.fetched_at.slice(11,16));
  const maxLen   = Math.max(rowsA.length, rowsB.length);
  const xLabels  = rowsA.length >= rowsB.length
    ? labelsA
    : rowsB.map(r => r.fetched_at.slice(11,16));

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: xLabels,
      datasets: [
        {
          label: labelA.toUpperCase() + " %",
          data: norm(rowsA),
          borderColor: CHART_COLORS[labelA] || "#06b6d4",
          borderWidth: 2, pointRadius: 0, tension: 0.4, fill: false,
        },
        {
          label: labelB.toUpperCase() + " %",
          data: norm(rowsB),
          borderColor: CHART_COLORS[labelB] || "#8b5cf6",
          borderWidth: 2, pointRadius: 0, tension: 0.4, fill: false,
          borderDash: [4, 2],
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: true, labels: { color: "#9ca3af", font: { size: 11 } } },
        tooltip: {
          backgroundColor: "#111827", borderColor: "#1f2937", borderWidth: 1,
          titleColor: "#f9fafb", bodyColor: "#9ca3af",
          callbacks: { label: c => ` ${c.dataset.label}: ${c.parsed.y >= 0 ? "+" : ""}${c.parsed.y.toFixed(2)}%` }
        }
      },
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "#4b5563", font: { size: 10 }, maxTicksLimit: 8 }},
        y: { position: "right", grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "#4b5563", font: { size: 10 },
          callback: v => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%` }}
      },
      interaction: { intersect: false, mode: "index" },
      animation: { duration: 600 }
    }
  });
}

let btChartInst = null;

async function runBacktest() {
  const btn     = document.getElementById("runBacktestBtn");
  const coin    = document.getElementById("btCoin").value;
  const shortW  = document.getElementById("btShortW").value;
  const longW   = document.getElementById("btLongW").value;
  const capital = document.getElementById("btCapital").value;

  btn.textContent = "Running…";
  btn.disabled    = true;

  try {
    const data = await fetch(
      `/api/backtest?coin=${coin}&short_w=${shortW}&long_w=${longW}&capital=${capital}`
    ).then(r => r.json());

    if (data.error) { toast(data.error, "error"); return; }

    // Summary cards
    document.getElementById("btSummary").style.display = "block";
    document.getElementById("btTradeLog").style.display = "block";

    const ret = data.total_return;
    document.getElementById("bt-final").textContent   = `$${data.final_value.toLocaleString("en",{maximumFractionDigits:2})}`;
    document.getElementById("bt-return").textContent  = `${ret >= 0 ? "+" : ""}${ret.toFixed(2)}%`;
    document.getElementById("bt-return").style.color  = ret >= 0 ? "var(--green)" : "var(--red)";
    document.getElementById("bt-trades").textContent  = data.total_trades;
    document.getElementById("bt-winrate").textContent = `${data.win_rate.toFixed(1)}%`;
    document.getElementById("bt-winrate").style.color = data.win_rate >= 50 ? "var(--green)" : "var(--red)";
    document.getElementById("bt-maxdd").textContent   = `${data.max_drawdown.toFixed(2)}%`;
    document.getElementById("bt-maxdd").style.color   = "var(--red)";

    const ctx2 = document.getElementById("btChart")?.getContext("2d");
    if (ctx2) {
      if (btChartInst) { btChartInst.destroy(); btChartInst = null; }
      const equity = data.equity || [];
      btChartInst = new Chart(ctx2, {
        type: "line",
        data: {
          labels: equity.map((_, i) => i),
          datasets: [{
            label: "Portfolio Value",
            data: equity.map(e => e.value),
            borderColor: ret >= 0 ? "#10b981" : "#f43f5e",
            borderWidth: 2, pointRadius: 0, tension: 0.3, fill: true,
            backgroundColor: (c) => {
              const g = c.chart.ctx.createLinearGradient(0,0,0,200);
              g.addColorStop(0, (ret >= 0 ? "#10b981" : "#f43f5e") + "30");
              g.addColorStop(1, (ret >= 0 ? "#10b981" : "#f43f5e") + "00");
              return g;
            }
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: {
            backgroundColor: "#111827", titleColor: "#f9fafb", bodyColor: "#9ca3af",
            callbacks: { label: c => ` $${c.parsed.y.toLocaleString("en",{maximumFractionDigits:2})}` }
          }},
          scales: {
            x: { display: false },
            y: { position: "right", grid: { color: "rgba(255,255,255,0.04)" }, ticks: {
              color: "#4b5563", font: { size: 10 },
              callback: v => `$${v >= 1000 ? (v/1000).toFixed(1)+"k" : v.toFixed(0)}`
            }}
          },
          animation: { duration: 600 }
        }
      });
    }

    const sells = (data.trades || []).filter(t => t.type === "SELL");
    document.getElementById("btTradeBody").innerHTML = !sells.length
      ? '<div class="empty-state">No completed trades — need more crossovers in the data.</div>'
      : `<table class="data-table">
          <thead><tr><th>#</th><th>Buy Price</th><th>Sell Price</th><th>P&L</th><th>Result</th></tr></thead>
          <tbody>${sells.map((t, i) => `<tr>
            <td>${i + 1}</td>
            <td>$${(t.price||0).toLocaleString("en",{maximumFractionDigits:4})}</td>
            <td>$${(t.sell_price||0).toLocaleString("en",{maximumFractionDigits:4})}</td>
            <td class="${(t.pnl||0) >= 0 ? 'up' : 'down'}">${(t.pnl||0) >= 0 ? "+" : ""}$${Math.abs(t.pnl||0).toFixed(4)}</td>
            <td><span class="trade-side ${t.win ? 'buy' : 'sell'}">${t.win ? "WIN" : "LOSS"}</span></td>
          </tr>`).join("")}</tbody>
        </table>`;

    toast(`Backtest complete — ${data.total_trades} trades, ${ret >= 0 ? "+" : ""}${ret.toFixed(2)}% return`, ret >= 0 ? "success" : "info");
  } catch(e) {
    toast("Backtest failed: " + e.message, "error");
  } finally {
    btn.textContent = "▶ Run Backtest";
    btn.disabled    = false;
  }
}


let _newsCoin = "";

async function loadNews(coin) {
  if (coin !== undefined) _newsCoin = coin;

  document.querySelectorAll(".news-filter").forEach(b =>
    b.classList.toggle("active", b.dataset.coin === _newsCoin));

  const grid = document.getElementById("newsGrid");
  if (!grid) return;
  grid.innerHTML = '<div class="empty-state">Loading news…</div>';

  try {
    const url  = `/api/news${_newsCoin ? "?coin=" + _newsCoin : ""}`;
    const data = await fetch(url).then(r => r.json());

    if (data.error) {
      grid.innerHTML = `<div class="empty-state">Could not load news: ${data.error}</div>`;
      return;
    }
    if (!data.length) {
      grid.innerHTML = '<div class="empty-state">No news found for this filter.</div>';
      return;
    }

    grid.innerHTML = data.map(n => {
      const sentClass = n.sentiment === "bullish" ? "bullish" :
                        n.sentiment === "bearish" ? "bearish" : "neutral-sent";
      const sentLabel = n.sentiment === "bullish" ? "▲ Bullish" :
                        n.sentiment === "bearish" ? "▼ Bearish" : "— Neutral";
      const coins = n.currencies.filter(Boolean).slice(0, 4)
        .map(c => `<span class="news-coin-tag">${c}</span>`).join("");
      const ago   = _timeAgo(n.published);
      return `<div class="news-card">
        <div class="news-meta">
          <span class="news-source">${n.source || "News"}</span>
          <span class="news-time">${ago}</span>
          <span class="news-sentiment ${sentClass}">${sentLabel}</span>
          <span style="margin-left:auto;display:flex;gap:4px;">${coins}</span>
        </div>
        <a class="news-title" href="${n.url}" target="_blank" rel="noopener">${n.title}</a>
        ${n.votes_pos || n.votes_neg ? `
        <div class="news-votes">
          <span style="color:var(--green);">▲ ${n.votes_pos}</span>
          <span style="color:var(--red);">▼ ${n.votes_neg}</span>
        </div>` : ""}
      </div>`;
    }).join("");
  } catch(e) {
    grid.innerHTML = `<div class="empty-state">Failed to load news. Check your connection.</div>`;
  }
}

function _timeAgo(val) {
  if (!val) return "";
  // Handle both unix timestamps (number) and ISO strings
  const ts = typeof val === "number" ? val * 1000 : new Date(val).getTime();
  const diff = Date.now() - ts;
  const m = Math.floor(diff / 60000);
  if (m < 1)  return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h/24)}d ago`;
}

function animateNumber(id, target, formatter) {
  const el = document.getElementById(id);
  if (!el || isNaN(target)) return;
  const dur = 800, t0 = performance.now();
  (function step(now) {
    const t    = Math.min((now - t0) / dur, 1);
    const ease = 1 - Math.pow(1 - t, 3);
    el.textContent = formatter(target * ease);
    if (t < 1) requestAnimationFrame(step);
  })(performance.now());
}

function toast(msg, type = "info") {
  const c = document.getElementById("toastContainer");
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.innerHTML = `<span class="toast-msg">${msg}</span>
    <span class="toast-close" onclick="this.parentElement.remove()">×</span>`;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Sub-tab system ────────────────────────────────────────────────────────────
function showSubTab(sectionId, subtabId) {
  const section = document.getElementById(`sec-${sectionId}`);
  if (!section) return;

  section.querySelectorAll(".sub-tab").forEach(b =>
    b.classList.toggle("active", b.dataset.subtab === subtabId));
  section.querySelectorAll("[id^='subtab-']").forEach(el =>
    el.style.display = el.id === `subtab-${subtabId}` ? "" : "none");

  const loaders = {
    "dashboard":    () => { loadOverview(); loadFearGreed(); loadDonut(); _allRows = []; loadChart(_currentCoin || WATCHLIST[0] || "bitcoin", _currentMins || 0); },
    "news":         () => loadNews(),
    "positions":    loadPortfolio,
    "tradelog":     loadTrades,
    "predictions":  loadPredictions,
    "risk":         loadRisk,
    "mixes":        loadMixes,
    "backtest":     () => {},
    "allocation":   loadRules,
    "price-alerts": loadPriceAlerts,
  };
  loaders[subtabId]?.();
}

// Wire sub-tab clicks for all sections
document.querySelectorAll(".sub-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    const section = btn.closest(".dash-section");
    if (!section) return;
    const sectionId = section.id.replace("sec-", "");
    showSubTab(sectionId, btn.dataset.subtab);
  });
});

const SECTION_LOADERS = {
  overview:  () => { loadFearGreed(); loadDonut(); showSubTab("overview",  "dashboard"); },
  portfolio: () => showSubTab("portfolio", "positions"),
  analysis:  () => showSubTab("analysis",  "predictions"),
  rules:     () => showSubTab("rules",     "allocation"),
  watchlist: loadWatchlist,
};

function showSection(id) {
  document.querySelectorAll(".dash-section").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".sb-link").forEach(l => l.classList.remove("active"));
  document.getElementById(`sec-${id}`)?.classList.add("active");
  document.querySelector(`[data-section="${id}"]`)?.classList.add("active");
  document.getElementById("breadcrumb").textContent =
    document.querySelector(`[data-section="${id}"] span`)?.textContent || id;
  SECTION_LOADERS[id]?.();
}

document.querySelectorAll(".sb-link").forEach(link =>
  link.addEventListener("click", e => { e.preventDefault(); showSection(link.dataset.section); })
);

document.getElementById("coinTabs")?.addEventListener("click", e => {
  const tab = e.target.closest(".coin-tab");
  if (tab) { _allRows = []; loadChart(tab.dataset.coin); }
});

document.getElementById("compareCoin")?.addEventListener("change", function() {
  if (this.value) {
    loadCompareChart();
  } else {
    _compareRows = [];
    _allRows = [];
    loadChart(_currentCoin, _currentMins);
  }
});

document.getElementById("runBacktestBtn")?.addEventListener("click", runBacktest);



document.getElementById("sec-overview")?.addEventListener("click", e => {
  const btn = e.target.closest(".news-filter");
  if (btn) loadNews(btn.dataset.coin);
});

document.getElementById("clearDemoBtn")?.addEventListener("click", async () => {
  if (!confirm("Remove ALL positions from your portfolio? This cannot be undone.")) return;
  try {
    await fetch("/api/position/clear-all", {method: "POST"});
    toast("All positions cleared", "info");
    loadPortfolio();
    loadDonut();
  } catch(_) { toast("Failed to clear positions", "error"); }
});

document.getElementById("addPosBtn")?.addEventListener("click", () => {
  const f = document.getElementById("addFormCard");
  f.style.display = f.style.display === "none" ? "block" : "none";
});
document.getElementById("cancelPosBtn")?.addEventListener("click", () => {
  document.getElementById("addFormCard").style.display = "none";
});
document.getElementById("posCoin")?.addEventListener("change", function() {
  document.getElementById("posSym").value = this.value.slice(0, 3).toUpperCase();
});
document.getElementById("savePosBtn")?.addEventListener("click", async () => {
  const d = {
    coin_id: document.getElementById("posCoin").value,
    symbol:  document.getElementById("posSym").value || document.getElementById("posCoin").value.slice(0, 3).toUpperCase(),
    amount:  document.getElementById("posAmt").value,
    avg_buy: document.getElementById("posAvg").value,
  };
  if (!d.amount || !d.avg_buy) return toast("Amount and average buy price are required.", "error");
  try {
    await fetch("/api/position", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(d)
    });
    document.getElementById("addFormCard").style.display = "none";
    toast(`Position saved for ${d.symbol}`, "success");
    loadPortfolio();
  } catch(_) { toast("Failed to save position", "error"); }
});

document.getElementById("saveTradeBtn")?.addEventListener("click", async () => {
  const d = {
    coin_id: document.getElementById("tradeCoin").value,
    symbol:  document.getElementById("tradeCoin").value.slice(0,6).toUpperCase(),
    side:    document.getElementById("tradeSide").value,
    amount:  document.getElementById("tradeAmount").value,
    price:   document.getElementById("tradePrice").value,
    fee:     document.getElementById("tradeFee").value || 0,
    note:    document.getElementById("tradeNote").value,
  };
  if (!d.amount || !d.price) return toast("Amount and price are required.", "error");
  try {
    await fetch("/api/trades", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(d)
    });
    toast(`${d.side.toUpperCase()} trade logged for ${d.symbol}`, "success");
    document.getElementById("tradeAmount").value = "";
    document.getElementById("tradePrice").value  = "";
    document.getElementById("tradeNote").value   = "";
    loadTrades();
  } catch(_) { toast("Failed to log trade", "error"); }
});

document.getElementById("saveAlertBtn")?.addEventListener("click", async () => {
  const coin_id   = document.getElementById("alertCoin").value;
  const condition = document.getElementById("alertCondition").value;
  const target    = document.getElementById("alertTarget").value;
  const note      = document.getElementById("alertNote").value;
  if (!target || isNaN(target)) return toast("Enter a valid target price", "error");
  try {
    const res  = await fetch("/api/price-alerts", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({coin_id, symbol: coin_id.slice(0,6).toUpperCase(), condition, target: parseFloat(target), note})
    });
    const data = await res.json();
    if (data.ok) {
      toast(`Alert set: ${coin_id} ${condition} $${parseFloat(target).toLocaleString()}`, "success");
      document.getElementById("alertTarget").value = "";
      document.getElementById("alertNote").value   = "";
      loadPriceAlerts();
    } else {
      toast(data.error || "Failed to save alert", "error");
    }
  } catch(_) { toast("Failed to save alert", "error"); }
});

document.getElementById("runMixBtn")?.addEventListener("click", async () => {
  const btn = document.getElementById("runMixBtn");
  btn.classList.add("loading"); btn.textContent = "Running…";
  try {
    const data = await (await fetch("/api/run-mixes", {method: "POST"})).json();
    toast(data.message, data.ok ? "success" : "error");
    if (data.ok) loadMixes();
  } catch(_) { toast("Mix calculation failed", "error"); }
  btn.classList.remove("loading");
  btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> Re-run Calculator`;
});

document.getElementById("exportBtn")?.addEventListener("click", async () => {
  try {
    const data = await (await fetch("/api/export-csv", {method: "POST"})).json();
    toast(`CSVs exported to ${data.dir}/`, "success");
  } catch(_) { toast("Export failed", "error"); }
});

document.getElementById("refreshRing")?.addEventListener("click", async () => {
  const ring = document.getElementById("refreshRing");
  ring.classList.add("spinning");
  await refreshTicker();
  const sec = document.querySelector(".sb-link.active")?.dataset.section || "overview";
  SECTION_LOADERS[sec]?.();
  ring.classList.remove("spinning");
  toast("Data refreshed", "info");
});

let countdown = 60;

setInterval(async () => {
  countdown--;
  if (countdown <= 0) {
    countdown = 60;
    // Only fetch if SocketIO didn't already push an update
    await refreshTicker();
    const sec = document.querySelector(".sb-link.active")?.dataset.section || "overview";
    SECTION_LOADERS[sec]?.();
  }
  const lbl = document.getElementById("liveLabel");
  if (lbl && countdown > 0) lbl.textContent = `Refresh in ${countdown}s`;
}, 1000);

document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM ready — starting CryptoManager");
  showSection("overview");
});