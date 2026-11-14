from typing import Dict, Optional
from .signals import evaluate_breakout_entry_signal


class TradingCouncil:
    """
    Evaluador determinista de entradas (TREND_BREAKOUT en BTCEUR).
    Delega la lógica de señales a src/signals.py (fuente única de verdad).
    """

    def debate_multi_strategy(
        self,
        symbol: str,
        analysis: Dict,
        cash: float,
        config: Dict,
        tier: str = "NORMAL",
        open_positions_count: int = 0,
        btc_healthy: bool = True,
        pair_cooldown_active: bool = False,
        recent_memory: Optional[Dict] = None,
    ) -> Dict:
        regime_name = analysis.get("regime", {}).get("regime", "RANGING")

        if pair_cooldown_active:
            return {
                "approved": False,
                "decision": "VETO",
                "strategy_tag": "COOLDOWN_GUARD",
                "regime": regime_name,
                "bull_score": 0.0,
                "bear_score": 100.0,
                "net_score": -100.0,
                "min_required": 100.0,
                "bull_arguments": [],
                "bear_objections": [f"VETO StoplossGuard/Cooldown activo en {symbol}: evitando revenge trading"],
                "risk_verdict": f"COOLDOWN ACTIVO ({symbol})",
                "summary": f"❄️ StoplossGuard/Cooldown bloquea re-entrada en {symbol}",
            }

        res = evaluate_breakout_entry_signal(
            symbol=symbol,
            analysis=analysis,
            open_positions_count=open_positions_count,
            donchian_period=int(config.get("breakout_donchian_period", 20)),
            volume_min_ratio=float(config.get("breakout_volume_min_ratio", 1.1)),
        )

        if recent_memory and int(recent_memory.get("consecutive_losses", 0)) >= 3 and res.get("approved"):
            res["approved"] = False
            res["decision"] = "HOLD"
            res["bear_score"] = round(res["bear_score"] + 20.0, 1)
            res["net_score"] = round(res["bull_score"] - res["bear_score"], 1)
            res["bear_objections"].append("Memoria de errores: 3+ pérdidas seguidas recientes")
            res["risk_verdict"] = "BLOQUEADO POR MEMORIA"

        return res
