import sys
import time
import threading
from datetime import datetime
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

from .config import CONFIG, SUPPORTED_SYMBOLS, MARKETS_CATALOG, DATA_DIR
from .market_data import MarketDataFeed
from .portfolio import Portfolio
from .strategy import SmartDCAStrategy
from .binance_client import BinanceSpotClient
from .binance_rules import BinanceRulesEngine

class TradingBot:
    def __init__(self, config: Dict = None):
        self.config = config or CONFIG.copy()
        self.feed = MarketDataFeed()

        # Portafolios 100% aislados por entorno
        self.sim_portfolio = Portfolio(storage_path=DATA_DIR / "portfolio.json", environment="simulation")
        self.live_portfolio = Portfolio(storage_path=DATA_DIR / "portfolio_live.json", environment="live", initial_capital=0.0)

        # Entorno activo por defecto: Simulación
        self.active_environment = "simulation"  # 'simulation' | 'live'
        self.live_trading_armed = False          # Cerrojo de seguridad para dinero real
        self.binance_client = BinanceSpotClient()

        self.strategy = SmartDCAStrategy(self.config)

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

    @property
    def portfolio(self) -> Portfolio:
        """Devuelve el portafolio correspondiente al entorno activo."""
        return self.live_portfolio if self.active_environment == "live" else self.sim_portfolio

    def set_environment(self, env: str):
        """Cambia de entorno de forma no destructiva."""
        if env in ["simulation", "live"]:
            with self._lock:
                self.active_environment = env
                env_title = "DINERO REAL (Binance Spot)" if env == "live" else "SIMULACIÓN (Paper Trading)"
                self.log(f"🔄 Entorno cambiado a: {env_title}")

    def set_live_armed(self, armed: bool):
        """Activa o desactiva el cerrojo de seguridad para órdenes reales en Binance."""
        with self._lock:
            self.live_trading_armed = bool(armed)
            estado = "🔴 ARMADO (Órdenes Reales Permitidas)" if armed else "🟢 DESARMADO (Modo Seguro / Sólo Lectura)"
            self.log(f"🛡️ Seguridad Binance: {estado}")

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

    def get_candidate_symbols(self) -> List[str]:
        if self.active_category in ["all", "crypto"]:
            return SUPPORTED_SYMBOLS
        return [sym for sym, meta in MARKETS_CATALOG.items() if meta.get("sub_category") == self.active_category or meta.get("category") == self.active_category]

    def step(self):
        """Ejecuta una iteración completa del ciclo con aislamiento por entorno."""
        self.iteration_count += 1
        with self._lock:
            if not self.is_running:
                self.status_message = "Bot en Pausa por el usuario"
                return

        # Sincronizar saldos reales de Binance si estamos en modo real
        if self.active_environment == "live":
            acc_info = self.binance_client.get_account_summary()
            with self._lock:
                self.live_portfolio.cash = acc_info.get("eur_cash", 0.0)

        # Heartbeat regular
        if self.iteration_count % 20 == 0:
            with self._lock:
                env_str = "REAL" if self.active_environment == "live" else "SIMULACIÓN"
                open_cnt = len(self.portfolio.positions)
                cash_val = self.portfolio.cash
            self.log(f"💓 Heartbeat: Motor activo ({env_str} #{self.iteration_count}) | Saldo: €{cash_val:,.2f} | Posiciones: {open_cnt}")

        active_port = self.portfolio

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
                action, amount_eur, reason = self.strategy.evaluate(analysis, position, cash)
                now_str = datetime.now().strftime("%H:%M:%S")

                if action == "SELL":
                    if self.active_environment == "live" and self.live_trading_armed:
                        # Venta real en Binance
                        raw_qty = position.get("amount", 0.0)
                        ok, adj_qty, msg = BinanceRulesEngine.adjust_quantity_for_sell(sym, raw_qty, price)
                        if ok:
                            placed, res, order_msg = self.binance_client.place_market_order(sym, "SELL", adj_qty)
                            if placed:
                                trade = active_port.sell(sym, price, f"[Binance Real] {reason}", sell_pct=1.0)
                                self.log(f"🔴 VENTA REAL EN BINANCE: {adj_qty} {sym} a {self.format_price(price)} | {reason}")
                            else:
                                self.log(f"⚠️ Error orden venta Binance: {order_msg}")
                    else:
                        sweep_pct = self.config.get("msci_sweep_pct", 0.0)
                        trade = active_port.sell(sym, price, reason, sell_pct=1.0, sweep_pct=sweep_pct)
                        if trade:
                            pnl_sign = "+" if trade['realized_pnl_eur'] >= 0 else ""
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
                            placed, res, order_msg = self.binance_client.place_market_order(sym, "BUY", adj_qty)
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

        # 2. Escanear candidatos concurrentemente según filtro activo (~2.5s para 29 mercados)
        candidate_symbols = self.get_candidate_symbols()
        symbols_to_scan = list(candidate_symbols)
        if self.current_symbol not in symbols_to_scan and symbols_to_scan:
            symbols_to_scan.insert(0, self.current_symbol)

        analyses = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_sym = {executor.submit(self.feed.analyze_symbol, s): s for s in symbols_to_scan}
            for future in future_to_sym:
                s = future_to_sym[future]
                try:
                    res = future.result()
                    if res and res.get("price", 0) > 0:
                        analyses[s] = res
                except Exception:
                    pass

        best_candidate = None
        best_analysis = None
        lowest_rsi = 999.0

        for sym, analysis in analyses.items():
            if sym == self.current_symbol:
                with self._lock:
                    self.last_analysis = analysis
            if sym in candidate_symbols:
                rsi = analysis.get("rsi", 50.0)
                if rsi < lowest_rsi:
                    lowest_rsi = rsi
                    best_candidate = sym
                    best_analysis = analysis

        target_symbol = best_candidate or self.current_symbol
        target_analysis = best_analysis or self.last_analysis

        with self._lock:
            if not self.last_analysis and target_analysis:
                self.last_analysis = target_analysis
            position = active_port.positions.get(target_symbol)
            cash = active_port.cash
            action, amount_eur, reason = self.strategy.evaluate(target_analysis, position, cash)
            now_str = datetime.now().strftime("%H:%M:%S")

            target_name = MARKETS_CATALOG.get(target_symbol, {}).get("name", target_symbol)

            if action == "BUY" and amount_eur > 0:
                price = target_analysis.get("price", 0.0)
                if self.active_environment == "live":
                    if not self.live_trading_armed:
                        self.status_message = f"Modo Real: Señal de compra en {target_name} (Trading Real Desarmado)"
                    elif cash < amount_eur:
                        self.status_message = f"Modo Real: Saldo insuficiente en Binance (€{cash:.2f} < €{amount_eur:.2f})"
                    else:
                        ok, adj_qty, msg = BinanceRulesEngine.validate_buy_order(target_symbol, amount_eur, price)
                        if ok:
                            placed, res, order_msg = self.binance_client.place_market_order(target_symbol, "BUY", adj_qty)
                            if placed:
                                trade = active_port.buy(target_symbol, amount_eur, price, f"[Binance Real] {reason}")
                                self.current_symbol = target_symbol
                                self.last_analysis = target_analysis
                                self.last_action = {"action": action, "reason": reason, "time": now_str}
                                self.log(f"🔴 COMPRA REAL EN BINANCE ({target_name}): {adj_qty} a {self.format_price(price)}")
                                self.status_message = f"Compra Real ejecutada en {target_name}"
                            else:
                                self.log(f"⚠️ Error orden Binance: {order_msg}")
                else:
                    trade = active_port.buy(target_symbol, amount_eur, price, reason)
                    if trade:
                        self.current_symbol = target_symbol
                        self.last_analysis = target_analysis
                        self.last_action = {"action": action, "reason": reason, "time": now_str}
                        self.log(f"✅ COMPRA EJECUTADA ({target_name}): {trade['quantity']} a {self.format_price(price)} (€{amount_eur:.2f} | {reason})")
                        self.status_message = f"Compra ejecutada de {target_name}"
            else:
                curr_analysis = self.feed.last_analysis_cache.get(self.current_symbol) or self.last_analysis
                curr_pos = active_port.positions.get(self.current_symbol)
                curr_act, _, curr_reason = self.strategy.evaluate(curr_analysis, curr_pos, cash)
                self.last_action = {"action": curr_act, "reason": curr_reason, "time": now_str}
                curr_name = MARKETS_CATALOG.get(self.current_symbol, {}).get("name", self.current_symbol)
                env_prefix = "[REAL] " if self.active_environment == "live" else ""
                self.status_message = f"{env_prefix}Monitorizando {curr_name} ({self.current_symbol}): {curr_reason}"

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
                "config": self.config,
                "logs": self.logs[:35]
            }
