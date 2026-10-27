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
            with self._lock:
                self.current_symbol = symbol
                self.config["symbol"] = symbol
                meta = MARKETS_CATALOG.get(symbol, {})
                name = meta.get("name", symbol)
                self.log(f"Activo seleccionado: {name} ({symbol})")

    def set_category(self, category: str):
        with self._lock:
            self.active_category = category
            self.config["active_category"] = category
            self.log(f"Filtro de mercado cambiado a: {category.upper()}")

    def get_candidate_symbols(self) -> List[str]:
        if self.active_category == "all":
            return SUPPORTED_SYMBOLS
        return [sym for sym, meta in MARKETS_CATALOG.items() if meta.get("category") == self.active_category]

    def step(self):
        """Ejecuta una iteración completa del ciclo de trading multi-mercado."""
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
                position = self.portfolio.positions.get(sym)
                cash = self.portfolio.cash
                action, amount_eur, reason = self.strategy.evaluate(analysis, position, cash)
                now_str = datetime.now().strftime("%H:%M:%S")

                if action == "SELL":
                    trade = self.portfolio.sell(sym, price, reason, sell_pct=1.0)
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

        # 2. Si hay capital libre, escanear la lista de candidatos según el filtro activo
        candidate_symbols = self.get_candidate_symbols()
        best_candidate = None
        best_analysis = None
        lowest_rsi = 999.0

        for sym in candidate_symbols:
            analysis = self.feed.analyze_symbol(sym)
            if analysis.get("price", 0) > 0:
                if sym == self.current_symbol:
                    with self._lock:
                        self.last_analysis = analysis
                rsi = analysis.get("rsi", 50.0)
                if rsi < lowest_rsi:
                    lowest_rsi = rsi
                    best_candidate = sym
                    best_analysis = analysis

        target_symbol = best_candidate or self.current_symbol
        target_analysis = best_analysis or self.last_analysis

        with self._lock:
            if not self.last_analysis:
                self.last_analysis = target_analysis
            position = self.portfolio.positions.get(target_symbol)
            cash = self.portfolio.cash
            action, amount_eur, reason = self.strategy.evaluate(target_analysis, position, cash)
            now_str = datetime.now().strftime("%H:%M:%S")
            self.last_action = {"action": action, "reason": reason, "time": now_str}

            target_name = MARKETS_CATALOG.get(target_symbol, {}).get("name", target_symbol)

            if action == "BUY" and amount_eur > 0:
                price = target_analysis.get("price", 0.0)
                trade = self.portfolio.buy(target_symbol, amount_eur, price, reason)
                if trade:
                    self.current_symbol = target_symbol
                    self.log(f"✅ COMPRA EJECUTADA ({target_name}): {trade['quantity']:.6f} a €{price:,.2f} (€{amount_eur:.2f} | {reason})")
                    self.status_message = f"Compra ejecutada de {target_name}"
            else:
                curr_name = MARKETS_CATALOG.get(self.current_symbol, {}).get("name", self.current_symbol)
                self.status_message = f"Monitorizando {curr_name} ({self.current_symbol}): {reason}"

    def run_loop(self):
        self.log(f"🚀 SV Inversión iniciado con capital de €{self.portfolio.cash:.2f}")
        while not self._stop_event.is_set():
            try:
                self.step()
            except Exception as e:
                self.log(f"⚠️ Error en ciclo del bot: {e}")
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
        with self._lock:
            sold_count = 0
            for sym in list(self.portfolio.positions.keys()):
                analysis = self.feed.analyze_symbol(sym)
                p = analysis.get("price")
                if p:
                    trade = self.portfolio.sell(sym, p, "⚠️ Venta de Emergencia solicitada por el usuario", sell_pct=1.0)
                    if trade:
                        sold_count += 1
                        self.log(f"🚨 Venta de emergencia completada para {sym} a €{p:,.2f}")
            return sold_count

    def get_state(self) -> Dict:
        with self._lock:
            # Precios actuales de todas las posiciones abiertas
            prices = {}
            for sym in self.portfolio.positions.keys():
                analysis = self.feed.analyze_symbol(sym)
                prices[sym] = analysis.get("price", 0.0)

            # Si el símbolo actual no está en posiciones, agregar su precio
            if self.current_symbol not in prices:
                prices[self.current_symbol] = self.last_analysis.get("price", 0.0)

            summary = self.portfolio.get_summary(prices)
            return {
                "bot_status": "ACTIVO" if self.is_running else "PAUSADO",
                "is_running": self.is_running,
                "current_symbol": self.current_symbol,
                "active_category": self.active_category,
                "supported_symbols": SUPPORTED_SYMBOLS,
                "markets_catalog": MARKETS_CATALOG,
                "status_message": self.status_message,
                "last_action": self.last_action,
                "analysis": self.last_analysis,
                "portfolio": summary,
                "config": {
                    "order_amount_eur": self.config.get("order_amount_eur"),
                    "take_profit_pct": self.config.get("take_profit_pct"),
                    "stop_loss_pct": self.config.get("stop_loss_pct"),
                    "rsi_buy_threshold": self.config.get("rsi_buy_threshold"),
                    "rsi_sell_threshold": self.config.get("rsi_sell_threshold"),
                    "active_category": self.active_category,
                    "msci_sweep_pct": self.config.get("msci_sweep_pct", 50.0)
                },
                "logs": self.logs[:20]
            }
