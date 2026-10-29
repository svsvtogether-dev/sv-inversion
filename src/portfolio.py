import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from .config import INITIAL_CAPITAL_EUR, TRADING_FEE_RATE, PORTFOLIO_FILE, DATA_DIR
from .binance_rules import BinanceRulesEngine

class Portfolio:
    def __init__(self, storage_path: Optional[Path] = None, environment: str = "simulation", initial_capital: Optional[float] = None):
        self.environment = environment  # 'simulation' | 'live'
        if storage_path:
            self.storage_path = storage_path
        else:
            self.storage_path = PORTFOLIO_FILE if environment == "simulation" else (DATA_DIR / "portfolio_live.json")

        self.initial_capital = initial_capital if initial_capital is not None else (INITIAL_CAPITAL_EUR if environment == "simulation" else 0.0)
        self.fee_rate = TRADING_FEE_RATE
        self.cash = self.initial_capital
        self.positions: Dict[str, Dict] = {}
        self.trades: List[Dict] = []
        self.total_fees_paid = 0.0
        self.realized_pnl = 0.0
        self.msci_vault_eur = 0.0
        self.db_url = os.getenv("DATABASE_URL")
        self.db_key = f"sv_inversion_{self.environment}"
        self.load()

    def _load_from_db(self) -> Optional[Dict]:
        """Intenta recuperar el estado persistente desde PostgreSQL (Supabase / Neon)."""
        if not self.db_url:
            return None
        try:
            import psycopg2
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS bot_state (
                            id VARCHAR(64) PRIMARY KEY,
                            payload JSONB,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    cur.execute("SELECT payload FROM bot_state WHERE id = %s;", (self.db_key,))
                    row = cur.fetchone()
                    if row and row[0]:
                        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        except Exception as e:
            print(f"[Aviso DB {self.environment}] No se pudo leer de base de datos externa: {e}")
        return None

    def _save_to_db(self, data: Dict):
        """Sincroniza el estado en PostgreSQL (Supabase / Neon)."""
        if not self.db_url:
            return
        try:
            import psycopg2
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO bot_state (id, payload, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT (id) DO UPDATE 
                        SET payload = EXCLUDED.payload, updated_at = NOW();
                    """, (self.db_key, json.dumps(data)))
        except Exception as e:
            print(f"[Aviso DB {self.environment}] Error al guardar en base de datos externa: {e}")

    def load(self):
        """Carga el estado del portafolio (DB externa o archivo local)."""
        data = self._load_from_db()
        if not data and self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[Aviso {self.environment}] No se pudo cargar archivo local: {e}")

        if data:
            self.environment = data.get("environment", self.environment)
            self.initial_capital = data.get("initial_capital", self.initial_capital)
            self.fee_rate = data.get("fee_rate", TRADING_FEE_RATE)
            self.cash = float(data.get("cash", self.initial_capital))
            self.positions = data.get("positions", {})
            self.trades = data.get("trades", [])
            self.total_fees_paid = float(data.get("total_fees_paid", 0.0))
            self.realized_pnl = float(data.get("realized_pnl", 0.0))
            self.msci_vault_eur = float(data.get("msci_vault_eur", 0.0))
            return

        self.save()

    def save(self):
        """Guarda el estado actual en disco y en la nube."""
        data = {
            "environment": self.environment,
            "initial_capital": self.initial_capital,
            "fee_rate": self.fee_rate,
            "cash": round(self.cash, 4),
            "positions": self.positions,
            "trades": self.trades,
            "total_fees_paid": round(self.total_fees_paid, 4),
            "realized_pnl": round(self.realized_pnl, 4),
            "msci_vault_eur": round(self.msci_vault_eur, 4),
            "last_updated": datetime.now().isoformat()
        }
        # 1. Guardado local
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Error] Fallo al guardar portafolio ({self.environment}): {e}")

        # 2. Sincronización en la base de datos externa
        self._save_to_db(data)

    def reset(self, new_capital: Optional[float] = None):
        """Reinicia la cuenta."""
        if new_capital is not None:
            self.initial_capital = float(new_capital)
        self.cash = self.initial_capital
        self.positions = {}
        self.trades = []
        self.total_fees_paid = 0.0
        self.realized_pnl = 0.0
        self.msci_vault_eur = 0.0
        self.save()

    def buy(self, symbol: str, amount_eur: float, current_price: float, reason: str = "") -> Optional[Dict]:
        """Ejecuta una compra con validación institucional de filtros de exchange."""
        if amount_eur > self.cash:
            amount_eur = self.cash

        # Control institucional de MIN_NOTIONAL de exchange
        is_valid, adjusted_qty, err_msg = BinanceRulesEngine.validate_buy_order(symbol, amount_eur, current_price)
        if not is_valid:
            print(f"[{self.environment.upper()}]: Compra rechazada para {symbol}: {err_msg}")
            return None

        fee_eur = round(amount_eur * self.fee_rate, 4)
        net_invested_eur = amount_eur - fee_eur
        quantity = net_invested_eur / current_price

        self.cash -= amount_eur
        self.total_fees_paid += fee_eur

        # Actualizar posición
        pos = self.positions.get(symbol, {
            "amount": 0.0,
            "avg_entry_price": 0.0,
            "total_cost_eur": 0.0,
            "dca_count": 0,
            "first_buy_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        new_total_amount = pos["amount"] + quantity
        new_total_cost = pos["total_cost_eur"] + amount_eur
        new_avg_price = (pos["amount"] * pos["avg_entry_price"] + quantity * current_price) / new_total_amount

        pos["amount"] = new_total_amount
        pos["avg_entry_price"] = new_avg_price
        pos["total_cost_eur"] = new_total_cost
        pos["dca_count"] += 1
        pos["last_buy_price"] = current_price

        self.positions[symbol] = pos

        trade = {
            "id": len(self.trades) + 1,
            "environment": self.environment,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "side": "BUY",
            "price": current_price,
            "quantity": quantity,
            "amount_eur": amount_eur,
            "fee_eur": fee_eur,
            "realized_pnl_eur": 0.0,
            "reason": reason
        }
        self.trades.insert(0, trade)
        self.save()
        return trade

    def sell(self, symbol: str, current_price: float, reason: str = "", sell_pct: float = 1.0, sweep_pct: Optional[float] = None) -> Optional[Dict]:
        """Ejecuta una venta ajustando al stepSize de Binance para evitar errores por polvo (dust)."""
        pos = self.positions.get(symbol)
        if not pos or pos["amount"] <= 0:
            return None

        raw_sell_amount = pos["amount"] * sell_pct

        # Ajuste por stepSize de Binance (redondeo hacia abajo para evitar balance insuficiente)
        is_valid, sell_amount, err_msg = BinanceRulesEngine.adjust_quantity_for_sell(symbol, raw_sell_amount, current_price)
        if not is_valid:
            sell_amount = raw_sell_amount

        gross_eur = sell_amount * current_price
        fee_eur = round(gross_eur * self.fee_rate, 4)
        net_eur = gross_eur - fee_eur

        # Coste proporcional
        cost_basis = pos["total_cost_eur"] * (sell_amount / pos["amount"]) if pos["amount"] > 0 else pos["total_cost_eur"]
        trade_pnl = net_eur - cost_basis

        # Si hay ganancia, desviar el % configurado a la Bóveda MSCI World
        swept_to_msci = 0.0
        if sweep_pct is None:
            from .config import CONFIG
            sweep_pct = CONFIG.get("msci_sweep_pct", 0.0)

        if trade_pnl > 0 and sweep_pct > 0:
            swept_to_msci = round(trade_pnl * (sweep_pct / 100.0), 4)
            self.msci_vault_eur += swept_to_msci
            self.cash += (net_eur - swept_to_msci)
        else:
            self.cash += net_eur

        self.total_fees_paid += fee_eur
        self.realized_pnl += trade_pnl

        # Actualizar o liquidar la posición (eliminando cualquier resto considerado polvo)
        remaining_amount = pos["amount"] - sell_amount
        rule = BinanceRulesEngine.get_rule(symbol)
        min_qty = rule.get("min_qty", 1e-5)
        if remaining_amount < min_qty or sell_pct >= 0.999:
            if symbol in self.positions:
                del self.positions[symbol]
        else:
            pos["amount"] = remaining_amount
            pos["total_cost_eur"] = max(0.0, pos["total_cost_eur"] - cost_basis)
            self.positions[symbol] = pos

        trade = {
            "id": len(self.trades) + 1,
            "environment": self.environment,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "side": "SELL",
            "price": current_price,
            "quantity": sell_amount,
            "amount_eur": round(net_eur, 4),
            "fee_eur": fee_eur,
            "realized_pnl_eur": round(trade_pnl, 4),
            "swept_to_msci_eur": swept_to_msci,
            "pnl_pct": round((trade_pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0.0,
            "reason": reason
        }
        self.trades.insert(0, trade)
        self.save()
        return trade

    def get_summary(self, current_prices: Dict[str, float]) -> Dict:
        """Calcula el estado consolidado de la cuenta, P&L no realizado, y métricas."""
        positions_value = 0.0
        positions_detail = []

        for sym, pos in self.positions.items():
            curr_p = current_prices.get(sym, 0.0)
            if not curr_p or curr_p <= 0:
                curr_p = pos.get("avg_entry_price", 0.0)
            val = pos["amount"] * curr_p
            positions_value += val
            cost = pos["total_cost_eur"]
            unrealized = val - cost
            unrealized_pct = (unrealized / cost * 100) if cost > 0 else 0.0

            positions_detail.append({
                "symbol": sym,
                "amount": pos["amount"],
                "avg_entry_price": round(pos["avg_entry_price"], 4),
                "current_price": round(curr_p, 4),
                "total_cost_eur": round(cost, 4),
                "current_value_eur": round(val, 4),
                "unrealized_pnl_eur": round(unrealized, 4),
                "unrealized_pnl_pct": round(unrealized_pct, 2),
                "dca_count": pos.get("dca_count", 1)
            })

        total_portfolio_value = self.cash + positions_value + self.msci_vault_eur
        net_profit_eur = total_portfolio_value - self.initial_capital
        net_profit_pct = (net_profit_eur / self.initial_capital * 100) if self.initial_capital > 0 else 0.0

        msci_proj_5yr = round(self.msci_vault_eur * ((1 + 0.08) ** 5), 2)
        msci_proj_10yr = round(self.msci_vault_eur * ((1 + 0.08) ** 10), 2)

        sells = [t for t in self.trades if t.get("side") == "SELL"]
        winning_trades = [t for t in sells if t.get("realized_pnl_eur", 0) > 0]
        losing_trades = [t for t in sells if t.get("realized_pnl_eur", 0) < 0]
        win_rate = (len(winning_trades) / len(sells) * 100) if sells else 0.0

        return {
            "environment": self.environment,
            "initial_capital_eur": self.initial_capital,
            "cash_eur": round(self.cash, 4),
            "positions_value_eur": round(positions_value, 4),
            "msci_vault_eur": round(self.msci_vault_eur, 4),
            "msci_proj_5yr": msci_proj_5yr,
            "msci_proj_10yr": msci_proj_10yr,
            "total_value_eur": round(total_portfolio_value, 4),
            "net_profit_eur": round(net_profit_eur, 4),
            "net_profit_pct": round(net_profit_pct, 2),
            "realized_pnl_eur": round(self.realized_pnl, 4),
            "total_fees_paid_eur": round(self.total_fees_paid, 4),
            "open_positions_count": len(self.positions),
            "total_trades_count": len(self.trades),
            "closed_trades_count": len(sells),
            "win_rate_pct": round(win_rate, 1),
            "positions": positions_detail,
            "recent_trades": self.trades[:50]
        }
