import sys
import time
import threading
from datetime import datetime
from typing import Dict, Optional, List

# Garantizar compatibilidad con caracteres UTF-8 en consolas de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .config import CONFIG, SUPPORTED_SYMBOLS, MARKETS_CATALOG
from .market_data import MarketDataFeed
from .portfolio import Portfolio
from .strategy import SmartDCAStrategy

class TradingBot:
    def __init__(self, config: Dict = None):
        self.config = config or CONFIG.copy()
        self.feed = MarketDataFeed()
        self.portfolio = Portfolio()
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

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
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

            # Si no estaba en caché o para refrescar al instante sin bloquear el lock:
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

    def get_candidate_symbols(self) -> List[str]:
        if self.active_category == "all":
            return SUPPORTED_SYMBOLS
        return [sym for sym, meta in MARKETS_CATALOG.items() if meta.get("category") == self.active_category]

    def step(self):
        """Ejecuta una iteración completa del ciclo de trading multi-mercado."""
        self.iteration_count += 1
        if self.iteration_count % 20 == 0:
            with self._lock:
                open_cnt = len(self.portfolio.positions)
                cash_val = self.portfolio.cash
            self.log(f"💓 Heartbeat: Motor cuantitativo activo (Ciclo #{self.iteration_count}) | Saldo: €{cash_val:,.2f} | Posiciones: {open_cnt}")

        with self._lock:
            if not self.is_running:
                self.status_message = "Bot en Pausa por el usuario"
                return

        # 1. Prioridad: Gestionar posiciones abiertas (Take-profit, Stop-loss, DCA)
        open_symbols = list(self.portfolio.positions.keys())
        for sym in open_symbols:
            analysis = self.feed.analyze_symbol(sym)
            price = analysis.get("price", 0.0)
            if price <= 0:
                continue

            with self._lock:
                if sym == self.current_symbol:
                    self.last_analysis = analysis
                position = self.portfolio.positions.get(sym)
                cash = self.portfolio.cash
                action, amount_eur, reason = self.strategy.evaluate(analysis, position, cash)
                now_str = datetime.now().strftime("%H:%M:%S")

                if action == "SELL":
                    sweep_pct = self.config.get("msci_sweep_pct", 0.0)
                    trade = self.portfolio.sell(sym, price, reason, sell_pct=1.0, sweep_pct=sweep_pct)
                    if trade:
                        pnl_sign = "+" if trade['realized_pnl_eur'] >= 0 else ""
                        self.log(f"💰 VENTA EJECUTADA: €{trade['amount_eur']:.2f} {sym} a €{price:,.2f} | P&L: {pnl_sign}€{trade['realized_pnl_eur']:.4f} ({trade.get('pnl_pct', 0):+.2f}%) | {reason}")
                        self.status_message = f"Venta de {sym} con beneficio {pnl_sign}€{trade['realized_pnl_eur']:.4f}"
                        self.last_action = {"action": action, "reason": reason, "time": now_str}
                        return
                elif action == "BUY" and amount_eur > 0:
                    trade = self.portfolio.buy(sym, amount_eur, price, reason)
                    if trade:
                        self.log(f"✅ DCA EJECUTADO: {trade['quantity']:.6f} {sym} a €{price:,.2f} (€{amount_eur:.2f} | {reason})")
                        self.status_message = f"DCA en {sym}"
                        self.last_action = {"action": action, "reason": reason, "time": now_str}
                        return

        # 2. Escanear la lista de candidatos según el filtro activo
        candidate_symbols = self.get_candidate_symbols()
        best_candidate = None
        best_analysis = None
        lowest_rsi = 999.0

        # Asegurar que el símbolo activo en pantalla siempre se actualice
        symbols_to_scan = list(candidate_symbols)
        if self.current_symbol not in symbols_to_scan:
            symbols_to_scan.insert(0, self.current_symbol)

        for sym in symbols_to_scan:
            analysis = self.feed.analyze_symbol(sym)
            if analysis.get("price", 0) > 0:
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
            position = self.portfolio.positions.get(target_symbol)
            cash = self.portfolio.cash
            action, amount_eur, reason = self.strategy.evaluate(target_analysis, position, cash)
            now_str = datetime.now().strftime("%H:%M:%S")

            target_name = MARKETS_CATALOG.get(target_symbol, {}).get("name", target_symbol)

            if action == "BUY" and amount_eur > 0:
                price = target_analysis.get("price", 0.0)
                trade = self.portfolio.buy(target_symbol, amount_eur, price, reason)
                if trade:
                    self.current_symbol = target_symbol
                    self.last_analysis = target_analysis
                    self.last_action = {"action": action, "reason": reason, "time": now_str}
                    self.log(f"✅ COMPRA EJECUTADA ({target_name}): {trade['quantity']:.6f} a €{price:,.2f} (€{amount_eur:.2f} | {reason})")
                    self.status_message = f"Compra ejecutada de {target_name}"
            else:
                # Mostrar la evaluación del activo actualmente seleccionado en pantalla
                curr_analysis = self.feed.last_analysis_cache.get(self.current_symbol) or self.last_analysis
                curr_pos = self.portfolio.positions.get(self.current_symbol)
                curr_act, _, curr_reason = self.strategy.evaluate(curr_analysis, curr_pos, cash)
                self.last_action = {"action": curr_act, "reason": curr_reason, "time": now_str}
                curr_name = MARKETS_CATALOG.get(self.current_symbol, {}).get("name", self.current_symbol)
                self.status_message = f"Monitorizando {curr_name} ({self.current_symbol}): {curr_reason}"

    def run_loop(self):
        self.log(f"🚀 SV Inversión iniciado con capital disponible de €{self.portfolio.cash:.2f}")
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
        open_syms = list(self.portfolio.positions.keys())
        for sym in open_syms:
            p = self.feed.last_known_prices_eur.get(sym, 0.0)
            if p <= 0:
                analysis = self.feed.analyze_symbol(sym)
                p = analysis.get("price", 0.0)
            with self._lock:
                pos = self.portfolio.positions.get(sym)
                if not pos:
                    continue
                if p <= 0:
                    p = pos.get("avg_entry_price", 0.0)
                if p > 0:
                    sweep_pct = self.config.get("msci_sweep_pct", 0.0)
                    trade = self.portfolio.sell(sym, p, "⚠️ Venta de Emergencia solicitada por el usuario", sell_pct=1.0, sweep_pct=sweep_pct)
                    if trade:
                        sold_count += 1
                        self.log(f"🚨 Venta de emergencia completada para {sym} a €{p:,.2f}")
        return sold_count

    def get_state(self) -> Dict:
        # Si aún no hay análisis en caché para el símbolo actual, obtenerlo fuera del lock
        if self.current_symbol not in self.feed.last_analysis_cache:
            analysis = self.feed.analyze_symbol(self.current_symbol)
            if analysis.get("price", 0) > 0:
                with self._lock:
                    self.last_analysis = analysis

        with self._lock:
            # Usar precios en caché EUR para respuesta instantánea sin bloquear
            prices = {}
            for sym, pos in self.portfolio.positions.items():
                cached_p = self.feed.last_known_prices_eur.get(sym, 0.0)
                prices[sym] = cached_p if cached_p > 0 else pos.get("avg_entry_price", 0.0)

            active_analysis = self.feed.last_analysis_cache.get(self.current_symbol) or self.last_analysis
            if self.current_symbol not in prices:
                prices[self.current_symbol] = active_analysis.get("price", 0.0)

            summary = self.portfolio.get_summary(prices)
            return {
                "bot_status": "ACTIVO" if self.is_running else "PAUSADO",
                "is_running": self.is_running,
                "current_symbol": self.current_symbol,
                "active_category": self.active_category,
                "supported_symbols": SUPPORTED_SYMBOLS,
                "markets_catalog": MARKETS_CATALOG,
                "status_message": self.status_message,
                "analysis": active_analysis,
                "last_action": self.last_action,
                "portfolio": summary,
                "config": self.config,
                "logs": self.logs[:35]
            }
