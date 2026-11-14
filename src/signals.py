from typing import Dict, List, Tuple


def evaluate_breakout_entry_signal(
    symbol: str,
    analysis: Dict,
    open_positions_count: int = 0,
    donchian_period: int = 20,
    volume_min_ratio: float = 1.1,
) -> Dict:
    """
    Fuente única de verdad para señales de entrada (TREND_BREAKOUT en BTCEUR, 4h, long-only).
    Usada tanto por el bot en vivo como por el backtester.
    """
    regime_info = analysis.get("regime", {})
    regime_name = regime_info.get("regime", "RANGING")
    vol_z = float(regime_info.get("vol_zscore", 0.0))
    news_status = analysis.get("news_status", {})

    if news_status.get("is_shield_active"):
        act_ev = news_status.get("active_event", {})
        title = act_ev.get("title", "Noticia Alto Impacto")
        return {
            "approved": False,
            "decision": "VETO",
            "strategy_tag": "TREND_BREAKOUT",
            "regime": regime_name,
            "bull_score": 0.0,
            "bear_score": 100.0,
            "net_score": -100.0,
            "min_required": 100.0,
            "bull_arguments": [],
            "bear_objections": [f"VETO News Shield: '{title}'"],
            "risk_verdict": f"VETO POR NOTICIA ({title})",
            "summary": f"🛡️ News Shield veta {symbol}: {title}",
        }

    if regime_name == "HIGH_VOLATILITY_SHOCK":
        return {
            "approved": False,
            "decision": "VETO",
            "strategy_tag": "SHOCK_GUARD",
            "regime": regime_name,
            "bull_score": 0.0,
            "bear_score": 100.0,
            "net_score": -100.0,
            "min_required": 100.0,
            "bull_arguments": [],
            "bear_objections": [f"VETO Shock de volatilidad (Vol Z={vol_z:.2f})"],
            "risk_verdict": f"VETO POR SHOCK VOLATILIDAD (Z={vol_z:.2f})",
            "summary": f"⚡ Risk Manager veta {symbol}: Shock de volatilidad (Z={vol_z:.2f})",
        }

    if symbol != "BTCEUR":
        return {
            "approved": False,
            "decision": "HOLD",
            "strategy_tag": "TREND_BREAKOUT",
            "regime": regime_name,
            "bull_score": 0.0,
            "bear_score": 100.0,
            "net_score": -100.0,
            "min_required": 100.0,
            "bull_arguments": [],
            "bear_objections": [f"Solo opera BTCEUR ({symbol} en espera)"],
            "risk_verdict": "PAR EN OBSERVACIÓN",
            "summary": f"⏸️ {symbol} en espera: solo opera BTCEUR",
        }

    if open_positions_count >= 1:
        return {
            "approved": False,
            "decision": "HOLD",
            "strategy_tag": "TREND_BREAKOUT",
            "regime": regime_name,
            "bull_score": 0.0,
            "bear_score": 100.0,
            "net_score": -100.0,
            "min_required": 100.0,
            "bull_arguments": [],
            "bear_objections": ["Máximo 1 posición abierta a la vez"],
            "risk_verdict": "POSICIÓN ACTIVA",
            "summary": "⏸️ Ya hay 1 posición abierta",
        }

    price = float(analysis.get("price", 0.0))
    ema_trend = float(analysis.get("ema_trend", 0.0))
    ema_200 = float(analysis.get("ema_200", 0.0))
    donchian_key = f"donchian_high_{donchian_period}"
    donchian_high = float(analysis.get(donchian_key, analysis.get("donchian_high_20", 0.0)))
    hma_slope = analysis.get("hma_50_slope", "FLAT")
    volume_ratio = float(analysis.get("volume_ratio", 1.0))

    if price <= 0 or ema_200 <= 0 or donchian_high <= 0:
        return {
            "approved": False,
            "decision": "HOLD",
            "strategy_tag": "TREND_BREAKOUT",
            "regime": regime_name,
            "bull_score": 0.0,
            "bear_score": 100.0,
            "net_score": -100.0,
            "min_required": 100.0,
            "bull_arguments": [],
            "bear_objections": ["Datos insuficientes de EMA 200 / Donchian"],
            "risk_verdict": "SIN DATOS",
            "summary": f"⏸️ Datos insuficientes en {symbol}",
        }

    checks: List[Tuple[bool, str, str]] = [
        (price > ema_200, f"Precio sobre EMA 200 (€{price:.0f} > €{ema_200:.0f})", f"Bajo EMA 200 (€{price:.0f} <= €{ema_200:.0f})"),
        (ema_trend >= ema_200, f"EMA 50 >= EMA 200 (€{ema_trend:.0f} >= €{ema_200:.0f})", f"EMA 50 < EMA 200 (€{ema_trend:.0f} < €{ema_200:.0f})"),
        (price > donchian_high, f"Ruptura Donchian {donchian_period} (€{price:.0f} > €{donchian_high:.0f})", f"Sin ruptura Donchian {donchian_period} (€{price:.0f} <= €{donchian_high:.0f})"),
        (hma_slope == "UP", "HMA 50 en pendiente alcista", f"HMA 50 no alcista ({hma_slope})"),
        (volume_ratio >= volume_min_ratio, f"Volumen x{volume_ratio:.2f} >= {volume_min_ratio:.2f}", f"Volumen insuficiente x{volume_ratio:.2f} < {volume_min_ratio:.2f}"),
    ]

    bull_args = [ok_msg for ok, ok_msg, _ in checks if ok]
    bear_objs = [fail_msg for ok, _, fail_msg in checks if not ok]
    passed_count = len(bull_args)
    bull_score = round(passed_count * 20.0, 1)
    bear_score = round((5 - passed_count) * 20.0, 1)
    net_score = round(bull_score - bear_score, 1)
    approved = passed_count == 5

    return {
        "approved": approved,
        "decision": "BUY" if approved else "HOLD",
        "strategy_tag": "TREND_BREAKOUT",
        "regime": regime_name,
        "bull_score": bull_score,
        "bear_score": bear_score,
        "net_score": net_score,
        "min_required": 100.0,
        "bull_arguments": bull_args,
        "bear_objections": bear_objs,
        "risk_verdict": "APROBADO (5/5)" if approved else f"ESPERANDO ({passed_count}/5 condiciones)",
        "summary": f"🚀 Breakout {symbol}: {passed_count}/5 condiciones ({'COMPRA' if approved else 'ESPERA'})",
    }


def evaluate_breakout_exit_signal(
    price: float,
    entry_price: float,
    highest_price: float,
    atr_pct: float,
    ema_50: float,
    sl_pct: float = -4.5,
    atr_mult: float = 2.0,
    min_trail_pct: float = 2.0,
    ema_exit_factor: float = 0.985,
    tp_pct: float = 25.0,
) -> Tuple[bool, str, float, float]:
    """
    Fuente única de verdad para señales de salida (TREND_BREAKOUT).
    Retorna: (should_sell, reason, pnl_pct, max_gain_pct)
    """
    if entry_price <= 0 or price <= 0:
        return False, "Precio no disponible", 0.0, 0.0

    effective_high = max(highest_price, price)
    pnl_pct = ((price - entry_price) / entry_price) * 100.0
    max_gain_pct = ((effective_high - entry_price) / entry_price) * 100.0
    trail_dist = max(min_trail_pct, atr_pct * atr_mult)
    trail_floor = max_gain_pct - trail_dist

    if pnl_pct <= sl_pct:
        return True, f"🛑 Stop Loss activado: {pnl_pct:.2f}% (Límite: {sl_pct:.1f}%)", pnl_pct, max_gain_pct

    if max_gain_pct >= 1.5 and pnl_pct <= trail_floor:
        return True, (
            f"🚀 Trailing Stop ATR Trend ejecutado: capturado +{pnl_pct:.2f}% "
            f"(Pico: +{max_gain_pct:.2f}% | Margen {atr_mult:.1f}xATR: {trail_dist:.2f}%)"
        ), pnl_pct, max_gain_pct

    if ema_50 > 0 and price < ema_50 * ema_exit_factor:
        return True, f"📉 Pérdida de EMA 50 ({pnl_pct:+.2f}%). Cerrando tendencia.", pnl_pct, max_gain_pct

    if pnl_pct >= tp_pct:
        return True, f"🎯 Take Profit alcanzado: +{pnl_pct:.2f}% (Meta: +{tp_pct:.1f}%)", pnl_pct, max_gain_pct

    return False, f"Posición vigilada: P&L {pnl_pct:+.2f}%", pnl_pct, max_gain_pct
