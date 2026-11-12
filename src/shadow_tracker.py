import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class ShadowTracker:
    """
    👻 Registro Contrafactual de Vetos (Shadow Ledger)
    Cada vez que TradingCouncil / Risk Manager veta o bloquea una señal alcista relevante,
    registra una operación virtual y la sigue con precios reales en vivo para medir con datos
    si el veto nos salvó de una pérdida (SAVED_LOSS) o nos privó de una ganancia (MISSED_WIN).
    """

    def __init__(self, data_dir: Path, max_history: int = 100):
        self.data_dir = Path(data_dir)
        self.storage_file = self.data_dir / "shadow_ledger.json"
        self.max_history = max_history
        self.records: List[Dict] = []
        self._load()

    def _load(self):
        try:
            if self.storage_file.exists():
                data = json.loads(self.storage_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.records = data[-self.max_history :]
        except Exception:
            self.records = []

    def _save(self):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.storage_file.write_text(
                json.dumps(self.records[-self.max_history :], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def record_veto(
        self,
        symbol: str,
        price: float,
        debate: Dict,
        tp_pct: float = 6.0,
        sl_pct: float = -4.5,
    ) -> bool:
        """Registra una operación fantasma si fue vetada o bloqueada teniendo tracción alcista."""
        if price <= 0 or not debate or debate.get("approved"):
            return False

        decision = debate.get("decision", "HOLD")
        bull_score = float(debate.get("bull_score", 0.0))
        if decision != "VETO" and bull_score < 40.0:
            return False

        now = time.time()
        # Evitar duplicados para el mismo símbolo si ya hay uno abierto o recién cerrado (< 30 min)
        for rec in self.records:
            if rec.get("symbol") == symbol:
                if rec.get("status") == "OPEN" or (now - float(rec.get("ts", 0.0)) < 1800.0):
                    return False

        tp_price = price * (1.0 + abs(tp_pct) / 100.0)
        sl_price = price * (1.0 - abs(sl_pct) / 100.0)
        reason = debate.get("risk_verdict") or debate.get("summary", "Bloqueado")

        entry = {
            "id": int(now * 1000),
            "ts": now,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "strategy_tag": debate.get("strategy_tag", "DCA_REVERSION"),
            "entry_price": round(price, 6),
            "tp_price": round(tp_price, 6),
            "sl_price": round(sl_price, 6),
            "bull_score": round(bull_score, 1),
            "bear_score": round(float(debate.get("bear_score", 0.0)), 1),
            "veto_reason": reason,
            "status": "OPEN",
            "close_price": None,
            "hypothetical_pnl_pct": 0.0,
        }
        self.records.append(entry)
        if len(self.records) > self.max_history:
            self.records = self.records[-self.max_history :]
        self._save()
        return True

    def update_with_analyses(self, analyses: Dict[str, Dict], max_age_seconds: float = 172800.0):
        """Evalúa las operaciones fantasma abiertas frente a los precios actuales."""
        if not analyses or not self.records:
            return

        now = time.time()
        changed = False
        for rec in self.records:
            if rec.get("status") != "OPEN":
                continue
            sym = rec.get("symbol")
            an = analyses.get(sym)
            if not an:
                continue
            price = float(an.get("price", 0.0))
            if price <= 0:
                continue

            entry_p = float(rec.get("entry_price", 0.0))
            if entry_p <= 0:
                continue

            pnl_pct = ((price - entry_p) / entry_p) * 100.0
            rec["hypothetical_pnl_pct"] = round(pnl_pct, 2)

            if price <= float(rec["sl_price"]):
                rec["status"] = "SAVED_LOSS"
                rec["close_price"] = round(price, 6)
                changed = True
            elif price >= float(rec["tp_price"]):
                rec["status"] = "MISSED_WIN"
                rec["close_price"] = round(price, 6)
                changed = True
            elif (now - float(rec.get("ts", now))) >= max_age_seconds:
                rec["status"] = "SAVED_LOSS" if pnl_pct < 0 else "MISSED_WIN"
                rec["close_price"] = round(price, 6)
                changed = True

        if changed:
            self._save()

    def get_summary(self) -> Dict:
        open_recs = [r for r in self.records if r.get("status") == "OPEN"]
        saved = [r for r in self.records if r.get("status") == "SAVED_LOSS"]
        missed = [r for r in self.records if r.get("status") == "MISSED_WIN"]
        decided = len(saved) + len(missed)
        accuracy = round((len(saved) / decided) * 100.0, 1) if decided > 0 else 0.0
        # Impacto neto estimado de los vetos: pérdidas evitadas (en positivo) - ganancias perdidas
        net_impact_pct = round(
            sum(-float(r.get("hypothetical_pnl_pct", 0.0)) for r in saved)
            - sum(float(r.get("hypothetical_pnl_pct", 0.0)) for r in missed),
            2,
        )
        return {
            "open_count": len(open_recs),
            "closed_count": decided,
            "saved_losses": len(saved),
            "missed_wins": len(missed),
            "filter_accuracy_pct": accuracy,
            "net_saved_pct": net_impact_pct,
            "recent": self.records[-5:][::-1],
        }
