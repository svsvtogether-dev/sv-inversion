let currentSymbol = "BTCEUR";
let currentCategory = "all";
let isRunning = true;
let marketsCatalog = {};
let configInitialized = false;
let tradesFilter = "ALL"; // "ALL" | "SELL"
let activeEnvironment = "simulation"; // "simulation" | "live"
let isLiveArmed = false;
let lastStateData = null;

// DOM Elements
const kpiTotalValue = document.getElementById("kpiTotalValue");
const kpiNetProfit = document.getElementById("kpiNetProfit");
const kpiCash = document.getElementById("kpiCash");
const kpiInPosition = document.getElementById("kpiInPosition");
const kpiRealizedPnl = document.getElementById("kpiRealizedPnl");
const kpiFees = document.getElementById("kpiFees");
const kpiWinRate = document.getElementById("kpiWinRate");
const kpiTradesCount = document.getElementById("kpiTradesCount");

const categoryTabs = document.getElementById("categoryTabs");
const symbolPillsContainer = document.getElementById("symbolPillsContainer");

const marketSymbolLabel = document.getElementById("marketSymbolLabel");
const marketPrice = document.getElementById("marketPrice");
const marketChange24h = document.getElementById("marketChange24h");
const decisionBadge = document.getElementById("decisionBadge");
const decisionDesc = document.getElementById("decisionDesc");

const rsiValue = document.getElementById("rsiValue");
const rsiNeedle = document.getElementById("rsiNeedle");
const emaFast = document.getElementById("emaFast");
const emaSlow = document.getElementById("emaSlow");
const sma50 = document.getElementById("sma50");
const bbUpper = document.getElementById("bbUpper");
const bbLower = document.getElementById("bbLower");

const positionsBadge = document.getElementById("positionsBadge");
const positionsTableBody = document.getElementById("positionsTableBody");
const tradesTableBody = document.getElementById("tradesTableBody");
const terminalLogs = document.getElementById("terminalLogs");
const lastTickTime = document.getElementById("lastTickTime");

const toggleBotBtn = document.getElementById("toggleBotBtn");
const botStateLabel = document.getElementById("botStateLabel");
const statusIndicator = document.getElementById("statusIndicator");
const emergencyBtn = document.getElementById("emergencyBtn");
const resetBtn = document.getElementById("resetBtn");
const saveConfigBtn = document.getElementById("saveConfigBtn");

// Environment Switcher Elements
const tabSimBtn = document.getElementById("tabSimBtn");
const tabLiveBtn = document.getElementById("tabLiveBtn");
const liveWarningBanner = document.getElementById("liveWarningBanner");
const liveApiStatusText = document.getElementById("liveApiStatusText");
const liveEurBalanceBadge = document.getElementById("liveEurBalanceBadge");
const liveBnbStatusBadge = document.getElementById("liveBnbStatusBadge");
const liveArmToggleBtn = document.getElementById("liveArmToggleBtn");
const headerEnvBadge = document.getElementById("headerEnvBadge");
const headerSubtitle = document.getElementById("headerSubtitle");

// Priority buttons
const quickBtnBTC = document.getElementById("quickBtnBTC");
const quickBtnETH = document.getElementById("quickBtnETH");

// Form inputs
const cfgOrderAmount = document.getElementById("cfgOrderAmount");
const cfgTakeProfit = document.getElementById("cfgTakeProfit");
const cfgStopLoss = document.getElementById("cfgStopLoss");
const cfgRsiBuy = document.getElementById("cfgRsiBuy");
const cfgRsiSell = document.getElementById("cfgRsiSell");
const cfgSmaPeriod = document.getElementById("cfgSmaPeriod");
const cfgMsciSweep = document.getElementById("cfgMsciSweep");
const dcaMarginHint = document.getElementById("dcaMarginHint");

const kpiMsciVault = document.getElementById("kpiMsciVault");
const kpiMsciSub = document.getElementById("kpiMsciSub");

function formatEur(val) {
  if (val === 0 || !val) return "0,00 €";
  if (Math.abs(val) < 0.0001) return `€${val.toFixed(8)}`;
  if (Math.abs(val) < 0.01) return `€${val.toFixed(6)}`;
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(val);
}

function formatCrypto(val) {
  if (val === 0 || !val) return "0";
  if (Math.abs(val) < 0.0001) return val.toFixed(8);
  if (Math.abs(val) < 0.01) return val.toFixed(6);
  if (Math.abs(val) >= 1000) return val.toLocaleString('es-ES', { maximumFractionDigits: 2 });
  return val.toFixed(4);
}

// Cálculo dinámico del margen de compras escalonadas
function updateDcaMarginHint() {
  const orderAmt = parseFloat(cfgOrderAmount ? cfgOrderAmount.value : 5.0) || 5.0;
  const p = (activeEnvironment === "live" && lastStateData && lastStateData.live) 
    ? lastStateData.live 
    : (lastStateData ? (lastStateData.simulation || lastStateData.portfolio) : null);
  const cash = p ? (p.cash_eur ?? 15.0) : 15.0;
  const steps = Math.floor(cash / orderAmt);
  if (dcaMarginHint) {
    if (cash < 5.0) {
      dcaMarginHint.innerHTML = `<span style="color:#f87171; font-weight:600;">⚠️ Saldo libre (€${cash.toFixed(2)}) &lt; 5€ (MIN_NOTIONAL). Entradas bloqueadas: esperando cierre de posición.</span>`;
    } else {
      dcaMarginHint.innerHTML = `Margen: <strong>${steps} compra${steps === 1 ? "" : "s"} escalonada${steps === 1 ? "" : "s"}</strong> posibles (Saldo libre: €${cash.toFixed(2)} / Orden: €${orderAmt.toFixed(2)})`;
    }
  }
}

// Quick pair selector
window.selectQuickSymbol = async function(symbol) {
  currentSymbol = symbol;
  updateQuickButtons(symbol);
  await fetch("/static/api/symbol", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol })
  });
  fetchState();
};

function updateQuickButtons(activeSym) {
  if (quickBtnBTC) quickBtnBTC.classList.toggle("active", activeSym === "BTCEUR");
  if (quickBtnETH) quickBtnETH.classList.toggle("active", activeSym === "ETHEUR");
}

// Environment Management
function updateEnvironmentUI(env) {
  if (!tabSimBtn || !tabLiveBtn) return;
  if (env === "live") {
    tabLiveBtn.className = "env-tab-btn active live-active";
    tabSimBtn.className = "env-tab-btn";
    if (liveWarningBanner) liveWarningBanner.style.display = "flex";
    if (headerEnvBadge) {
      headerEnvBadge.textContent = "🔴 DINERO REAL (BINANCE LIVE)";
      headerEnvBadge.className = "badge live";
    }
    if (headerSubtitle) {
      headerSubtitle.textContent = "🔴 Binance Spot Oficial (EUR) - Operativa en Producción";
    }
    if (resetBtn) resetBtn.style.display = "none";
  } else {
    tabSimBtn.className = "env-tab-btn active";
    tabLiveBtn.className = "env-tab-btn";
    if (liveWarningBanner) liveWarningBanner.style.display = "none";
    if (headerEnvBadge) {
      headerEnvBadge.textContent = "🧪 SIMULACIÓN 15 €";
      headerEnvBadge.className = "badge paper";
    }
    if (headerSubtitle) {
      headerSubtitle.textContent = "🧪 Paper Trading Cuantitativo (Forward-testing hasta el viernes)";
    }
    if (resetBtn) resetBtn.style.display = "inline-flex";
  }
  updateDcaMarginHint();
}

window.setEnvironment = async function(env) {
  activeEnvironment = env;
  updateEnvironmentUI(env);

  try {
    const res = await fetch(`/static/api/environment?env=${env}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ environment: env })
    });
    if (!res.ok) {
      await fetch(`/static/api/environment?env=${env}`);
    }
  } catch (err) {
    try { await fetch(`/static/api/environment?env=${env}`); } catch(e) {}
  }
  fetchState();
};

window.toggleLiveArmed = async function() {
  if (!isLiveArmed) {
    const ok = confirm("⚠️ ATENCIÓN: ¿Estás seguro de que deseas armar la operativa en DINERO REAL?\n\nAl activarlo, cualquier señal de compra o venta se ejecutará en tu cuenta real de Binance Spot con tus fondos reales.");
    if (!ok) return;
    try {
      await fetch("/static/api/live_armed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ armed: true })
      });
      fetchState();
    } catch (err) {
      console.error("Error armando trading real:", err);
    }
  } else {
    try {
      await fetch("/static/api/live_armed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ armed: false })
      });
      fetchState();
    } catch (err) {
      console.error("Error desarmando trading real:", err);
    }
  }
};

// Fetch bot state
async function fetchState() {
  try {
    const res = await fetch("/static/api/status");
    if (!res.ok) return;
    const data = await res.json();
    renderState(data);
  } catch (err) {
    console.error("Error al actualizar datos:", err);
  }
}

function renderPills(catalog, activeCat, activeSym) {
  symbolPillsContainer.innerHTML = "";
  for (const [sym, meta] of Object.entries(catalog)) {
    if (activeCat !== "all" && meta.category !== activeCat && meta.sub_category !== activeCat) continue;

    const btn = document.createElement("button");
    btn.className = `pill-btn ${sym === activeSym ? "active" : ""}`;
    btn.dataset.symbol = sym;
    btn.innerHTML = `
      <span>${meta.name}</span>
      <span class="pill-tag">${meta.symbol_clean || sym}</span>
    `;
    btn.addEventListener("click", async () => {
      await fetch("/static/api/symbol", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym })
      });
      fetchState();
    });
    symbolPillsContainer.appendChild(btn);
  }
}

function renderState(data) {
  lastStateData = data;
  currentSymbol = data.current_symbol;
  currentCategory = data.active_category || "all";
  isRunning = data.is_running;
  marketsCatalog = data.markets_catalog || {};
  activeEnvironment = data.active_environment || "simulation";
  isLiveArmed = Boolean(data.live_trading_armed);

  updateQuickButtons(currentSymbol);

  // Environment Switcher UI state
  if (tabSimBtn && tabLiveBtn) {
    if (activeEnvironment === "live") {
      tabLiveBtn.className = "env-tab-btn active live-active";
      tabSimBtn.className = "env-tab-btn";
      if (liveWarningBanner) liveWarningBanner.style.display = "flex";
      if (headerEnvBadge) {
        headerEnvBadge.textContent = "🔴 DINERO REAL (BINANCE LIVE)";
        headerEnvBadge.className = "badge live";
      }
      if (headerSubtitle) {
        headerSubtitle.textContent = "🔴 Binance Spot Oficial (EUR) - Operativa en Producción";
      }
      if (resetBtn) resetBtn.style.display = "none";

      const binance = data.binance_account || {};
      if (liveApiStatusText) {
        liveApiStatusText.textContent = binance.status || "Conectado";
        liveApiStatusText.style.color = binance.connected ? "#4ade80" : "#f87171";
      }
      if (liveEurBalanceBadge) {
        liveEurBalanceBadge.textContent = formatEur(binance.eur_cash || 0);
      }
      if (liveBnbStatusBadge) {
        if (binance.has_bnb_fee_discount) {
          liveBnbStatusBadge.textContent = `✅ Activo (0.075%) - Saldo: ${binance.bnb_cash} BNB`;
          liveBnbStatusBadge.style.color = "#fbbf24";
        } else {
          liveBnbStatusBadge.textContent = `ℹ️ ${binance.bnb_cash ? binance.bnb_cash + ' BNB' : 'Sin BNB'} (Tarifa 0.10%)`;
          liveBnbStatusBadge.style.color = "#94a3b8";
        }
      }
      if (liveArmToggleBtn) {
        if (isLiveArmed) {
          liveArmToggleBtn.textContent = "🔴 OPERATIVA ARMADA (Trading Real Activo)";
          liveArmToggleBtn.className = "btn btn-sm btn-armed";
        } else {
          liveArmToggleBtn.textContent = "🛡️ DESARMADO (Modo Seguro)";
          liveArmToggleBtn.className = "btn btn-sm btn-outline-warning";
        }
      }
    } else {
      tabSimBtn.className = "env-tab-btn active";
      tabLiveBtn.className = "env-tab-btn";
      if (liveWarningBanner) liveWarningBanner.style.display = "none";
      if (headerEnvBadge) {
        headerEnvBadge.textContent = "🧪 SIMULACIÓN 15 €";
        headerEnvBadge.className = "badge paper";
      }
      if (headerSubtitle) {
        headerSubtitle.textContent = "🧪 Paper Trading Cuantitativo (Forward-testing hasta el viernes)";
      }
      if (resetBtn) resetBtn.style.display = "inline-flex";
    }
  }

  // Header controls
  botStateLabel.textContent = isRunning ? "ACTIVO" : "PAUSADO";
  const dot = statusIndicator.querySelector(".dot");
  if (isRunning) {
    dot.className = "dot live";
    toggleBotBtn.textContent = "⏸️ Pausar";
    toggleBotBtn.className = "btn btn-secondary has-help";
  } else {
    dot.className = "dot paused";
    toggleBotBtn.textContent = "▶️ Reanudar";
    toggleBotBtn.className = "btn btn-primary has-help";
  }

  // Sincronizar casillas de configuración si no se están editando activamente
  if (data.config) {
    if (document.activeElement !== cfgOrderAmount) cfgOrderAmount.value = data.config.order_amount_eur ?? 5.0;
    if (document.activeElement !== cfgTakeProfit) cfgTakeProfit.value = data.config.take_profit_pct ?? 3.5;
    if (document.activeElement !== cfgStopLoss) cfgStopLoss.value = data.config.stop_loss_pct ?? -3.0;
    if (document.activeElement !== cfgRsiBuy) cfgRsiBuy.value = data.config.rsi_buy_threshold ?? 32;
    if (document.activeElement !== cfgRsiSell) cfgRsiSell.value = data.config.rsi_sell_threshold ?? 68;
    if (document.activeElement !== cfgSmaPeriod && cfgSmaPeriod) cfgSmaPeriod.value = data.config.sma_period ?? 50;
    if (document.activeElement !== cfgMsciSweep) cfgMsciSweep.value = data.config.msci_sweep_pct ?? 0;
  }

  // Actualizar cálculo dinámico del hint de compras escalonadas
  updateDcaMarginHint();

  // Category buttons
  document.querySelectorAll(".cat-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.category === currentCategory);
  });

  // Render symbol pills
  renderPills(marketsCatalog, currentCategory, currentSymbol);

  // KPIs Aislados por Entorno
  const p = (activeEnvironment === "live" && data.live) ? data.live : (data.simulation || data.portfolio);
  kpiTotalValue.textContent = formatEur(p.total_value_eur);

  const profitSign = p.net_profit_eur >= 0 ? "+" : "";
  const profitClass = p.net_profit_eur > 0 ? "text-green" : (p.net_profit_eur < 0 ? "text-red" : "neutral");
  kpiNetProfit.innerHTML = `P&L: <span class="${profitClass}">${profitSign}${formatEur(p.net_profit_eur)} (${profitSign}${p.net_profit_pct}%)</span>`;

  kpiCash.textContent = formatEur(p.cash_eur);
  kpiInPosition.textContent = `En posiciones: ${formatEur(p.positions_value_eur)}`;

  const rPnlClass = p.realized_pnl_eur > 0 ? "text-green" : (p.realized_pnl_eur < 0 ? "text-red" : "");
  kpiRealizedPnl.innerHTML = `<span class="${rPnlClass}">${profitSign}${formatEur(p.realized_pnl_eur)}</span>`;
  kpiFees.textContent = `Comisiones (0.1%): ${formatEur(p.total_fees_paid_eur)}`;

  kpiWinRate.textContent = `${p.win_rate_pct}%`;
  kpiTradesCount.textContent = `${p.closed_trades_count} cerradas (${p.total_trades_count} totales)`;

  // Bóveda MSCI World
  if (kpiMsciVault) {
    kpiMsciVault.textContent = formatEur(p.msci_vault_eur || 0);
  }
  if (kpiMsciSub) {
    kpiMsciSub.textContent = `Proyección 10a: ${formatEur(p.msci_proj_10yr || 0)}`;
  }

  // Market & Technicals
  const a = data.analysis;
  const meta = marketsCatalog[currentSymbol] || {};
  const assetName = meta.name ? `${meta.name} (${meta.symbol_clean || currentSymbol})` : currentSymbol;

  marketSymbolLabel.textContent = `${assetName} - Datos en Vivo`;
  marketPrice.textContent = formatEur(a.price || 0);

  const stats = a.stats_24h || {};
  const chg = stats.priceChangePercent || 0;
  const chgClass = chg >= 0 ? "positive" : "negative";
  marketChange24h.className = `change-pill ${chgClass}`;
  marketChange24h.textContent = `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}% (24h)`;

  // Decision
  const act = data.last_action || {};
  decisionDesc.textContent = act.reason || data.status_message;
  if (act.action === "BUY") {
    decisionBadge.className = "decision-badge buy";
    decisionBadge.textContent = "COMPRA";
  } else if (act.action === "SELL") {
    decisionBadge.className = "decision-badge sell";
    decisionBadge.textContent = "VENTA";
  } else {
    decisionBadge.className = "decision-badge hold";
    decisionBadge.textContent = "ESPERANDO";
  }

  // RSI Gauge
  const rsi = a.rsi || 50;
  rsiValue.textContent = rsi.toFixed(1);
  if (rsi <= 35) rsiValue.style.color = "var(--green)";
  else if (rsi >= 65) rsiValue.style.color = "var(--red)";
  else rsiValue.style.color = "var(--text-primary)";

  const clampedRsi = Math.max(0, Math.min(100, rsi));
  rsiNeedle.style.left = `${clampedRsi}%`;

  // Moving Averages, Bollinger & SMA Macro
  emaFast.textContent = formatEur(a.ema_fast || 0);
  emaSlow.textContent = formatEur(a.ema_slow || 0);
  bbUpper.textContent = formatEur(a.bb_upper || 0);
  bbLower.textContent = formatEur(a.bb_lower || 0);

  if (sma50) {
    const smaVal = a.sma_50 || a.ema_trend || 0;
    sma50.textContent = formatEur(smaVal);
    if (a.price >= smaVal) {
      sma50.style.color = "#4ade80"; // Sobre SMA: alcista
    } else if (a.price >= smaVal * 0.992) {
      sma50.style.color = "#38bdf8"; // Convergiendo
    } else {
      sma50.style.color = "#f87171"; // Caída libre bajo SMA
    }
  }

  // Positions Table (Aislada por Entorno)
  const posCount = Object.keys(p.positions || {}).length;
  positionsBadge.textContent = `${posCount} activa${posCount === 1 ? "" : "s"}`;

  if (!p.positions || p.positions.length === 0) {
    positionsTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No hay posiciones abiertas en este entorno</td></tr>`;
  } else {
    positionsTableBody.innerHTML = p.positions.map(pos => {
      const pnlSign = pos.unrealized_pnl_eur >= 0 ? "+" : "";
      const pnlClass = pos.unrealized_pnl_eur > 0 ? "text-green" : (pos.unrealized_pnl_eur < 0 ? "text-red" : "");
      const posMeta = marketsCatalog[pos.symbol] || {};
      const posName = posMeta.name || pos.symbol;
      return `
        <tr>
          <td><strong>${posName}</strong></td>
          <td>${formatCrypto(pos.amount)}</td>
          <td>${formatEur(pos.avg_entry_price)}</td>
          <td>${formatEur(pos.current_price)}</td>
          <td>${formatEur(pos.total_cost_eur)}</td>
          <td>${formatEur(pos.current_value_eur)}</td>
          <td class="${pnlClass}">${pnlSign}${formatEur(pos.unrealized_pnl_eur)} (${pnlSign}${pos.unrealized_pnl_pct}%)</td>
          <td><span class="dca-badge">Nivel ${pos.dca_count}</span></td>
        </tr>
      `;
    }).join("");
  }

  // Recent Trades Table (Filtradas Estrictamente por Entorno)
  const allTrades = p.recent_trades || [];
  let filteredTrades = allTrades;
  if (tradesFilter === "SELL") {
    filteredTrades = allTrades.filter(t => t.side === "SELL");
  }

  if (filteredTrades.length === 0) {
    tradesTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No hay operaciones registradas en ${activeEnvironment === "live" ? "Dinero Real" : "Simulación"}</td></tr>`;
  } else {
    tradesTableBody.innerHTML = filteredTrades.map(t => {
      const isBuy = t.side === "BUY";
      const sideLabel = isBuy ? "🟢 COMPRA" : "💰 VENTA";
      const badgeStyle = isBuy
        ? "background: rgba(59,130,246,0.18); color: #60a5fa; padding: 3px 7px; border-radius: 5px; font-weight: bold; font-size: 11px;"
        : "background: rgba(16,185,129,0.22); color: #10b981; padding: 3px 7px; border-radius: 5px; font-weight: bold; font-size: 11px;";
      const rowStyle = isBuy ? "" : "background: rgba(16, 185, 129, 0.05);";
      const pctSuffix = t.pnl_pct !== undefined ? ` (${t.pnl_pct >= 0 ? "+" : ""}${t.pnl_pct}%)` : "";
      const pnlText = isBuy
        ? "En curso"
        : (t.realized_pnl_eur >= 0 ? `✅ +${formatEur(t.realized_pnl_eur)}${pctSuffix}` : `🛑 ${formatEur(t.realized_pnl_eur)}${pctSuffix}`);
      const pnlClass = isBuy ? "text-muted" : (t.realized_pnl_eur >= 0 ? "text-green font-bold" : "text-red font-bold");
      const tMeta = marketsCatalog[t.symbol] || {};
      const tName = tMeta.name || t.symbol;
      return `
        <tr style="${rowStyle}">
          <td class="text-muted">${t.timestamp.split(" ")[1] || t.timestamp}</td>
          <td><span style="${badgeStyle}">${sideLabel}</span></td>
          <td><strong>${tName}</strong></td>
          <td>${formatEur(t.price)}</td>
          <td>${formatEur(t.amount_eur)}</td>
          <td class="text-muted">${formatEur(t.fee_eur)}</td>
          <td class="${pnlClass}">${pnlText}</td>
          <td class="text-muted" style="max-width: 260px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${t.reason}">${t.reason}</td>
        </tr>
      `;
    }).join("");
  }

  // Logs terminal
  if (data.logs && data.logs.length > 0) {
    terminalLogs.innerHTML = data.logs.map(line => {
      let color = "#94a3b8";
      if (line.includes("COMPRA EJECUTADA") || line.includes("COMPRA REAL")) color = "#10b981";
      if (line.includes("VENTA EJECUTADA") || line.includes("VENTA REAL")) color = "#f59e0b";
      if (line.includes("Error") || line.includes("🚨")) color = "#ef4444";
      return `<div class="log-line" style="color: ${color};">${line}</div>`;
    }).join("");
  }
  lastTickTime.textContent = new Date().toLocaleTimeString();
}

// Category tabs click
const filterAllTradesBtn = document.getElementById("filterAllTradesBtn");
const filterSellTradesBtn = document.getElementById("filterSellTradesBtn");

if (filterAllTradesBtn && filterSellTradesBtn) {
  filterAllTradesBtn.addEventListener("click", () => {
    tradesFilter = "ALL";
    filterAllTradesBtn.className = "btn btn-primary btn-sm";
    filterSellTradesBtn.className = "btn btn-secondary btn-sm";
    fetchState();
  });
  filterSellTradesBtn.addEventListener("click", () => {
    tradesFilter = "SELL";
    filterSellTradesBtn.className = "btn btn-primary btn-sm";
    filterAllTradesBtn.className = "btn btn-secondary btn-sm";
    fetchState();
  });
}

document.querySelectorAll(".cat-btn").forEach(btn => {
  btn.addEventListener("click", async () => {
    const category = btn.dataset.category;
    await fetch("/static/api/category", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category })
    });
    fetchState();
  });
});

toggleBotBtn.addEventListener("click", async () => {
  await fetch("/static/api/toggle", { method: "POST" });
  fetchState();
});

emergencyBtn.addEventListener("click", async () => {
  if (confirm("¿Estás seguro de que deseas vender inmediatamente todas las posiciones al precio actual de mercado?")) {
    await fetch("/static/api/emergency_sell", { method: "POST" });
    fetchState();
  }
});

resetBtn.addEventListener("click", async () => {
  if (confirm("¿Deseas reiniciar la cartera virtual a los 15 € iniciales?")) {
    await fetch("/static/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ capital: 15.0 })
    });
    fetchState();
  }
});

saveConfigBtn.addEventListener("click", async () => {
  const payload = {
    order_amount_eur: parseFloat(cfgOrderAmount.value),
    take_profit_pct: parseFloat(cfgTakeProfit.value),
    stop_loss_pct: parseFloat(cfgStopLoss.value),
    rsi_buy_threshold: parseFloat(cfgRsiBuy.value),
    rsi_sell_threshold: parseFloat(cfgRsiSell.value),
    sma_period: parseFloat(cfgSmaPeriod ? cfgSmaPeriod.value : 50),
    msci_sweep_pct: parseFloat(cfgMsciSweep.value)
  };
  const res = await fetch("/static/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (res.ok) {
    alert("✅ Parámetros de la estrategia guardados correctamente.");
    fetchState();
  }
});

if (cfgOrderAmount) {
  cfgOrderAmount.addEventListener("input", updateDcaMarginHint);
}

// Interactive Educational Tooltip Engine con retraso de 2 segundos
const globalTooltip = document.getElementById("globalTooltip");
let tooltipTimer = null;
let currentHoveredTarget = null;
let lastMouseEvent = null;

function setupTooltips() {
  document.addEventListener("mouseover", (e) => {
    const target = e.target.closest("[data-tooltip]");
    if (!target) {
      clearTimeout(tooltipTimer);
      globalTooltip.classList.remove("visible");
      currentHoveredTarget = null;
      return;
    }

    if (target === currentHoveredTarget) return;

    clearTimeout(tooltipTimer);
    globalTooltip.classList.remove("visible");
    currentHoveredTarget = target;
    lastMouseEvent = e;

    const title = target.getAttribute("data-tooltip-title") || "";
    const text = target.getAttribute("data-tooltip") || "";
    if (!text) return;

    tooltipTimer = setTimeout(() => {
      if (currentHoveredTarget === target) {
        const titleHtml = title ? `<span class="tooltip-title">💡 ${title}</span>` : "";
        globalTooltip.innerHTML = `${titleHtml}<div>${text}</div>`;
        globalTooltip.classList.add("visible");
        if (lastMouseEvent) {
          positionTooltip(lastMouseEvent);
        }
      }
    }, 2000);
  });

  document.addEventListener("mousemove", (e) => {
    lastMouseEvent = e;
    if (globalTooltip.classList.contains("visible")) {
      positionTooltip(e);
    }
  });

  document.addEventListener("mouseout", (e) => {
    const target = e.target.closest("[data-tooltip]");
    if (!target) return;

    const related = e.relatedTarget;
    if (!target.contains(related)) {
      clearTimeout(tooltipTimer);
      globalTooltip.classList.remove("visible");
      currentHoveredTarget = null;
    }
  });
}

function positionTooltip(e) {
  const tooltipWidth = globalTooltip.offsetWidth || 260;
  const tooltipHeight = globalTooltip.offsetHeight || 80;
  const padding = 15;

  let left = e.clientX + padding;
  let top = e.clientY + padding;

  if (left + tooltipWidth > window.innerWidth - 10) {
    left = e.clientX - tooltipWidth - padding;
  }

  if (top + tooltipHeight > window.innerHeight - 10) {
    top = e.clientY - tooltipHeight - padding;
  }

  globalTooltip.style.left = `${Math.max(10, left)}px`;
  globalTooltip.style.top = `${Math.max(10, top)}px`;
}

setupTooltips();


if (tabSimBtn) tabSimBtn.addEventListener("click", () => window.setEnvironment("simulation"));
if (tabLiveBtn) tabLiveBtn.addEventListener("click", () => window.setEnvironment("live"));
if (liveArmToggleBtn) liveArmToggleBtn.addEventListener("click", () => window.toggleLiveArmed());

// Loop
fetchState();

setInterval(fetchState, 3000);
