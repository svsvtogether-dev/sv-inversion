import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR, FROZEN_CONFIG_HASH, FROZEN_EXPERIMENT
from .signals import evaluate_daily_sma200_signal


def _max_drawdown_pct(series: List[float]) -> float:
    if not series:
        return 0.0
    peak = series[0]
    max_dd = 0.0
    for val in series:
        if val > peak:
            peak = val
        if peak > 0:
            dd = ((peak - val) / peak) * 100.0
            if dd > max_dd:
                max_dd = dd
    return max_dd


def run_daily_sma200_replica(
    daily_candles: List[Dict],
    start_idx: int,
    end_idx: int,
    initial_eur: float = 50.0,
    monthly_deposit_eur: float = 0.0,
    cost_rate: float = 0.0015,
) -> Dict:
    """
    Réplica exacta usando src/signals.py (evaluate_daily_sma200_signal).
    Señal calculada al cierre del día i; ejecución en el open del día i+1.
    """
    closes = [c["close"] for c in daily_candles]
    cash = initial_eur
    contributed = initial_eur
    qty = 0.0
    entry_price = 0.0
    pending = "HOLD"
    peak = initial_eur
    max_dd = 0.0
    days_in_market = 0
    trades: List[Dict] = []

    last_dep_ts = daily_candles[start_idx]["timestamp"]
    ms_30d = 30 * 24 * 3600 * 1000

    for i in range(start_idx, end_idx):
        c = daily_candles[i]
        if monthly_deposit_eur > 0 and i > start_idx and (c["timestamp"] - last_dep_ts) >= ms_30d:
            cash += monthly_deposit_eur
            contributed += monthly_deposit_eur
            peak += monthly_deposit_eur
            last_dep_ts += ms_30d

        if pending == "BUY" and qty == 0.0 and cash > 1.0:
            exec_p = c["open"]
            qty = (cash * (1.0 - cost_rate)) / exec_p
            entry_price = exec_p
            cash = 0.0
            pending = "HOLD"
        elif pending == "SELL" and qty > 0.0:
            exec_p = c["open"]
            net_eur = qty * exec_p * (1.0 - cost_rate)
            pnl_eur = net_eur - (qty * entry_price / (1.0 - cost_rate))
            trades.append({"pnl_eur": pnl_eur})
            cash += net_eur
            qty = 0.0
            entry_price = 0.0
            pending = "HOLD"

        if qty > 0.0 and cash > 1.0:
            qty += (cash * (1.0 - cost_rate)) / c["open"]
            cash = 0.0

        if qty > 0.0:
            days_in_market += 1

        eq = cash + qty * c["close"]
        if eq > peak:
            peak = eq
        dd = ((peak - eq) / peak * 100.0) if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

        if i + 1 >= end_idx or i < 199:
            continue
        sma200 = sum(closes[i - 199 : i + 1]) / 200.0
        sig = evaluate_daily_sma200_signal(c["close"], sma200, in_position=(qty > 0.0))
        if sig in ("BUY", "SELL"):
            pending = sig

    final_eur = cash + qty * daily_candles[end_idx - 1]["close"]
    wins = [t for t in trades if t["pnl_eur"] > 0]
    losses = [t for t in trades if t["pnl_eur"] <= 0]
    gw = sum(t["pnl_eur"] for t in wins)
    gl = abs(sum(t["pnl_eur"] for t in losses))
    pf = (gw / gl) if gl > 0 else (99.0 if gw > 0 else 0.0)
    total_days = max(1, end_idx - start_idx)
    return {
        "final_eur": final_eur,
        "contributed_eur": contributed,
        "ret_pct": ((final_eur - contributed) / contributed) * 100.0,
        "max_dd_pct": max_dd,
        "trades": len(trades),
        "pf": pf,
        "days_in_market": days_in_market,
        "total_days": total_days,
    }


class ExperimentTracker:
    """
    Registro diario (00:05 UTC), resumen semanal e informe final 2027-05-14
    para el experimento congelado v1.0-frozen.
    """

    CSV_FIELDS = [
        "fecha",
        "cierre",
        "sma200",
        "senal",
        "posicion",
        "equity_bot_eur",
        "ref_buy_hold_eur",
        "ref_dca_20_eur",
        "ref_efectivo_eur",
    ]

    def __init__(self, data_dir: Path = DATA_DIR, initial_eur: float = 50.0, cost_rate: float = 0.0015):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.initial_eur = float(initial_eur)
        self.cost_rate = float(cost_rate)

        self.csv_path = self.data_dir / "experiment_daily.csv"
        self.state_path = self.data_dir / "experiment_state.json"
        self.weekly_path = self.data_dir / "weekly_summary.md"
        self.final_report_path = self.data_dir / "final_report_2027-05-14.md"

        self.state = self._load_state()
        self._ensure_csv_header()

    def _default_state(self) -> Dict:
        return {
            "version": FROZEN_EXPERIMENT["version"],
            "config_hash": FROZEN_CONFIG_HASH,
            "start_date": FROZEN_EXPERIMENT["start_date"],
            "review_date": FROZEN_EXPERIMENT["review_date"],
            "bot_cash_eur": self.initial_eur,
            "bot_btc_qty": 0.0,
            "pending_signal": "HOLD",
            "pending_signal_date": None,
            "signals_evaluated": 0,
            "signals_executed_next_open": 0,
            "trades_closed": 0,
            "last_entry_price": 0.0,
            "ref_bh_btc_qty": 0.0,
            "ref_dca_btc_qty": 0.0,
            "ref_dca_contributed_eur": self.initial_eur,
            "ref_dca_last_deposit_date": None,
            "ref_cash_eur": self.initial_eur,
            "last_recorded_date": None,
        }

    def _load_state(self) -> Dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self._default_state()

    def _save_state(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _ensure_csv_header(self) -> None:
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=self.CSV_FIELDS).writeheader()

    def _read_rows(self) -> List[Dict]:
        if not self.csv_path.exists():
            return []
        with open(self.csv_path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def process_daily_bar(self, date_str: str, open_price: float, close_price: float, sma_200: float) -> Optional[Dict]:
        """
        Procesa 1 vela diaria cerrada (a las >= 00:05 UTC):
        1. Ejecuta cualquier señal pendiente del día anterior al open_price de hoy.
        2. Actualiza referencias (Buy & Hold, DCA 20€/mes, Efectivo).
        3. Calcula la señal de hoy al cierre (close_price vs sma_200) para el open de mañana.
        4. Guarda en data/experiment_daily.csv sin duplicar fechas.
        """
        existing = self._read_rows()
        if any(r.get("fecha") == date_str for r in existing):
            return None

        # Inicializar referencias en el primer día registrado
        if self.state["ref_bh_btc_qty"] == 0.0 and open_price > 0:
            self.state["ref_bh_btc_qty"] = (self.initial_eur * (1.0 - self.cost_rate)) / open_price
            self.state["ref_dca_btc_qty"] = (self.initial_eur * (1.0 - self.cost_rate)) / open_price
            self.state["ref_dca_last_deposit_date"] = date_str
        else:
            # Aportación DCA 20 EUR cada 30 días desde el último depósito
            last_dep = self.state.get("ref_dca_last_deposit_date")
            if last_dep and open_price > 0:
                d_now = datetime.strptime(date_str, "%Y-%m-%d")
                d_prev = datetime.strptime(last_dep, "%Y-%m-%d")
                if (d_now - d_prev).days >= 30:
                    self.state["ref_dca_btc_qty"] += (20.0 * (1.0 - self.cost_rate)) / open_price
                    self.state["ref_dca_contributed_eur"] += 20.0
                    self.state["ref_dca_last_deposit_date"] = date_str

        # Ejecutar señal pendiente del día anterior en el OPEN de hoy
        pending = self.state.get("pending_signal", "HOLD")
        if pending == "BUY" and self.state["bot_btc_qty"] == 0.0 and self.state["bot_cash_eur"] > 1.0:
            self.state["bot_btc_qty"] = (self.state["bot_cash_eur"] * (1.0 - self.cost_rate)) / open_price
            self.state["bot_cash_eur"] = 0.0
            self.state["last_entry_price"] = open_price
            self.state["signals_executed_next_open"] += 1
        elif pending == "SELL" and self.state["bot_btc_qty"] > 0.0:
            self.state["bot_cash_eur"] += self.state["bot_btc_qty"] * open_price * (1.0 - self.cost_rate)
            self.state["bot_btc_qty"] = 0.0
            self.state["trades_closed"] += 1
            self.state["signals_executed_next_open"] += 1
        self.state["pending_signal"] = "HOLD"

        # Evaluar señal al cierre de hoy para ejecutar en la apertura de mañana
        in_pos = self.state["bot_btc_qty"] > 0.0
        signal = evaluate_daily_sma200_signal(close_price, sma_200, in_position=in_pos)
        if signal in ("BUY", "SELL"):
            self.state["pending_signal"] = signal
            self.state["pending_signal_date"] = date_str
            self.state["signals_evaluated"] += 1

        eq_bot = self.state["bot_cash_eur"] + self.state["bot_btc_qty"] * close_price
        eq_bh = self.state["ref_bh_btc_qty"] * close_price
        eq_dca = self.state["ref_dca_btc_qty"] * close_price
        eq_cash = self.state["ref_cash_eur"]

        row = {
            "fecha": date_str,
            "cierre": f"{close_price:.2f}",
            "sma200": f"{sma_200:.2f}",
            "senal": signal,
            "posicion": "BTC" if in_pos else "EUR",
            "equity_bot_eur": f"{eq_bot:.4f}",
            "ref_buy_hold_eur": f"{eq_bh:.4f}",
            "ref_dca_20_eur": f"{eq_dca:.4f}",
            "ref_efectivo_eur": f"{eq_cash:.4f}",
        }

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=self.CSV_FIELDS).writerow(row)

        self.state["last_recorded_date"] = date_str
        self._save_state()

        total_rows = len(existing) + 1
        if total_rows % 7 == 0 or total_rows == 1:
            self.generate_weekly_summary()
        if date_str >= FROZEN_EXPERIMENT["review_date"]:
            self.generate_final_report()

        return row

    def generate_weekly_summary(self) -> Path:
        rows = self._read_rows()
        if not rows:
            self.weekly_path.write_text("# Resumen Semanal v1.0-frozen\n\nSin datos aún.\n", encoding="utf-8")
            return self.weekly_path

        bot_s = [float(r["equity_bot_eur"]) for r in rows]
        bh_s = [float(r["ref_buy_hold_eur"]) for r in rows]
        dca_s = [float(r["ref_dca_20_eur"]) for r in rows]
        cash_s = [float(r["ref_efectivo_eur"]) for r in rows]

        dca_contrib = self.state.get("ref_dca_contributed_eur", self.initial_eur)
        bot_ret = ((bot_s[-1] - self.initial_eur) / self.initial_eur) * 100.0
        bh_ret = ((bh_s[-1] - self.initial_eur) / self.initial_eur) * 100.0
        dca_ret = ((dca_s[-1] - dca_contrib) / dca_contrib) * 100.0
        cash_ret = ((cash_s[-1] - self.initial_eur) / self.initial_eur) * 100.0

        md = (
            f"# Resumen Semanal — Experimento Congelado {FROZEN_EXPERIMENT['version']}\n\n"
            f"- **Periodo registrado:** `{rows[0]['fecha']}` → `{rows[-1]['fecha']}` ({len(rows)} días)\n"
            f"- **Hash config:** `{FROZEN_CONFIG_HASH}`\n"
            f"- **Operaciones cerradas (bot):** `{self.state.get('trades_closed', 0)}`\n\n"
            f"| Serie | Equity actual | Retorno | Max Drawdown |\n"
            f"| :--- | :---: | :---: | :---: |\n"
            f"| **Bot (`Close > SMA200`)** | `{bot_s[-1]:.2f} €` | `{bot_ret:+.2f}%` | `{_max_drawdown_pct(bot_s):.2f}%` |\n"
            f"| Buy & Hold `BTCEUR` | `{bh_s[-1]:.2f} €` | `{bh_ret:+.2f}%` | `{_max_drawdown_pct(bh_s):.2f}%` |\n"
            f"| DCA `20 €/mes` (aportado `{dca_contrib:.0f} €`) | `{dca_s[-1]:.2f} €` | `{dca_ret:+.2f}%` | `{_max_drawdown_pct(dca_s):.2f}%` |\n"
            f"| Efectivo (`EUR`) | `{cash_s[-1]:.2f} €` | `{cash_ret:+.2f}%` | `{_max_drawdown_pct(cash_s):.2f}%` |\n"
        )
        self.weekly_path.write_text(md, encoding="utf-8")
        return self.weekly_path

    def generate_final_report(self) -> Path:
        rows = self._read_rows()
        if not rows:
            self.final_report_path.write_text("# Informe Final 2027-05-14\n\nSin datos.\n", encoding="utf-8")
            return self.final_report_path

        bot_s = [float(r["equity_bot_eur"]) for r in rows]
        bh_s = [float(r["ref_buy_hold_eur"]) for r in rows]
        dca_s = [float(r["ref_dca_20_eur"]) for r in rows]

        dd_bot = _max_drawdown_pct(bot_s)
        dd_bh = _max_drawdown_pct(bh_s)
        c2_limit = 0.60 * dd_bh
        c2_pass = dd_bot <= c2_limit

        sig_eval = self.state.get("signals_evaluated", 0)
        sig_exec = self.state.get("signals_executed_next_open", 0)
        pending_now = 1 if self.state.get("pending_signal", "HOLD") in ("BUY", "SELL") else 0
        c1_pass = (sig_exec + pending_now) == sig_eval

        trades_closed = self.state.get("trades_closed", 0)
        dca_contrib = self.state.get("ref_dca_contributed_eur", self.initial_eur)
        bot_ret = ((bot_s[-1] - self.initial_eur) / self.initial_eur) * 100.0
        bh_ret = ((bh_s[-1] - self.initial_eur) / self.initial_eur) * 100.0
        dca_ret = ((dca_s[-1] - dca_contrib) / dca_contrib) * 100.0

        c3_note = (
            "MUESTRA INSUFICIENTE (< 10 operaciones cerradas): NO es evidencia estadística de ventaja."
            if trades_closed < 10
            else f"Muestra de {trades_closed} operaciones cerradas."
        )

        md = (
            f"# Informe Final del Experimento ({FROZEN_EXPERIMENT['start_date']} → {FROZEN_EXPERIMENT['review_date']})\n\n"
            f"- **Versión:** `{FROZEN_EXPERIMENT['version']}` | **Hash:** `{FROZEN_CONFIG_HASH}`\n"
            f"- **Días registrados:** `{len(rows)}` (`{rows[0]['fecha']}` → `{rows[-1]['fecha']}`)\n\n"
            f"## Criterios de Éxito (fijados al inicio)\n"
            f"- **C1 (Funcionamiento):** {'CUMPLE' if c1_pass else 'NO CUMPLE'} — "
            f"Señales evaluadas: `{sig_eval}`, ejecutadas en apertura siguiente: `{sig_exec}` (pendientes hoy: `{pending_now}`).\n"
            f"- **C2 (Riesgo):** {'CUMPLE' if c2_pass else 'NO CUMPLE'} — "
            f"MaxDD Bot `{dd_bot:.2f}%` vs límite 60% de Buy & Hold (`{c2_limit:.2f}%`, siendo MaxDD B&H `{dd_bh:.2f}%`).\n"
            f"- **C3 (Informativo):** Bot `{bot_ret:+.2f}%` (`{bot_s[-1]:.2f} €`) | "
            f"Buy & Hold `{bh_ret:+.2f}%` (`{bh_s[-1]:.2f} €`) | "
            f"DCA 20 €/mes `{dca_ret:+.2f}%` (`{dca_s[-1]:.2f} €` sobre `{dca_contrib:.0f} €`).\n"
            f"  - Nota metodológica: {c3_note}\n"
        )
        self.final_report_path.write_text(md, encoding="utf-8")
        return self.final_report_path
