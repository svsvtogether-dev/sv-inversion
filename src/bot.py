import sys
import json
import uuid
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Garantizar compatibilidad con caracteres UTF-8 en consolas de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .config import (
    CONFIG,
    SUPPORTED_SYMBOLS,
    TOP4_SYMBOLS,
    MARKETS_CATALOG,
    DATA_DIR,
    FROZEN_EXPERIMENT,
    FROZEN_CONFIG_HASH,
    verify_frozen_config,
)
from .market_data import MarketDataFeed
from .portfolio import Portfolio
from .binance_client import BinanceSpotClient
from .binance_rules import BinanceRulesEngine
from .automaton_brain import AutomatonBrain
from .experiment_tracker import ExperimentTracker

class TradingBot:
    def __init__(self, config: Dict = None):
        self.config = config or CONFIG.copy()
        self.feed = MarketDataFeed()

        # Portafolios 100% aislados por entorno
        self.sim_portfolio = Portfolio(storage_path=DATA_DIR / "portfolio.json", environment="simulation")
        self.live_portfolio = Portfolio(storage_path=DATA_DIR / "portfolio_live.json", environment="live", initial_capital=0.0)

        # Experimento congelado v1.0-frozen: cerrojo inmutable de dinero real
        self.frozen_hash = verify_frozen_config()
        self.experiment = ExperimentTracker(DATA_DIR)

        # Entorno activo bloqueado en Simulación
        self.active_environment = "simulation"
        self.live_trading_armed = False
        self.binance_client = BinanceSpotClient()

        # Cerebro soberano de inversión Conway Automaton
        self.automaton = AutomatonBrain(DATA_DIR)

        self.is_running = True
        self.current_symbol = self.config.get("symbol", "BTCEUR")
        self.active_category = self.config.get("active_category", "all")
        self.status_message = "Iniciando motor universal multi-mercado..."
        self.last_analysis: Dict = {}
        self.last_action: Dict = {"action": "HOLD", "reason": "Iniciando", "time": ""}
        self.logs: List[str] = []
        self.iteration_count = 0

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.manual_orders_file = DATA_DIR / "manual_orders.json"
        self.pending_orders: List[Dict] = self._load_manual_orders()

    @property
    def portfolio(self) -> Portfolio:
        """Devuelve el portafolio correspondiente al entorno activo."""
        return self.live_portfolio if self.active_environment == "live" else self.sim_portfolio

    def set_environment(self, env: str):
        """Bloqueado en experimento congelado v1.0-frozen: siempre simulación."""
        with self._lock:
            self.active_environment = "simulation"
            self.live_trading_armed = False
            if env == "live":
                self.log("🔒 BLOQUEADO: modo REAL deshabilitado en experimento congelado v1.0-frozen.")
            else:
                self.log("🔄 Entorno: SIMULACIÓN (v1.0-frozen)")

    def set_live_armed(self, armed: bool):
        """Bloqueado en experimento congelado v1.0-frozen: live_armed siempre False."""
        with self._lock:
            self.live_trading_armed = False
            if armed:
                self.log("🔒 BLOQUEADO: live_armed=False forzado por código en v1.0-frozen.")

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = "[REAL]" if self.active_environment == "live" else "[SIM]"
        entry = f"[{timestamp}] {tag} {message}"
        self.logs.insert(0, entry)
        if len(self.logs) > 60:
            self.logs.pop()
        print(entry)

    def set_symbol(self, symbol: str):
        if symbol in SUPPORTED_SYMBOLS:
            cached = self.feed.last_analysis_cache.get(symbol)
            with self._lock:
                self.current_symbol = symbol
                self.config["symbol"] = symbol
                if cached and cached.get("price", 0) > 0:
                    self.last_analysis = cached
                meta = MARKETS_CATALOG.get(symbol, {})
                name = meta.get("name", symbol)
                self.log(f"Activo seleccionado: {name} ({symbol})")

            analysis = self.feed.analyze_symbol(symbol)
            if analysis.get("price", 0) > 0:
                with self._lock:
                    if self.current_symbol == symbol:
                        self.last_analysis = analysis

    def set_category(self, category: str):
        with self._lock:
            self.active_category = category
            self.config["active_category"] = category
            candidates = self.get_candidate_symbols()
            new_sym = None
            if candidates and self.current_symbol not in candidates:
                new_sym = candidates[0]
                self.current_symbol = new_sym
                self.config["symbol"] = new_sym
                cached = self.feed.last_analysis_cache.get(new_sym)
                if cached and cached.get("price", 0) > 0:
                    self.last_analysis = cached
            self.log(f"Filtro de mercado cambiado a: {category.upper()}")

        if new_sym:
            analysis = self.feed.analyze_symbol(new_sym)
            if analysis.get("price", 0) > 0:
                with self._lock:
                    if self.current_symbol == new_sym:
                        self.last_analysis = analysis

    @staticmethod
    def format_price(p: float) -> str:
        if p <= 0:
            return "€0.00"
        if p < 0.0001:
            return f"€{p:.8f}"
        if p < 0.01:
            return f"€{p:.6f}"
        return f"€{p:,.2f}"

    @staticmethod
    def calculate_opportunity_score(analysis: Dict) -> float:
        """
        Calcula una puntuación cuantitativa multicriterio para seleccionar el mejor activo,
        priorizando sobreventa con confirmación de giro alcista y activos líderes (evitando trampas bajistas).
        """
        if not analysis or analysis.get("price", 0) <= 0:
            return -999.0

        rsi = analysis.get("rsi", 50.0)
        rsi_prev = analysis.get("rsi_prev", rsi)
        price = analysis.get("price", 0.0)
        ema_fast = analysis.get("ema_fast", price)
        ema_slow = analysis.get("ema_slow", price)
        ema_trend = analysis.get("ema_trend", price)
        bb_lower = analysis.get("bb_lower", 0.0)
        sub_cat = analysis.get("sub_category", "")
        hma_50 = analysis.get("hma_50", 0.0)
        hma_50_prev = analysis.get("hma_50_prev", hma_50)
        hma_slope = analysis.get("hma_50_slope", "FLAT")
        session_info = analysis.get("session_info", {})
        candle_bullish = analysis.get("candle_bullish", False)

        score = 0.0

        # 1. Ponderación por calidad y liquidez (preferir activos Top de Binance)
        if sub_cat in ["top4", "top"]:
            score += 25.0
        elif sub_cat == "l1":
            score += 15.0
        elif sub_cat == "memes":
            score += 5.0

        # 2. Zona de sobreventa con confirmación de giro
        if 25.0 <= rsi <= 36.0:
            score += 45.0
            if rsi > rsi_prev:
                score += 25.0  # Giro alcista en formación
            if candle_bullish:
                score += 15.0  # Vela verde cerrando al alza
        elif rsi < 25.0:
            # Sobreventa extrema: si no hay giro, penalizar para evitar cuchillos cayendo
            if rsi > rsi_prev or candle_bullish:
                score += 35.0
            else:
                score -= 15.0  # Desplome vertical sin freno
        elif 36.0 < rsi <= 45.0:
            score += 15.0
            if rsi > rsi_prev and candle_bullish:
                score += 15.0

        # 3. Soporte en Banda Bollinger Inferior
        if bb_lower > 0 and price <= (bb_lower * 1.002):
            score += 20.0

        # 4. Tendencia Dinámica de Hull (HMA 50 - Zero Lag)
        if hma_slope == "UP":
            score += 20.0  # Giro alcista limpio en formación
        elif hma_50 >= hma_50_prev and hma_50 > 0:
            score += 10.0

        if hma_50 > 0 and price >= hma_50:
            score += 15.0  # Fortaleza por encima de la media de Hull

        # 5. Ventana de Liquidez Institucional (13:00 - 17:00 UTC)
        if session_info.get("is_institutional_window"):
            score += 15.0  # Horas de volumen y dirección fiable
        elif session_info.get("liquidity_tier") == "LOW":
            score -= 10.0  # Horas muertas / manipulación

        # 6. Filtro de tendencia macro complementario (Precio vs EMA 50)
        if ema_trend > 0:
            if price >= ema_trend:
                score += 15.0
            elif price >= (ema_trend * 0.97):
                score += 5.0
            else:
                score -= 20.0  # Tendencia bajista profunda

        # 7. Estructura alcista de medias móviles (EMA 9 > EMA 21)
        if ema_fast > ema_slow:
            score += 10.0

        return score

    def get_candidate_symbols(self) -> List[str]:
        if self.active_category in ["top4", "top_4"]:
            return TOP4_SYMBOLS
        if self.active_category in ["all", "crypto"]:
            return SUPPORTED_SYMBOLS
        if self.active_category == "top":
            return [sym for sym, meta in MARKETS_CATALOG.items() if meta.get("sub_category") in ["top", "top4"]]
        return [sym for sym, meta in MARKETS_CATALOG.items() if meta.get("sub_category") == self.active_category or meta.get("category") == self.active_category]

    def _check_daily_experiment_0005_utc(self):
        """Registra 1 fila diaria tras las 00:05 UTC con la vela diaria cerrada BTCEUR y SMA 200."""
        now_utc = datetime.now(timezone.utc)
        if now_utc.hour == 0 and now_utc.minute < 5:
            return
        try:
            _, _, daily_candles = self.feed._get_binance_data("BTCEUR", interval="1d", limit=205)
            if not daily_candles or len(daily_candles) < 201:
                return
            # daily_candles[-1] es la vela del día actual en curso; daily_candles[-2] es la última vela diaria cerrada
            closed_bar = daily_candles[-2]
            current_bar = daily_candles[-1]
            raw_ts = closed_bar.get("time") or closed_bar.get("timestamp") or 0
            ts_sec = raw_ts / 1000.0 if raw_ts > 1e11 else float(raw_ts)
            closed_date = datetime.fromtimestamp(ts_sec, tz=timezone.utc).strftime("%Y-%m-%d")
            if self.experiment.state.get("last_recorded_date") == closed_date:
                return
            closed_window = daily_candles[-201:-1]  # 200 velas cerradas hasta closed_bar inclusive
            sma200 = sum(c["close"] for c in closed_window) / len(closed_window)
            row = self.experiment.process_daily_bar(
                date_str=closed_date,
                open_price=current_bar["open"],
                close_price=closed_bar["close"],
                sma_200=sma200,
            )
            if row:
                self.log(
                    f"📅 Registro diario 00:05 UTC ({closed_date}): Cierre={row['cierre']}€ | "
                    f"SMA200={row['sma200']}€ | Señal={row['senal']} | Bot={row['equity_bot_eur']}€"
                )
        except Exception as e:
            self.log(f"⚠️ Error en registro diario 00:05 UTC: {e}")

    def step(self):
        """Ejecuta una iteración completa del ciclo con aislamiento por entorno."""
        self.iteration_count += 1
        with self._lock:
            if not self.is_running:
                self.status_message = "Bot en Pausa por el usuario"
                return
        self._check_daily_experiment_0005_utc()
        self._process_pending_manual_orders()

        # Ciclo vital y consumo de cómputo de Conway Automaton
        self.automaton.burn_cycle()

        # Sincronizar saldos reales de Binance si estamos en modo real
        if self.active_environment == "live":
            acc_info = self.binance_client.get_account_summary()
            with self._lock:
                self.live_portfolio.cash = acc_info.get("eur_cash", 0.0)
                # Control de comisiones con BNB
                if acc_info.get("has_bnb_fee_discount"):
                    self.live_portfolio.fee_rate = 0.00075
                else:
                    self.live_portfolio.fee_rate = 0.0010

        # Heartbeat regular
        if self.iteration_count % 20 == 0:
            with self._lock:
                env_str = "REAL" if self.active_environment == "live" else "SIMULACIÓN"
                open_cnt = len(self.portfolio.positions)
                cash_val = self.portfolio.cash
            self.log(f"💓 Heartbeat: Motor activo ({env_str} #{self.iteration_count}) | Saldo: €{cash_val:,.2f} | Posiciones: {open_cnt}")

        active_port = self.portfolio

        # Sincronizar salud y batería vital de Automaton con el capital gestionado (Automaton y Cartera son 1 solo sistema)
        with self._lock:
            curr_prices = {self.current_symbol: self.last_analysis.get("price", 0.0)}
            port_summary = active_port.get_summary(curr_prices)
            self.automaton.sync_portfolio(port_summary.get("total_value_eur", 50.0))

        # 1. Prioridad: Gestionar posiciones abiertas del entorno activo (TP, SL, DCA)
        open_symbols = list(active_port.positions.keys())
        for sym in open_symbols:
            analysis = self.feed.analyze_symbol(sym)
            price = analysis.get("price", 0.0)
            if price <= 0:
                continue

            with self._lock:
                if sym == self.current_symbol:
                    self.last_analysis = analysis
                position = active_port.positions.get(sym)
                cash = active_port.cash
                manual_exit_reason = self._evaluate_manual_risk(sym, price, position)
                if manual_exit_reason:
                    action, amount_eur, reason = "SELL", 0.0, manual_exit_reason
                elif position.get("strategy_tag") == "MANUAL":
                    action, amount_eur, reason = "HOLD", 0.0, "Posición manual bajo gestión del usuario"
                else:
                    action, amount_eur, reason = self.automaton.evaluate_position_management(sym, analysis, position, cash, self.config)
                now_str = datetime.now().strftime("%H:%M:%S")

                if action == "SELL":
                    if self.active_environment == "live" and self.live_trading_armed:
                        # Venta real en Binance
                        raw_qty = position.get("amount", 0.0)
                        ok, adj_qty, msg = BinanceRulesEngine.adjust_quantity_for_sell(sym, raw_qty, price)
                        if ok:
                            placed, res, order_msg = self.binance_client.place_smart_order(sym, "SELL", adj_qty)
                            if placed:
                                trade = active_port.sell(sym, price, f"[Binance Real] {reason}", sell_pct=1.0)
                                if trade:
                                    pnl_val = trade.get('realized_pnl_eur', 0.0)
                                    self.automaton.record_profit(pnl_val, reason)
                                    self.automaton.record_trade_exit(
                                        sym,
                                        pnl_val,
                                        was_stoploss=("Stop" in reason or pnl_val < 0),
                                        strategy_tag=position.get("strategy_tag", ""),
                                    )
                                self.log(f"🔴 VENTA REAL EN BINANCE: {adj_qty} {sym} a {self.format_price(price)} | {reason}")
                            else:
                                self.log(f"⚠️ Error orden venta Binance: {order_msg}")
                    else:
                        sweep_pct = self.config.get("msci_sweep_pct", 0.0)
                        trade = active_port.sell(sym, price, reason, sell_pct=1.0, sweep_pct=sweep_pct)
                        if trade:
                            pnl_val = trade.get('realized_pnl_eur', 0.0)
                            pnl_sign = "+" if pnl_val >= 0 else ""
                            # Alimentar a Automaton con los beneficios generados
                            self.automaton.record_profit(pnl_val, reason)
                            self.automaton.record_trade_exit(
                                sym,
                                pnl_val,
                                was_stoploss=("Stop" in reason or pnl_val < 0),
                                strategy_tag=position.get("strategy_tag", ""),
                            )
                            self.log(f"💰 VENTA ({trade['environment'].upper()}): €{trade['amount_eur']:.2f} {sym} a {self.format_price(price)} | P&L: {pnl_sign}€{trade['realized_pnl_eur']:.4f} ({trade.get('pnl_pct', 0):+.2f}%) | {reason}")
                            self.status_message = f"Venta de {sym} con beneficio {pnl_sign}€{trade['realized_pnl_eur']:.4f}"
                            self.last_action = {"action": action, "reason": reason, "time": now_str}
                            return
                elif action == "BUY" and amount_eur > 0:
                    if self.active_environment == "live":
                        if not self.live_trading_armed:
                            self.status_message = "Modo Real: Señal de compra detectada pero trading real desarmado (Modo Seguro)"
                            return
                        if active_port.cash < amount_eur:
                            self.status_message = f"Modo Real: Saldo en Binance (€{active_port.cash:.2f}) menor que orden (€{amount_eur:.2f})"
                            return
                        # Compra real en Binance
                        ok, adj_qty, msg = BinanceRulesEngine.validate_buy_order(sym, amount_eur, price)
                        if ok:
                            placed, res, order_msg = self.binance_client.place_smart_order(sym, "BUY", adj_qty)
                            if placed:
                                trade = active_port.buy(sym, amount_eur, price, f"[Binance Real] {reason}")
                                self.log(f"🔴 COMPRA REAL EN BINANCE: {adj_qty} {sym} a {self.format_price(price)} (€{amount_eur:.2f})")
                            else:
                                self.log(f"⚠️ Error orden compra Binance: {order_msg}")
                    else:
                        trade = active_port.buy(sym, amount_eur, price, reason)
                        if trade:
                            self.log(f"✅ DCA ({trade['environment'].upper()}): {trade['quantity']} {sym} a {self.format_price(price)} (€{amount_eur:.2f} | {reason})")
                            self.status_message = f"DCA en {sym}"
                            self.last_action = {"action": action, "reason": reason, "time": now_str}
                            return

        # 2. Protección de Saldo Mínimo: Bloquear nuevas entradas si no hay saldo para MIN_NOTIONAL
        min_order = self.config.get("min_order_eur", 5.0)
        if active_port.cash < min_order:
            with self._lock:
                now_str = datetime.now().strftime("%H:%M:%S")
                env_prefix = "[REAL] " if self.active_environment == "live" else ""
                msg = f"{env_prefix}Esperando cierre de posición (Saldo libre €{active_port.cash:.2f} < €{min_order:.2f} MIN_NOTIONAL)"
                self.status_message = msg
                self.last_action = {"action": "HOLD", "reason": msg, "time": now_str}
            return

        # 3. Escáner Cuantitativo Multiactivo (Top 4 Líderes: BTC, ETH, BNB, SOL)
        candidate_symbols = self.get_candidate_symbols()
        # Filtrar candidatos que no tengan posición abierta ya (la posición abierta se gestiona en el paso 1)
        unheld_candidates = [s for s in candidate_symbols if s not in active_port.positions]
        if not unheld_candidates:
            unheld_candidates = candidate_symbols or [self.current_symbol]

        analyses = {}
        with ThreadPoolExecutor(max_workers=min(len(unheld_candidates), 8)) as executor:
            future_to_sym = {executor.submit(self.feed.analyze_symbol, s): s for s in unheld_candidates}
            for future in future_to_sym:
                s = future_to_sym[future]
                try:
                    res = future.result()
                    if res and res.get("price", 0) > 0:
                        analyses[s] = res
                except Exception:
                    pass

        if not analyses:
            return

        # 3. Evaluación Autónoma de Inversión por Conway Automaton + BTC Macro Guard
        btc_health = self.feed.get_btc_macro_health(interval=self.config.get("candle_interval", "4h"))
        with self._lock:
            self.automaton.shadow_tracker.update_with_analyses(analyses)
            cur_prices = {s: float(a.get("price", 0.0)) for s, a in analyses.items() if a.get("price", 0.0) > 0}
            cur_equity = active_port.get_summary(cur_prices).get("total_value_eur", active_port.cash)
            self.automaton.update_equity_drawdown(cur_equity)
            cash = active_port.cash
            best_buy_sym, best_buy_analysis, best_buy_amount, best_buy_reason = self.automaton.evaluate_new_entry(
                analyses,
                cash,
                self.config,
                open_positions_count=len(active_port.positions),
                btc_healthy=btc_health.get("btc_bullish", True),
            )
            now_str = datetime.now().strftime("%H:%M:%S")
            env_prefix = "[REAL] " if self.active_environment == "live" else ""

            if best_buy_sym:
                target_symbol = best_buy_sym
                target_analysis = best_buy_analysis
                price = target_analysis.get("price", 0.0)
                amount_eur = best_buy_amount
                target_name = MARKETS_CATALOG.get(target_symbol, {}).get("name", target_symbol)

                strat_tag = self.automaton.last_council_debate.get("strategy_tag", "DCA_REVERSION")
                if self.active_environment == "live":
                    if not self.live_trading_armed:
                        self.status_message = f"Modo Real: Señal de compra en {target_name} (Trading Real Desarmado)"
                    elif cash < amount_eur:
                        self.status_message = f"Modo Real: Saldo insuficiente en Binance (€{cash:.2f} < €{amount_eur:.2f})"
                    else:
                        bid_p, ask_p = self.binance_client.get_book_ticker(target_symbol)
                        spread_pct = ((ask_p - bid_p) / bid_p * 100.0) if (bid_p > 0 and ask_p >= bid_p) else 0.0
                        if spread_pct > 0.35:
                            self.status_message = f"SpreadFilter bloquea {target_name}: spread {spread_pct:.2f}% > 0.35%"
                            self.log(f"⚠️ SpreadFilter bloqueó entrada en {target_symbol} (spread {spread_pct:.2f}%)")
                        else:
                            ok, adj_qty, msg = BinanceRulesEngine.validate_buy_order(target_symbol, amount_eur, price)
                            if ok:
                                placed, res, order_msg = self.binance_client.place_smart_order(target_symbol, "BUY", adj_qty)
                                if placed:
                                    trade = active_port.buy(target_symbol, amount_eur, price, f"[Binance Real] {best_buy_reason}", strategy_tag=strat_tag)
                                    self.current_symbol = target_symbol
                                    self.last_analysis = target_analysis
                                    self.last_action = {"action": "BUY", "reason": best_buy_reason, "time": now_str}
                                    self.log(f"🔴 COMPRA REAL EN BINANCE ({target_name}): {adj_qty} a {self.format_price(price)}")
                                    self.status_message = f"Compra Real ejecutada en {target_name}"
                                else:
                                    self.log(f"⚠️ Error orden Binance: {order_msg}")
                else:
                    trade = active_port.buy(target_symbol, amount_eur, price, best_buy_reason, strategy_tag=strat_tag)
                    if trade:
                        self.current_symbol = target_symbol
                        self.last_analysis = target_analysis
                        self.last_action = {"action": "BUY", "reason": best_buy_reason, "time": now_str}
                        self.log(f"✅ COMPRA EJECUTADA ({target_name}): {trade['quantity']} a {self.format_price(price)} (€{amount_eur:.2f} | {best_buy_reason})")
                        self.status_message = f"Compra ejecutada de {target_name}"
            else:
                # Mantener en radar el activo con mejor análisis o el que el usuario tenga seleccionado
                target_symbol = self.current_symbol if self.current_symbol in analyses else list(analyses.keys())[0]
                target_analysis = analyses.get(target_symbol, list(analyses.values())[0])
                self.last_analysis = target_analysis
                target_name = MARKETS_CATALOG.get(target_symbol, {}).get("name", target_symbol)
                target_reason = best_buy_reason
                self.last_action = {"action": "HOLD", "reason": target_reason, "time": now_str}
                cat_label = "Top 4" if self.active_category in ["top4", "top_4"] else self.active_category.upper()
                self.status_message = f"{env_prefix}Escaneando {cat_label} | {target_name} ({target_symbol}) - {target_reason}"

    def run_loop(self):
        self.log(f"🚀 SV Inversión iniciado | Entorno: {self.active_environment.upper()}")
        consecutive_errors = 0
        while not self._stop_event.is_set():
            try:
                self.step()
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                backoff = min(60, 6 * (2 ** min(consecutive_errors - 1, 4)))
                self.log(f"⚠️ Error en ciclo del bot: {e}. Reintentando en {backoff}s...")
                time.sleep(backoff)
                continue
            time.sleep(self.config.get("check_interval_seconds", 6))

    def start(self):
        self.frozen_hash = verify_frozen_config()
        self.live_trading_armed = False
        self.active_environment = "simulation"
        self.log(
            f"🔒 Experimento congelado {FROZEN_EXPERIMENT['version']} | "
            f"Hash={self.frozen_hash[:12]}... | Inicio={FROZEN_EXPERIMENT['start_date']} | "
            f"Revisión={FROZEN_EXPERIMENT['review_date']} | live_armed=False"
        )
        if self.binance_client.is_configured():
            rec = self.binance_client.reconcile_startup("BTCEUR")
            self.log(
                f"🔄 Reconciliación Binance al arrancar: ok={rec.get('ok')} | "
                f"EUR={rec.get('eur_free', 0.0):.2f} | BTC={rec.get('asset_free', 0.0):.6f} | "
                f"Órdenes abiertas={rec.get('open_orders_count', 0)}"
            )
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self.run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def emergency_sell_all(self) -> int:
        sold_count = 0
        active_port = self.portfolio
        open_syms = list(active_port.positions.keys())
        for sym in open_syms:
            p = self.feed.last_known_prices_eur.get(sym, 0.0)
            if p <= 0:
                analysis = self.feed.analyze_symbol(sym)
                p = analysis.get("price", 0.0)
            with self._lock:
                pos = active_port.positions.get(sym)
                if not pos:
                    continue
                if p <= 0:
                    p = pos.get("avg_entry_price", 0.0)
                if p > 0:
                    trade = active_port.sell(sym, p, "⚠️ Venta de Emergencia solicitada", sell_pct=1.0)
                    if trade:
                        sold_count += 1
                        self.log(f"🚨 Venta de emergencia ({trade['environment'].upper()}): {sym} a €{p:,.2f}")
        return sold_count

    def _resolve_live_price(self, symbol: str) -> float:
        """Obtiene el precio EUR más reciente del caché o consultando el feed."""
        price = self.feed.last_known_prices_eur.get(symbol, 0.0)
        if price <= 0:
            analysis = self.feed.analyze_symbol(symbol)
            price = float(analysis.get("price", 0.0) or 0.0)
        return price

    def _load_manual_orders(self) -> List[Dict]:
        if not self.manual_orders_file.exists():
            return []
        try:
            with open(self.manual_orders_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_manual_orders(self):
        try:
            with open(self.manual_orders_file, "w", encoding="utf-8") as f:
                json.dump(self.pending_orders, f, indent=2)
        except Exception:
            pass

    def _evaluate_manual_risk(self, sym: str, price: float, position: Dict) -> Optional[str]:
        """Evalúa SL, TP y Trailing Stop personalizados configurados en la posición."""
        if not position or price <= 0:
            return None
        avg_entry = float(position.get("avg_entry_price", 0.0) or 0.0)
        if avg_entry <= 0:
            return None

        peak = float(position.get("peak_price", avg_entry) or avg_entry)
        if price > peak:
            position["peak_price"] = price
            peak = price
            self.portfolio.save()

        pnl_pct = ((price - avg_entry) / avg_entry) * 100.0
        sl_pct = position.get("manual_sl_pct")
        tp_pct = position.get("manual_tp_pct")
        trail_pct = position.get("manual_trail_pct")

        if sl_pct is not None and pnl_pct <= float(sl_pct):
            return f"🛑 Stop Loss Manual ({float(sl_pct):.2f}% | P&L {pnl_pct:+.2f}%)"
        if tp_pct is not None and pnl_pct >= float(tp_pct):
            return f"🎯 Take Profit Manual (+{float(tp_pct):.2f}% | P&L {pnl_pct:+.2f}%)"
        if trail_pct is not None and peak > 0:
            trail_trigger = peak * (1.0 - float(trail_pct) / 100.0)
            if price <= trail_trigger:
                return f"📉 Trailing Stop Manual (-{float(trail_pct):.2f}% desde máximo €{peak:,.2f})"
        return None

    def _process_pending_manual_orders(self):
        """Comprueba órdenes Límite pendientes y las ejecuta cuando el precio alcanza el objetivo."""
        if not self.pending_orders:
            return
        with self._lock:
            orders_snapshot = list(self.pending_orders)

        for order in orders_snapshot:
            sym = order.get("symbol", "")
            side = order.get("side", "")
            limit_price = float(order.get("limit_price", 0.0) or 0.0)
            if not sym or limit_price <= 0:
                continue
            price = self._resolve_live_price(sym)
            if price <= 0:
                continue

            if side == "BUY" and price <= limit_price:
                res = self.manual_buy(
                    symbol=sym,
                    amount_eur=float(order.get("amount_eur", 0.0)),
                    order_type="MARKET",
                    sl_pct=order.get("sl_pct"),
                    tp_pct=order.get("tp_pct"),
                    trail_pct=order.get("trail_pct"),
                )
                if res.get("ok"):
                    self.cancel_manual_order(order["id"], silent=True)
                    self.log(f"🎯 Orden Límite BUY ejecutada: {sym} @ €{price:,.2f} (objetivo €{limit_price:,.2f})")
            elif side == "SELL" and price >= limit_price:
                res = self.manual_sell(
                    symbol=sym,
                    sell_pct=float(order.get("sell_pct", 1.0)),
                    order_type="MARKET",
                )
                if res.get("ok"):
                    self.cancel_manual_order(order["id"], silent=True)
                    self.log(f"🎯 Orden Límite SELL ejecutada: {sym} @ €{price:,.2f} (objetivo €{limit_price:,.2f})")

    def manual_buy(
        self,
        symbol: str,
        amount_eur: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        sl_pct: Optional[float] = None,
        tp_pct: Optional[float] = None,
        trail_pct: Optional[float] = None,
    ) -> Dict:
        """Ejecuta una compra manual (Mercado o Límite) con SL/TP/Trailing opcionales."""
        sym = (symbol or self.current_symbol).upper().strip()
        if sym not in SUPPORTED_SYMBOLS:
            return {"ok": False, "error": f"Símbolo no soportado: {sym}"}
        if amount_eur <= 0:
            return {"ok": False, "error": "El importe debe ser mayor que 0 €."}

        otype = (order_type or "MARKET").upper().strip()
        if otype == "LIMIT":
            if not limit_price or float(limit_price) <= 0:
                return {"ok": False, "error": "Indica un precio límite válido mayor que 0 €."}
            with self._lock:
                if self.portfolio.cash < float(amount_eur):
                    return {"ok": False, "error": f"Saldo insuficiente para reservar la orden (disponible: €{self.portfolio.cash:.2f})."}
                order = {
                    "id": uuid.uuid4().hex[:8],
                    "symbol": sym,
                    "side": "BUY",
                    "amount_eur": round(float(amount_eur), 2),
                    "limit_price": round(float(limit_price), 4),
                    "sl_pct": -abs(float(sl_pct)) if sl_pct else None,
                    "tp_pct": abs(float(tp_pct)) if tp_pct else None,
                    "trail_pct": abs(float(trail_pct)) if trail_pct else None,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.pending_orders.append(order)
                self._save_manual_orders()
                self.log(f"📌 Orden Límite BUY creada: {sym} €{order['amount_eur']:.2f} si baja a €{order['limit_price']:,.2f}")
                return {"ok": True, "pending": True, "order": order, "cash_eur": round(self.portfolio.cash, 4)}

        price = self._resolve_live_price(sym)
        if price <= 0:
            return {"ok": False, "error": f"No se pudo obtener precio en vivo para {sym}."}

        with self._lock:
            active_port = self.portfolio
            if active_port.cash <= 0:
                return {"ok": False, "error": "Sin liquidez disponible (€0.00)."}
            trade = active_port.buy(
                sym,
                float(amount_eur),
                price,
                reason="Operación manual del usuario",
                strategy_tag="MANUAL",
            )
            if not trade:
                return {
                    "ok": False,
                    "error": f"Orden rechazada por mínimo de Binance o saldo insuficiente (disponible: €{active_port.cash:.2f}).",
                }
            if sl_pct or tp_pct or trail_pct:
                active_port.set_position_risk(sym, sl_pct=sl_pct, tp_pct=tp_pct, trail_pct=trail_pct)
            self.last_action = {
                "action": "BUY",
                "reason": f"Compra manual {sym} (€{trade['amount_eur']:.2f})",
                "time": datetime.now().strftime("%H:%M:%S"),
            }
            self.log(f"✋ Compra manual ({trade['environment'].upper()}): {sym} €{trade['amount_eur']:.2f} @ €{price:,.2f}")
            return {"ok": True, "trade": trade, "cash_eur": round(active_port.cash, 4)}

    def manual_sell(
        self,
        symbol: str,
        sell_pct: float = 1.0,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
    ) -> Dict:
        """Ejecuta una venta manual (Mercado o Límite) parcial o total."""
        sym = (symbol or self.current_symbol).upper().strip()
        if sym not in SUPPORTED_SYMBOLS:
            return {"ok": False, "error": f"Símbolo no soportado: {sym}"}
        pct = max(0.01, min(1.0, float(sell_pct)))

        otype = (order_type or "MARKET").upper().strip()
        if otype == "LIMIT":
            if not limit_price or float(limit_price) <= 0:
                return {"ok": False, "error": "Indica un precio límite válido mayor que 0 €."}
            with self._lock:
                pos = self.portfolio.positions.get(sym)
                if not pos or pos.get("amount", 0.0) <= 0:
                    return {"ok": False, "error": f"No tienes posición abierta en {sym}."}
                order = {
                    "id": uuid.uuid4().hex[:8],
                    "symbol": sym,
                    "side": "SELL",
                    "sell_pct": pct,
                    "limit_price": round(float(limit_price), 4),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.pending_orders.append(order)
                self._save_manual_orders()
                self.log(f"📌 Orden Límite SELL creada: {sym} ({int(round(pct*100))}%) si sube a €{order['limit_price']:,.2f}")
                return {"ok": True, "pending": True, "order": order, "cash_eur": round(self.portfolio.cash, 4)}

        price = self._resolve_live_price(sym)
        with self._lock:
            active_port = self.portfolio
            pos = active_port.positions.get(sym)
            if not pos or pos.get("amount", 0.0) <= 0:
                return {"ok": False, "error": f"No tienes posición abierta en {sym}."}
            if price <= 0:
                price = float(pos.get("avg_entry_price", 0.0) or 0.0)
            if price <= 0:
                return {"ok": False, "error": f"No se pudo obtener precio para vender {sym}."}

            trade = active_port.sell(
                sym,
                price,
                reason=f"Venta manual del usuario ({int(round(pct * 100))}%)",
                sell_pct=pct,
            )
            if not trade:
                return {"ok": False, "error": f"No se pudo cerrar la posición en {sym}."}
            self.last_action = {
                "action": "SELL",
                "reason": f"Venta manual {sym} ({int(round(pct * 100))}%)",
                "time": datetime.now().strftime("%H:%M:%S"),
            }
            self.log(
                f"✋ Venta manual ({trade['environment'].upper()}): {sym} @ €{price:,.2f} "
                f"| P&L: €{trade['realized_pnl_eur']:+.4f}"
            )
            return {"ok": True, "trade": trade, "cash_eur": round(active_port.cash, 4)}

    def update_position_risk(
        self,
        symbol: str,
        sl_pct: Optional[float] = None,
        tp_pct: Optional[float] = None,
        trail_pct: Optional[float] = None,
    ) -> Dict:
        sym = (symbol or self.current_symbol).upper().strip()
        with self._lock:
            pos = self.portfolio.set_position_risk(sym, sl_pct=sl_pct, tp_pct=tp_pct, trail_pct=trail_pct)
            if not pos:
                return {"ok": False, "error": f"No hay posición abierta en {sym}."}
            self.log(
                f"🛡️ Riesgo actualizado en {sym}: SL={pos.get('manual_sl_pct')}% | "
                f"TP={pos.get('manual_tp_pct')}% | Trail={pos.get('manual_trail_pct')}%"
            )
            return {"ok": True, "symbol": sym, "position": pos}

    def cancel_manual_order(self, order_id: str, silent: bool = False) -> Dict:
        with self._lock:
            before = len(self.pending_orders)
            self.pending_orders = [o for o in self.pending_orders if o.get("id") != order_id]
            if len(self.pending_orders) == before:
                return {"ok": False, "error": "Orden no encontrada."}
            self._save_manual_orders()
            if not silent:
                self.log(f"❌ Orden límite {order_id} cancelada por el usuario.")
            return {"ok": True, "pending_orders": list(self.pending_orders)}

    def get_state(self) -> Dict:
        if self.current_symbol not in self.feed.last_analysis_cache:
            analysis = self.feed.analyze_symbol(self.current_symbol)
            if analysis.get("price", 0) > 0:
                with self._lock:
                    self.last_analysis = analysis

        with self._lock:
            prices = {}
            for port in [self.sim_portfolio, self.live_portfolio]:
                for sym, pos in port.positions.items():
                    cached_p = self.feed.last_known_prices_eur.get(sym, 0.0)
                    prices[sym] = cached_p if cached_p > 0 else pos.get("avg_entry_price", 0.0)

            active_analysis = self.feed.last_analysis_cache.get(self.current_symbol) or self.last_analysis
            if self.current_symbol not in prices:
                prices[self.current_symbol] = active_analysis.get("price", 0.0)

            sim_summary = self.sim_portfolio.get_summary(prices)
            live_summary = self.live_portfolio.get_summary(prices)
            active_summary = live_summary if self.active_environment == "live" else sim_summary
            binance_info = self.binance_client.get_account_summary()

            return {
                "bot_status": "ACTIVO" if self.is_running else "PAUSADO",
                "is_running": self.is_running,
                "active_environment": self.active_environment,
                "live_trading_armed": self.live_trading_armed,
                "binance_account": binance_info,
                "current_symbol": self.current_symbol,
                "active_category": self.active_category,
                "supported_symbols": SUPPORTED_SYMBOLS,
                "markets_catalog": MARKETS_CATALOG,
                "status_message": self.status_message,
                "analysis": active_analysis,
                "last_action": self.last_action,
                "portfolio": active_summary,
                "simulation": sim_summary,
                "live": live_summary,
                "automaton": self.automaton.get_status_dict(),
                "config": self.config,
                "pending_orders": list(self.pending_orders),
                "logs": self.logs[:35]
            }
