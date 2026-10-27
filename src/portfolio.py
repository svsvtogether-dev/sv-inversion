import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from .config import INITIAL_CAPITAL_EUR, TRADING_FEE_RATE, PORTFOLIO_FILE

class Portfolio:
    def __init__(self, storage_path: Path = PORTFOLIO_FILE):
        self.storage_path = storage_path
        self.initial_capital = INITIAL_CAPITAL_EUR
        self.fee_rate = TRADING_FEE_RATE
        self.cash = self.initial_capital
        self.positions: Dict[str, Dict] = {}  # symbol -> {amount, avg_entry_price, total_cost_eur, dca_count, first_buy_time}
        self.trades: List[Dict] = []
        self.total_fees_paid = 0.0
        self.realized_pnl = 0.0
        self.msci_vault_eur = 0.0  # Bóveda de ahorro a largo plazo en Fondo Indexado MSCI World
        self.load()

    def load(self):
        """Carga el estado del portafolio desde el archivo JSON si existe."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.initial_capital = data.get("initial_capital", INITIAL_CAPITAL_EUR)
                    self.fee_rate = data.get("fee_rate", TRADING_FEE_RATE)
                    self.cash = float(data.get("cash", self.initial_capital))
                    self.positions = data.get("positions", {})
                    self.trades = data.get("trades", [])
                    self.total_fees_paid = float(data.get("total_fees_paid", 0.0))
                    self.realized_pnl = float(data.get("realized_pnl", 0.0))
                    self.msci_vault_eur = float(data.get("msci_vault_eur", 0.0))
                    return
            except Exception as e:
                print(f"[Aviso] No se pudo cargar el archivo de portafolio: {e}. Se inicializará uno nuevo.")

        self.save()

    def save(self):
        """Guarda el estado actual en el archivo JSON."""
        data = {
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
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Error] Fallo al guardar portafolio: {e}")

    def reset(self, new_capital: Optional[float] = None):
        """Reinicia la cuenta virtual a los 30 € iniciales."""
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
        """Ejecuta una compra virtual descontando comisiones y ajustando precio medio (DCA)."""
        if amount_eur > self.cash:
            amount_eur = self.cash  # Usa el máximo disponible si es menor

        if amount_eur < 1.0:  # Mínimo para poder ejecutar
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

    def sell(self, symbol: str, current_price: float, reason: str = "", sell_pct: float = 1.0) -> Optional[Dict]:
        """Ejecuta una venta virtual de la posición abierta."""
        pos = self.positions.get(symbol)
        if not pos or pos["amount"] <= 0:
            return None

        sell_amount = pos["amount"] * sell_pct
        gross_eur = sell_amount * current_price
        fee_eur = round(gross_eur * self.fee_rate, 4)
        net_eur = gross_eur - fee_eur

        # Coste proporcional
        cost_basis = pos["total_cost_eur"] * sell_pct
        trade_pnl = net_eur - cost_basis

        # Si hay ganancia, desviar el % configurado (ej: 50%) a la Bóveda de Ahorro MSCI World
        swept_to_msci = 0.0
        from .config import CONFIG
        sweep_pct = CONFIG.get("msci_sweep_pct", 50.0)

        if trade_pnl > 0 and sweep_pct > 0:
            swept_to_msci = round(trade_pnl * (sweep_pct / 100.0), 4)
            self.msci_vault_eur += swept_to_msci
            self.cash += (net_eur - swept_to_msci)
        else:
            self.cash += net_eur

        self.total_fees_paid += fee_eur
        self.realized_pnl += trade_pnl

        # Actualizar o eliminar la posición
        remaining_amount = pos["amount"] - sell_amount
        if remaining_amount <= 1e-8 or sell_pct >= 0.999:
            del self.positions[symbol]
        else:
            pos["amount"] = remaining_amount
            pos["total_cost_eur"] -= cost_basis
            self.positions[symbol] = pos

        trade = {
            "id": len(self.trades) + 1,
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
            curr_p = current_prices.get(sym, pos.get("avg_entry_price", 0.0))
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

        # Proyección compuesta del MSCI World a 8% anualizado
        msci_proj_5yr = round(self.msci_vault_eur * ((1 + 0.08) ** 5), 2)
        msci_proj_10yr = round(self.msci_vault_eur * ((1 + 0.08) ** 10), 2)

        # Métricas de acierto (Win rate)
        sells = [t for t in self.trades if t["side"] == "SELL"]
        winning_trades = [t for t in sells if t.get("realized_pnl_eur", 0) > 0]
        losing_trades = [t for t in sells if t.get("realized_pnl_eur", 0) < 0]
        win_rate = (len(winning_trades) / len(sells) * 100) if sells else 0.0

        return {
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
            "recent_trades": self.trades[:15]
        }
