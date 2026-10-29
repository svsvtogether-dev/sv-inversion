let currentSymbol = "BTCEUR";
let currentCategory = "all";
let isRunning = true;
let marketsCatalog = {};
let configInitialized = false;
let tradesFilter = "ALL"; // "ALL" | "SELL"

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

// Form inputs
const cfgOrderAmount = document.getElementById("cfgOrderAmount");
const cfgTakeProfit = document.getElementById("cfgTakeProfit");
const cfgStopLoss = document.getElementById("cfgStopLoss");
const cfgRsiBuy = document.getElementById("cfgRsiBuy");
const cfgRsiSell = document.getElementById("cfgRsiSell");
const cfgMsciSweep = document.getElementById("cfgMsciSweep");

const kpiMsciVault = document.getElementById("kpiMsciVault");
const kpiMsciSub = document.getElementById("kpiMsciSub");

function formatEur(val) {
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(val);
}

function formatCrypto(val) {
  if (val === 0) return "0";
  if (val < 0.001) return val.toFixed(6);
  return val.toFixed(4);
}

// Fetch bot state
async function fetchState() {
  try {
    const res = await fetch("/api/status");
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
    if (activeCat !== "all" && meta.category !== activeCat) continue;

    const btn = document.createElement("button");
    btn.className = `pill-btn ${sym === activeSym ? "active" : ""}`;
    btn.dataset.symbol = sym;
    btn.innerHTML = `
      <span>${meta.name}</span>
      <span class="pill-tag">${meta.symbol_clean || sym}</span>
    `;
    btn.addEventListener("click", async () => {
      await fetch("/api/symbol", {
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
  currentSymbol = data.current_symbol;
  currentCategory = data.active_category || "all";
  isRunning = data.is_running;
  marketsCatalog = data.markets_catalog || {};

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
    if (document.activeElement !== cfgOrderAmount) cfgOrderAmount.value = data.config.order_amount_eur ?? 25.0;
    if (document.activeElement !== cfgTakeProfit) cfgTakeProfit.value = data.config.take_profit_pct ?? 4.5;
    if (document.activeElement !== cfgStopLoss) cfgStopLoss.value = data.config.stop_loss_pct ?? -3.5;
    if (document.activeElement !== cfgRsiBuy) cfgRsiBuy.value = data.config.rsi_buy_threshold ?? 35;
    if (document.activeElement !== cfgRsiSell) cfgRsiSell.value = data.config.rsi_sell_threshold ?? 65;
    if (document.activeElement !== cfgMsciSweep) cfgMsciSweep.value = data.config.msci_sweep_pct ?? 0;
  }

  // Category buttons
  document.querySelectorAll(".cat-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.category === currentCategory);
  });

  // Render symbol pills
  renderPills(marketsCatalog, currentCategory, currentSymbol);

  // KPIs
  const p = data.portfolio;
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
  rsiNeedle.style.left = `${Math.min(100, Math.max(0, rsi))}%`;

  // Indicators
  emaFast.textContent = a.ema_fast ? formatEur(a.ema_fast) : "€--";
  emaSlow.textContent = a.ema_slow ? formatEur(a.ema_slow) : "€--";
  bbUpper.textContent = a.bb_upper ? formatEur(a.bb_upper) : "€--";
  bbLower.textContent = a.bb_lower ? formatEur(a.bb_lower) : "€--";

  // Positions Table
  positionsBadge.textContent = `${p.positions.length} abiertas`;
  if (p.positions.length === 0) {
    positionsTableBody.innerHTML = `<tr><td colspan="8" class="text-center empty-state">Sin posiciones abiertas. El bot comprará automáticamente cuando detecte una oportunidad de descuento o sobreventa.</td></tr>`;
  } else {
    positionsTableBody.innerHTML = p.positions.map(pos => {
      const pnlSign = pos.unrealized_pnl_eur >= 0 ? "+" : "";
      const pnlClass = pos.unrealized_pnl_eur >= 0 ? "text-green" : "text-red";
      const pMeta = marketsCatalog[pos.symbol] || {};
      const posName = pMeta.name || pos.symbol;
      return `
        <tr>
          <td><strong>${posName}</strong> <small class="text-muted">${pos.symbol}</small></td>
          <td>${formatCrypto(pos.amount)}</td>
          <td>${formatEur(pos.avg_entry_price)}</td>
          <td>${formatEur(pos.current_price)}</td>
          <td>${formatEur(pos.total_cost_eur)}</td>
          <td>${formatEur(pos.current_value_eur)}</td>
          <td class="${pnlClass}"><strong>${pnlSign}${formatEur(pos.unrealized_pnl_eur)} (${pnlSign}${pos.unrealized_pnl_pct}%)</strong></td>
          <td>${pos.dca_count} / 3</td>
        </tr>
      `;
    }).join("");
  }

  // Recent Trades Table
  const allTrades = p.recent_trades || [];
  const filteredTrades = tradesFilter === "SELL" ? allTrades.filter(t => t.side === "SELL") : allTrades;

  if (filteredTrades.length === 0) {
    tradesTableBody.innerHTML = `<tr><td colspan="8" class="text-center empty-state">Aún no hay operaciones registradas en esta vista.</td></tr>`;
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
      if (line.includes("COMPRA EJECUTADA")) color = "#10b981";
      if (line.includes("VENTA EJECUTADA")) color = "#f59e0b";
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
    await fetch("/api/category", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category })
    });
    fetchState();
  });
});

toggleBotBtn.addEventListener("click", async () => {
  await fetch("/api/toggle", { method: "POST" });
  fetchState();
});

emergencyBtn.addEventListener("click", async () => {
  if (confirm("¿Estás seguro de que deseas vender inmediatamente todas las posiciones al precio actual de mercado?")) {
    await fetch("/api/emergency_sell", { method: "POST" });
    fetchState();
  }
});

resetBtn.addEventListener("click", async () => {
  if (confirm("¿Deseas reiniciar la cartera virtual a los 250 € iniciales?")) {
    await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ capital: 250.0 })
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
    msci_sweep_pct: parseFloat(cfgMsciSweep.value)
  };
  const res = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (res.ok) {
    alert("✅ Parámetros de la estrategia guardados correctamente.");
    fetchState();
  }
});

// Interactive Educational Tooltip Engine con retraso intencional de 2 segundos
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

    // Cancelar cualquier temporizador previo
    clearTimeout(tooltipTimer);
    globalTooltip.classList.remove("visible");
    currentHoveredTarget = target;
    lastMouseEvent = e;

    const title = target.getAttribute("data-tooltip-title") || "";
    const text = target.getAttribute("data-tooltip") || "";
    if (!text) return;

    // Solo mostrar si el usuario mantiene el puntero quieto durante 2 segundos (2000 ms)
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

    // Comprobar si el cursor realmente salió del contenedor
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

  // Ajustar si se sale por la derecha
  if (left + tooltipWidth > window.innerWidth - 10) {
    left = e.clientX - tooltipWidth - padding;
  }

  // Ajustar si se sale por abajo
  if (top + tooltipHeight > window.innerHeight - 10) {
    top = e.clientY - tooltipHeight - padding;
  }

  globalTooltip.style.left = `${Math.max(10, left)}px`;
  globalTooltip.style.top = `${Math.max(10, top)}px`;
}

setupTooltips();

// Loop
fetchState();
setInterval(fetchState, 3000);
