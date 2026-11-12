from typing import Dict, List, Optional

class TradingCouncil:
    """
    🏛️ Mesa de Debate Multi-Agente (Inspirada en TauricResearch/TradingAgents)
    
    En lugar de una única puntuación lineal, enfrenta explícitamente a tres roles antes de arriesgar capital:
    1. Agente Alcista (Bull Analyst): Recopila argumentos estadísticos de entrada y rebote.
    2. Agente Bajista (Bear Analyst): Busca activamente señales de trampa, caída libre o baja liquidez.
    3. Gestor de Riesgo (Risk Manager): Evalúa eventos macroeconómicos (Forex Factory), exposición y reserva de DCA.
    """

    def debate_entry(
        self,
        symbol: str,
        analysis: Dict,
        cash: float,
        config: Dict,
        tier: str = "NORMAL",
        open_positions_count: int = 0
    ) -> Dict:
        price = float(analysis.get("price", 0.0))
        if price <= 0:
            return {
                "approved": False,
                "decision": "HOLD",
                "bull_score": 0.0,
                "bear_score": 100.0,
                "net_score": -100.0,
                "min_required": 50.0,
                "bull_arguments": [],
                "bear_objections": ["Precio inválido o no disponible"],
                "risk_verdict": "RECHAZADO (Sin datos)",
                "summary": "Sin datos válidos para debate"
            }

        rsi = float(analysis.get("rsi", 50.0))
        rsi_prev = float(analysis.get("rsi_prev", rsi))
        sma = float(analysis.get("sma_50", 0.0))
        hma = float(analysis.get("hma_50", sma))
        hma_prev = float(analysis.get("hma_50_prev", hma))
        hma_slope = analysis.get("hma_50_slope", "FLAT")
        bb_lower = float(analysis.get("bb_lower", 0.0))
        ema_fast = float(analysis.get("ema_fast", 0.0))
        ema_slow = float(analysis.get("ema_slow", 0.0))
        candle_bullish = bool(analysis.get("candle_bullish", False))
        session_info = analysis.get("session_info", {})
        kronos = analysis.get("kronos", {})
        news_status = analysis.get("news_status", {})

        rsi_threshold = float(config.get("rsi_buy_threshold", 32.0))
        if tier == "CRITICAL":
            rsi_threshold = min(rsi_threshold, 28.0)

        # ------------------------------------------------------------------
        # 1. GESTOR DE RIESGO (Risk Manager - Veto Inviolable)
        # ------------------------------------------------------------------
        if news_status.get("is_shield_active"):
            act_ev = news_status.get("active_event", {})
            title = act_ev.get("title", "Noticia Alto Impacto")
            return {
                "approved": False,
                "decision": "VETO",
                "bull_score": 0.0,
                "bear_score": 100.0,
                "net_score": -100.0,
                "min_required": 50.0,
                "bull_arguments": [],
                "bear_objections": [f"VETO Risk Manager: Escudo Forex Factory activo por '{title}'"],
                "risk_verdict": f"VETO POR NOTICIA ({title})",
                "summary": f"🛡️ Risk Manager veta {symbol}: Escudo Forex Factory activo ({title})"
            }

        # ------------------------------------------------------------------
        # 2. AGENTE ALCISTA (Bull Analyst)
        # ------------------------------------------------------------------
        bull_score = 0.0
        bull_args: List[str] = []

        # A. Sobreventa RSI
        if rsi <= rsi_threshold:
            pts = (rsi_threshold - rsi) * 2.5 + 45.0
            bull_score += pts
            bull_args.append(f"RSI en sobreventa ({rsi:.1f} <= {rsi_threshold:.1f}, +{pts:.0f})")
        elif rsi <= 40.0:
            pts = (40.0 - rsi) * 1.5
            bull_score += pts
            bull_args.append(f"RSI acercándose a zona barata ({rsi:.1f}, +{pts:.0f})")

        # B. Giro alcista en formación
        if rsi > rsi_prev and rsi <= 42.0:
            bull_score += 15.0
            bull_args.append("Giro de RSI al alza (+15)")
        if candle_bullish and rsi <= 42.0:
            bull_score += 10.0
            bull_args.append("Vela verde de rechazo (+10)")

        # C. Soporte Banda Bollinger Inferior
        if bb_lower > 0 and price <= bb_lower * 1.01:
            bull_score += 25.0
            bull_args.append("Tocando soporte Bollinger Inferior (+25)")

        # D. Media Móvil de Hull (HMA 50)
        if hma_slope == "UP":
            bull_score += 20.0
            bull_args.append("HMA 50 en pendiente alcista (+20)")
        elif hma > 0 and hma >= hma_prev:
            bull_score += 10.0
            bull_args.append("HMA 50 estabilizada (+10)")

        if hma > 0 and price >= hma:
            bull_score += 15.0
            bull_args.append("Precio sobre HMA 50 (+15)")

        # E. Ventana Institucional
        if session_info.get("is_institutional_window"):
            bull_score += 15.0
            bull_args.append("Ventana institucional NY/Londres (+15)")

        # F. Cruce EMA rápido
        if ema_fast > 0 and ema_slow > 0 and ema_fast >= ema_slow:
            bull_score += 10.0
            bull_args.append("EMA 9 >= EMA 21 (+10)")

        # G. Oráculo Kronos Alcista
        if kronos.get("verdict") == "BULLISH_BIAS":
            bull_score += 15.0
            bull_args.append(f"Oráculo Kronos alcista {kronos.get('bullish_prob', 60)}% (+15)")

        # ------------------------------------------------------------------
        # 3. AGENTE BAJISTA (Bear Analyst - Abogado del Diablo)
        # ------------------------------------------------------------------
        bear_score = 0.0
        bear_objs: List[str] = []

        # A. Cuchillo cayendo sin freno
        if rsi < 35.0 and rsi < rsi_prev and not candle_bullish:
            bear_score += 20.0
            bear_objs.append("Cuchillo cayendo: RSI bajando y vela roja (-20)")

        # B. Tendencia HMA bajista o caída pronunciada
        if hma_slope == "DOWN":
            bear_score += 15.0
            bear_objs.append("HMA 50 en pendiente bajista (-15)")
        if hma > 0 and price < hma * 0.985:
            bear_score += 15.0
            bear_objs.append("Precio >1.5% bajo HMA 50 (-15)")

        # C. Sesión nocturna de baja liquidez
        if session_info.get("liquidity_tier") == "LOW":
            bear_score += 15.0
            bear_objs.append("Baja liquidez nocturna: riesgo de trampas (-15)")

        # D. Oráculo Kronos Bajista
        if kronos.get("verdict") == "BEARISH_BIAS":
            penalty = 25.0 if float(kronos.get("bullish_prob", 50.0)) <= 35.0 else 15.0
            bear_score += penalty
            bear_objs.append(f"Kronos prevé sesgo bajista (-{penalty:.0f})")

        # E. Riesgo de concentración de cartera (Gestor de Riesgo)
        order_amt = float(config.get("order_amount_eur", 5.0))
        min_order = float(config.get("min_order_eur", 5.0))
        if open_positions_count >= 3 and cash < (order_amt + min_order):
            bear_score += 15.0
            bear_objs.append("Alta exposición: dejaría poco margen para DCA (-15)")

        # ------------------------------------------------------------------
        # 4. CONSENSO FINAL DEL JUEZ
        # ------------------------------------------------------------------
        net_score = round(bull_score - bear_score, 1)
        min_required = 50.0
        if tier == "LOW_COMPUTE":
            min_required = 65.0
        elif tier == "CRITICAL":
            min_required = 78.0

        approved = (net_score >= min_required) and (bull_score > bear_score)
        decision = "BUY" if approved else "HOLD"
        risk_verdict = "APROBADO" if approved else "BLOQUEADO POR DEBATE"

        bull_str = f"Bull {bull_score:.0f} pts"
        bear_str = f"Bear {bear_score:.0f} pts"
        summary = f"🏛️ Mesa {symbol}: {bull_str} vs {bear_str} => Neto {net_score:+.1f} pts (Req: {min_required:.0f})"

        return {
            "approved": approved,
            "decision": decision,
            "bull_score": round(bull_score, 1),
            "bear_score": round(bear_score, 1),
            "net_score": net_score,
            "min_required": min_required,
            "bull_arguments": bull_args,
            "bear_objections": bear_objs,
            "risk_verdict": risk_verdict,
            "summary": summary
        }
