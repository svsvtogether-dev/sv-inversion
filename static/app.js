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
const hma50 = document.getElementById("hma50");
const sessionLiquidityBadge = document.getElementById("sessionLiquidityBadge");
const kronosOracleBadge = document.getElementById("kronosOracleBadge");
const bbUpper = document.getElementById("bbUpper");
const bbLower = document.getElementById("bbLower");
const atrVal = document.getElementById("atrVal");

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
const quickBtnBNB = document.getElementById("quickBtnBNB");
const quickBtnSOL = document.getElementById("quickBtnSOL");

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
  const cash = p ? (p.cash_eur ?? 50.0) : 50.0;
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
  if (quickBtnBNB) quickBtnBNB.classList.toggle("active", activeSym === "BNBEUR");
  if (quickBtnSOL) quickBtnSOL.classList.toggle("active", activeSym === "SOLEUR");
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
      headerEnvBadge.textContent = "🧪 SIMULACIÓN 50 €";
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
    if (activeCat !== "all" && meta.category !== activeCat && meta.sub_category !== activeCat && !(activeCat === "top" && meta.sub_category === "top4")) continue;

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
  renderAutomaton(data.automaton);

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
        headerEnvBadge.textContent = "🧪 SIMULACIÓN 50 €";
        headerEnvBadge.className = "badge paper";
      }
      if (headerSubtitle) {
        headerSubtitle.textContent = "100% de la gestión, capital, estrategia y supervivencia a cargo de Conway Automaton";
      }
      if (resetBtn) resetBtn.style.display = "inline-flex";
    }
  }

  // Header controls & Automaton status
  const auto = data.automaton || {};
  if (!auto.is_alive) {
    botStateLabel.textContent = "AUTOMATON: APAGADO (DEAD)";
    statusIndicator.querySelector(".dot").className = "dot paused";
  } else if (isRunning) {
    botStateLabel.textContent = `AUTOMATON: ACTIVO (${auto.tier || "NORMAL"})`;
    statusIndicator.querySelector(".dot").className = "dot live";
  } else {
    botStateLabel.textContent = "AUTOMATON: EN PAUSA";
    statusIndicator.querySelector(".dot").className = "dot paused";
  }

  if (isRunning) {
    toggleBotBtn.textContent = "⏸️ Pausar";
    toggleBotBtn.className = "btn btn-secondary has-help";
  } else {
    toggleBotBtn.textContent = "▶️ Reanudar";
    toggleBotBtn.className = "btn btn-primary has-help";
  }

  // Radar de Convicción Automaton para Top 4
  const scores = auto.candidate_scores || {};
  const minReq = auto.min_score_required || 60;
  const radarMinReqBadge = document.getElementById("radarMinReqBadge");
  if (radarMinReqBadge) radarMinReqBadge.textContent = `${minReq} pts`;

  const setConvBadge = (id, sc, sym) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (sc != null) {
      if (sc >= minReq) {
        el.className = "conviction-badge high";
        el.textContent = `${sc} pts ✅`;
      } else if (auto.best_candidate === sym) {
        el.className = "conviction-badge radar";
        el.textContent = `${sc} pts ⭐ Radar`;
      } else {
        el.className = "conviction-badge";
        el.textContent = `${sc} pts`;
      }
    } else {
      el.textContent = "-- pts";
      el.className = "conviction-badge";
    }
  };

  setConvBadge("convictionBTC", scores["BTCEUR"], "BTCEUR");
  setConvBadge("convictionETH", scores["ETHEUR"], "ETHEUR");
  setConvBadge("convictionBNB", scores["BNBEUR"], "BNBEUR");
  setConvBadge("convictionSOL", scores["SOLEUR"], "SOLEUR");

  // Sincronizar casillas de configuración si existen en el DOM
  if (data.config && cfgOrderAmount) {
    if (document.activeElement !== cfgOrderAmount) cfgOrderAmount.value = data.config.order_amount_eur ?? 5.0;
    if (cfgTakeProfit && document.activeElement !== cfgTakeProfit) cfgTakeProfit.value = data.config.take_profit_pct ?? 3.5;
    if (cfgStopLoss && document.activeElement !== cfgStopLoss) cfgStopLoss.value = data.config.stop_loss_pct ?? -3.0;
    if (cfgRsiBuy && document.activeElement !== cfgRsiBuy) cfgRsiBuy.value = data.config.rsi_buy_threshold ?? 32;
    if (cfgRsiSell && document.activeElement !== cfgRsiSell) cfgRsiSell.value = data.config.rsi_sell_threshold ?? 68;
    if (cfgSmaPeriod && document.activeElement !== cfgSmaPeriod) cfgSmaPeriod.value = data.config.sma_period ?? 50;
    if (cfgMsciSweep && document.activeElement !== cfgMsciSweep) cfgMsciSweep.value = data.config.msci_sweep_pct ?? 0;
  }

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
  
  const lifeContributed = document.getElementById("kpiLifeContributed");
  if (lifeContributed) {
    lifeContributed.textContent = `+${formatEur(auto.total_earned_eur || auto.total_earned_usd || 0)}`;
  } else {
    kpiFees.textContent = `Comisiones (0.1%): ${formatEur(p.total_fees_paid_eur)}`;
  }

  kpiWinRate.textContent = `${p.win_rate_pct}%`;
  kpiTradesCount.textContent = `${p.closed_trades_count} cerradas (${p.total_trades_count} totales)`;

  // Saldo Vital Automaton & Bóveda (Unificado al 100% con los 50 € de inversión)
  const kpiVitalTreasury = document.getElementById("kpiVitalTreasury");
  if (kpiVitalTreasury) {
    kpiVitalTreasury.textContent = formatEur(auto.treasury_eur || p.total_value_eur || 50.0);
    kpiVitalTreasury.style.color = auto.tier === "DEAD" ? "#ef4444" : (auto.tier === "CRITICAL" ? "#f87171" : "#4ade80");
  }
  if (kpiMsciSub) {
    kpiMsciSub.textContent = `Bóveda MSCI: ${formatEur(p.msci_vault_eur || 0)} • Tier: ${auto.tier || 'NORMAL'}`;
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

  if (atrVal) {
    const atr = a.atr || 0;
    const atrPct = a.atr_pct || 0;
    atrVal.textContent = `${formatEur(atr)} (±${atrPct}%)`;
  }

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

  if (hma50) {
    const hmaVal = a.hma_50 || a.price || 0;
    const slope = a.hma_50_slope || "FLAT";
    const slopeIcon = slope === "UP" ? "🟢" : (slope === "DOWN" ? "🔴" : "⚪");
    hma50.textContent = `${formatEur(hmaVal)} ${slopeIcon}`;
    if (slope === "UP") {
      hma50.style.color = "#4ade80";
    } else if (slope === "DOWN") {
      hma50.style.color = "#f87171";
    } else {
      hma50.style.color = "#94a3b8";
    }
  }

  if (sessionLiquidityBadge) {
    const sInfo = a.session_info || {};
    if (sInfo.is_institutional_window) {
      sessionLiquidityBadge.textContent = `🏛️ NY/Londres (${sInfo.utc_time})`;
      sessionLiquidityBadge.style.color = "#4ade80";
    } else if (sInfo.liquidity_tier === "LOW") {
      sessionLiquidityBadge.textContent = `🌙 Nocturna (${sInfo.utc_time || "--"})`;
      sessionLiquidityBadge.style.color = "#fbbf24";
    } else {
      sessionLiquidityBadge.textContent = `🌐 Regular (${sInfo.utc_time || "--"})`;
      sessionLiquidityBadge.style.color = "#38bdf8";
    }
  }

  if (kronosOracleBadge) {
    const k = a.kronos || {};
    const prob = k.bullish_prob !== undefined ? k.bullish_prob : 50;
    const expRet = k.expected_return_pct !== undefined ? k.expected_return_pct : 0.0;
    const sign = expRet >= 0 ? "+" : "";
    if (k.verdict === "BULLISH_BIAS") {
      kronosOracleBadge.textContent = `🔮 ${prob}% Alcista (${sign}${expRet}%)`;
      kronosOracleBadge.style.color = "#4ade80";
    } else if (k.verdict === "BEARISH_BIAS") {
      kronosOracleBadge.textContent = `⚠️ ${Math.round(100 - prob)}% Bajista (${sign}${expRet}%)`;
      kronosOracleBadge.style.color = "#f87171";
    } else {
      kronosOracleBadge.textContent = `⚖️ Neutral (${prob}%)`;
      kronosOracleBadge.style.color = "#c084fc";
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
      const tpTarget = (pos.avg_entry_price * (1 + (auto.target_tp_pct || 3.5) / 100));
      return `
        <tr>
          <td>
            <strong>${posName}</strong><br/>
            <span class="sovereign-tag" style="font-size: 9px; padding: 1px 5px;">🤖 Gestionado por Automaton</span>
          </td>
          <td>${formatCrypto(pos.amount)}</td>
          <td>${formatEur(pos.avg_entry_price)}</td>
          <td>${formatEur(pos.current_price)}</td>
          <td>${formatEur(pos.total_cost_eur)}</td>
          <td>${formatEur(pos.current_value_eur)}</td>
          <td class="${pnlClass}">
            ${pnlSign}${formatEur(pos.unrealized_pnl_eur)} (${pnlSign}${pos.unrealized_pnl_pct}%)<br/>
            <small style="color: #38bdf8;">Meta TP: +${(auto.target_tp_pct || 3.5)}% (${formatEur(tpTarget)})</small>
          </td>
          <td>
            <span class="dca-badge">DCA ${pos.dca_count}/3</span><br/>
            <small style="color: #34d399;">Riesgo Protegido</small>
          </td>
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
  if (confirm("¿Deseas reiniciar la cartera virtual a los 50 € iniciales?")) {
    await fetch("/static/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ capital: 50.0 })
    });
    fetchState();
  }
});

if (saveConfigBtn) {
  saveConfigBtn.addEventListener("click", async () => {
    const payload = {
      order_amount_eur: parseFloat(cfgOrderAmount ? cfgOrderAmount.value : 5.0),
      take_profit_pct: parseFloat(cfgTakeProfit ? cfgTakeProfit.value : 3.5),
      stop_loss_pct: parseFloat(cfgStopLoss ? cfgStopLoss.value : -3.0),
      rsi_buy_threshold: parseFloat(cfgRsiBuy ? cfgRsiBuy.value : 32),
      rsi_sell_threshold: parseFloat(cfgRsiSell ? cfgRsiSell.value : 68),
      sma_period: parseFloat(cfgSmaPeriod ? cfgSmaPeriod.value : 50),
      msci_sweep_pct: parseFloat(cfgMsciSweep ? cfgMsciSweep.value : 0)
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
}

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

// Render Conway Automaton Sovereign AI State
function renderAutomaton(auto) {
  if (!auto) return;
  const tierBadge = document.getElementById("automatonTierBadge");
  const pulseDot = document.getElementById("automatonPulseDot");
  const batteryFill = document.getElementById("automatonBatteryFill");
  const treasuryVal = document.getElementById("automatonTreasuryVal");
  const burnRateVal = document.getElementById("automatonBurnRateVal");
  const walletAddr = document.getElementById("automatonWalletAddress");
  const earnedVal = document.getElementById("automatonEarnedVal");
  const cyclesVal = document.getElementById("automatonCyclesVal");
  const thoughtText = document.getElementById("automatonThoughtText");
  const thoughtTime = document.getElementById("automatonThoughtTime");
  const reviveBtn = document.getElementById("reviveAutomatonBtn");
  const fundBtn = document.getElementById("fundAutomatonBtn");

  const tier = auto.tier || "NORMAL";
  if (tierBadge) {
    tierBadge.textContent = `TIER ${tier.replace('_', ' ')}`;
    tierBadge.className = `tier-pill tier-${tier.toLowerCase().replace('_', '-')}`;
  }

  if (pulseDot) {
    pulseDot.className = `automaton-pulse-dot ${auto.is_alive ? '' : 'dead'}`;
  }

  if (batteryFill) {
    const pct = auto.battery_pct != null ? auto.battery_pct : 100;
    batteryFill.style.width = `${pct}%`;
    if (tier === "DEAD") {
      batteryFill.style.background = "#ef4444";
    } else if (tier === "CRITICAL") {
      batteryFill.style.background = "linear-gradient(90deg, #ef4444 0%, #f97316 100%)";
    } else if (tier === "LOW_COMPUTE") {
      batteryFill.style.background = "linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%)";
    } else {
      batteryFill.style.background = "linear-gradient(90deg, #10b981 0%, #34d399 100%)";
    }
  }

  if (treasuryVal) {
    treasuryVal.textContent = formatEur(auto.treasury_eur || auto.treasury_usd || 50.0);
    treasuryVal.style.color = tier === "DEAD" ? "#ef4444" : (tier === "CRITICAL" ? "#f87171" : (tier === "LOW_COMPUTE" ? "#fbbf24" : "#4ade80"));
  }

  if (burnRateVal) {
    burnRateVal.textContent = `Salud: ${Math.round(auto.battery_pct != null ? auto.battery_pct : 100)}% (${tier})`;
  }

  if (walletAddr && auto.wallet_address) {
    const w = auto.wallet_address;
    walletAddr.textContent = `${w.slice(0, 6)}...${w.slice(-4)}`;
    walletAddr.title = w;
  }

  if (earnedVal) {
    earnedVal.textContent = `Ganancias vida: +${formatEur(auto.total_earned_eur || auto.total_earned_usd || 0)}`;
  }

  if (cyclesVal) {
    cyclesVal.textContent = `Ciclos: #${auto.cycle_count || 0}`;
  }

  if (thoughtText && auto.last_thought) {
    thoughtText.textContent = auto.last_thought;
  }

  if (thoughtTime) {
    thoughtTime.textContent = new Date().toLocaleTimeString();
  }

  // Actualizar criterios auto-calibrados por Automaton
  const autoRiskLevel = document.getElementById("autoRiskLevel");
  const autoRiskHint = document.getElementById("autoRiskHint");
  const autoTakeProfit = document.getElementById("autoTakeProfit");
  const autoStopLoss = document.getElementById("autoStopLoss");
  const autoMinScore = document.getElementById("autoMinScore");
  const autoScoreHint = document.getElementById("autoScoreHint");
  const autoDcaStatus = document.getElementById("autoDcaStatus");

  if (autoRiskLevel) {
    if (tier === "DEAD") {
      autoRiskLevel.textContent = "INACTIVO (Muerto)";
      autoRiskLevel.style.color = "#ef4444";
      if (autoRiskHint) autoRiskHint.textContent = "La IA está apagada. No se realizan operaciones.";
    } else if (tier === "CRITICAL") {
      autoRiskLevel.textContent = "EXTREMO / ULTRA-DEFENSIVO";
      autoRiskLevel.style.color = "#f87171";
      if (autoRiskHint) autoRiskHint.textContent = "Batería baja. Solo acepta operaciones de convicción > 88 pts.";
    } else if (tier === "LOW_COMPUTE") {
      autoRiskLevel.textContent = "ALTO / CONSERVADOR";
      autoRiskLevel.style.color = "#fbbf24";
      if (autoRiskHint) autoRiskHint.textContent = "Modo conservación activo. Convicción mínima requerida: 75 pts.";
    } else {
      autoRiskLevel.textContent = "MODERADO (Tier Normal)";
      autoRiskLevel.style.color = "#4ade80";
      if (autoRiskHint) autoRiskHint.textContent = "Capacidad de cálculo plena y búsqueda activa de oportunidades.";
    }
  }

  if (autoTakeProfit) {
    if (tier === "CRITICAL") {
      autoTakeProfit.textContent = "+1.5% (Toma rápida de supervivencia)";
      autoTakeProfit.style.color = "#f87171";
    } else if (tier === "LOW_COMPUTE") {
      autoTakeProfit.textContent = "+2.2% (Toma prudente)";
      autoTakeProfit.style.color = "#fbbf24";
    } else {
      autoTakeProfit.textContent = "+3.5% (Objetivo óptimo)";
      autoTakeProfit.style.color = "#38bdf8";
    }
  }

  if (autoStopLoss) {
    if (tier === "CRITICAL") {
      autoStopLoss.textContent = "-2.0% (Corte de emergencia anticipado)";
    } else {
      autoStopLoss.textContent = "-3.0% (Protección estricta)";
    }
  }

  if (autoMinScore) {
    const scoreReq = tier === "CRITICAL" ? "88 / 100 pts" : (tier === "LOW_COMPUTE" ? "75 / 100 pts" : "60 / 100 pts");
    autoMinScore.textContent = scoreReq;
    if (autoScoreHint) {
      autoScoreHint.textContent = tier === "CRITICAL" ? "Solo setups con ventaja estadística casi garantizada." : "Filtro cuantitativo adaptativo.";
    }
  }

  if (autoDcaStatus) {
    if (tier === "CRITICAL" || tier === "DEAD") {
      autoDcaStatus.textContent = "BLOQUEADA (Preservación de capital)";
      autoDcaStatus.style.color = "#ef4444";
    } else {
      autoDcaStatus.textContent = "HABILITADA (Hasta 3 escalones)";
      autoDcaStatus.style.color = "#34d399";
    }
  }

  const autoCircuitBreaker = document.getElementById("autoCircuitBreaker");
  const autoCircuitHint = document.getElementById("autoCircuitHint");
  const cb = auto.circuit_breaker || {};
  if (autoCircuitBreaker) {
    if (cb.active) {
      autoCircuitBreaker.textContent = "🛑 DISPARADO (Compras Pausadas)";
      autoCircuitBreaker.style.color = "#ef4444";
      if (autoCircuitHint) autoCircuitHint.textContent = `Límite diario alcanzado (-€${Math.abs(cb.daily_realized_pnl_eur || 0).toFixed(2)}). Preservando capital.`;
    } else {
      const dailyLoss = cb.daily_realized_pnl_eur || 0;
      autoCircuitBreaker.textContent = `ARMADO (-${(cb.max_daily_loss_eur || 1.5).toFixed(2)} € máx)`;
      autoCircuitBreaker.style.color = "#4ade80";
      if (autoCircuitHint) {
        autoCircuitHint.textContent = `P&L hoy: ${dailyLoss >= 0 ? '+' : ''}€${dailyLoss.toFixed(2)}. Operativa autorizada.`;
      }
    }
  }

  if (reviveBtn) {
    reviveBtn.style.display = auto.is_alive ? "none" : "inline-flex";
  }
}

window.fundAutomaton = async function(amount = 5.0) {
  try {
    const res = await fetch("/static/api/automaton/fund", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount })
    });
    fetchState();
  } catch (err) {
    console.error("Error al recargar Automaton:", err);
  }
};

window.reviveAutomaton = async function() {
  try {
    const res = await fetch("/static/api/automaton/revive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grant: 3.0 })
    });
    fetchState();
  } catch (err) {
    console.error("Error al revivir Automaton:", err);
  }
};

// Loop
fetchState();

setInterval(fetchState, 3000);
