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

        # H. Smart Money Concepts (Liquidity Sweep + Fair Value Gap Alcista)
        smc = analysis.get("smc", {})
        if smc.get("bullish_sweep") and smc.get("bullish_fvg"):
            bull_score += 20.0
            bull_args.append("SMC: Barrido de liquidez + FVG alcista sin mitigar (+20)")
        elif smc.get("bullish_sweep"):
            bull_score += 12.0
            bull_args.append("SMC: Barrido de mínimo reciente recuperado (+12)")
        elif smc.get("bullish_fvg"):
            bull_score += 10.0
            bull_args.append("SMC: FVG alcista activo (+10)")

        # I. Alineación con Régimen de Mercado (Ranging favorece Mean Reversion)
        regime_info = analysis.get("regime", {})
        if regime_info.get("regime") == "RANGING":
            bull_score += 10.0
            bull_args.append(f"Régimen Rango (ADX {regime_info.get('adx', 20):.1f}): favorece Mean Reversion (+10)")

        # ------------------------------------------------------------------
        # 3. AGENTE BAJISTA (Bear Analyst - Abogado del Diablo)
        # ------------------------------------------------------------------
        bear_score = 0.0
        bear_objs: List[str] = []

        # A. Cuchillo cayendo sin freno
        if rsi < 35.0 and rsi < rsi_prev and not candle_bullish:
            bear_score += 20.0
            bear_objs.append("Cuchillo cayendo: RSI bajando y vela roja (-20)")

        # B. Tendencia HMA bajista o caída bajo macro EMA 200
        if hma_slope == "DOWN":
            bear_score += 20.0
            bear_objs.append("HMA 50 en pendiente bajista (-20)")
        if hma > 0 and price < hma * 0.985:
            bear_score += 15.0
            bear_objs.append("Precio >1.5% bajo HMA 50 (-15)")
        ema_200 = float(analysis.get("ema_200", 0.0))
        if ema_200 > 0 and price < ema_200:
            bear_score += 20.0
            bear_objs.append("Bajo EMA 200 macro bajista (-20)")

        # C. Vela de confirmación alcista (evita comprar velas rojas en caída libre)
        if not candle_bullish:
            bear_score += 25.0
            bear_objs.append("Vela actual roja sin rechazo alcista (-25)")

        # D. Sesión nocturna de baja liquidez
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

        # F. Smart Money Concepts: FVG Bajista justo encima como resistencia
        if smc.get("bearish_fvg_overhead"):
            bear_score += 15.0
            bear_objs.append("SMC: FVG bajista sin mitigar actuando como techo (-15)")

        # ------------------------------------------------------------------
        # 4. CONSENSO FINAL DEL JUEZ
        # ------------------------------------------------------------------
        net_score = round(bull_score - bear_score, 1)
        min_required = 58.0
        if tier == "LOW_COMPUTE":
            min_required = 68.0
        elif tier == "CRITICAL":
            min_required = 80.0

        approved = (net_score >= min_required) and (bull_score > bear_score)
        decision = "BUY" if approved else "HOLD"
        risk_verdict = "APROBADO" if approved else "BLOQUEADO POR DEBATE"

        bull_str = f"Bull {bull_score:.0f} pts"
        bear_str = f"Bear {bear_score:.0f} pts"
        summary = f"🏛️ Mesa {symbol}: {bull_str} vs {bear_str} => Neto {net_score:+.1f} pts (Req: {min_required:.0f})"

        return {
            "approved": approved,
            "decision": decision,
            "strategy_tag": "DCA_REVERSION",
            "bull_score": round(bull_score, 1),
            "bear_score": round(bear_score, 1),
            "net_score": net_score,
            "min_required": min_required,
            "bull_arguments": bull_args,
            "bear_objections": bear_objs,
            "risk_verdict": risk_verdict,
            "summary": summary
        }

    def debate_breakout_entry(
        self,
        symbol: str,
        analysis: Dict,
        cash: float,
        config: Dict,
        tier: str = "NORMAL",
        open_positions_count: int = 0
    ) -> Dict:
        """
        Segunda estrategia descorrelacionada: Trend Breakout (Ruptura Donchian 20 + HMA 50 + Volumen).
        Permite capturar tendencias alcistas sostenidas cuando el mercado no ofrece caídas de sobreventa.
        """
        price = float(analysis.get("price", 0.0))
        if price <= 0:
            return {
                "approved": False,
                "decision": "HOLD",
                "strategy_tag": "TREND_BREAKOUT",
                "bull_score": 0.0,
                "bear_score": 100.0,
                "net_score": -100.0,
                "min_required": 55.0,
                "bull_arguments": [],
                "bear_objections": ["Precio inválido"],
                "risk_verdict": "RECHAZADO (Sin datos)",
                "summary": "Sin datos válidos para breakout"
            }

        news_status = analysis.get("news_status", {})
        if news_status.get("is_shield_active"):
            act_ev = news_status.get("active_event", {})
            title = act_ev.get("title", "Noticia Alto Impacto")
            return {
                "approved": False,
                "decision": "VETO",
                "strategy_tag": "TREND_BREAKOUT",
                "bull_score": 0.0,
                "bear_score": 100.0,
                "net_score": -100.0,
                "min_required": 55.0,
                "bull_arguments": [],
                "bear_objections": [f"VETO Risk Manager: Escudo Forex Factory activo por '{title}'"],
                "risk_verdict": f"VETO POR NOTICIA ({title})",
                "summary": f"🛡️ Risk Manager veta {symbol} (Breakout): Escudo activo ({title})"
            }

        rsi = float(analysis.get("rsi", 50.0))
        hma = float(analysis.get("hma_50", price))
        hma_slope = analysis.get("hma_50_slope", "FLAT")
        ema_trend = float(analysis.get("ema_trend", price))
        ema_200 = float(analysis.get("ema_200", 0.0))
        donchian_high = float(analysis.get("donchian_high_20", 0.0))
        volume_ratio = float(analysis.get("volume_ratio", 1.0))
        session_info = analysis.get("session_info", {})
        kronos = analysis.get("kronos", {})

        bull_score = 0.0
        bull_args: List[str] = []

        if donchian_high > 0 and price >= donchian_high:
            bull_score += 40.0
            bull_args.append("Ruptura confirmada máximo Donchian 20 velas (+40)")

        if hma > 0 and price > hma and hma_slope == "UP":
            bull_score += 25.0
            bull_args.append("Tendencia alcista confirmada sobre HMA 50 (+25)")

        if ema_200 > 0 and price > ema_200 and ema_trend >= ema_200:
            bull_score += 20.0
            bull_args.append("Alineación macro alcista EMA 50 >= EMA 200 (+20)")

        if volume_ratio >= 1.25:
            bull_score += 20.0
            bull_args.append(f"Expansión de volumen institucional x{volume_ratio:.2f} (+20)")

        if 52.0 <= rsi <= 72.0:
            bull_score += 15.0
            bull_args.append(f"Momento alcista saludable RSI {rsi:.1f} (+15)")

        if kronos.get("available") and kronos.get("signal") == "BULLISH":
            bull_score += 15.0
            bull_args.append("Kronos proyecta continuidad alcista (+15)")

        if session_info.get("is_institutional_window"):
            bull_score += 10.0
            bull_args.append("Ventana institucional NY/Londres (+10)")

        regime_info = analysis.get("regime", {})
        if regime_info.get("regime") == "TRENDING":
            bull_score += 10.0
            bull_args.append(f"Régimen Tendencia (ADX {regime_info.get('adx', 25):.1f}): favorece Breakout (+10)")

        bear_score = 0.0
        bear_objs: List[str] = []

        if rsi > 75.0:
            bear_score += 35.0
            bear_objs.append(f"Sobrecompra extrema RSI {rsi:.1f}: riesgo de bull trap (-35)")

        if hma_slope == "DOWN":
            bear_score += 30.0
            bear_objs.append("HMA 50 bajista: ruptura contra tendencia (-30)")

        if ema_200 > 0 and (price < ema_200 or ema_trend < ema_200):
            bear_score += 65.0
            bear_objs.append("Bajo EMA 200 / cruce bajista macro: evita bull traps (-65)")

        if volume_ratio < 0.85:
            bear_score += 25.0
            bear_objs.append(f"Volumen débil x{volume_ratio:.2f}: posible falsa ruptura (-25)")

        if kronos.get("available") and kronos.get("signal") == "BEARISH":
            bear_score += 25.0
            bear_objs.append("Kronos advierte giro bajista (-25)")

        if open_positions_count >= 2:
            bear_score += 15.0
            bear_objs.append(f"Exposición elevada ({open_positions_count} activas) (-15)")

        if session_info.get("liquidity_tier") == "LOW":
            bear_score += 15.0
            bear_objs.append("Baja liquidez nocturna (-15)")

        net_score = round(bull_score - bear_score, 1)
        min_required = 55.0 if tier == "NORMAL" else (68.0 if tier == "LOW_COMPUTE" else 80.0)
        approved = (net_score >= min_required) and (bull_score > bear_score)
        decision = "BUY" if approved else "HOLD"
        risk_verdict = "APROBADO" if approved else "BLOQUEADO POR DEBATE"

        summary = f"🚀 Breakout {symbol}: Bull {bull_score:.0f} pts vs Bear {bear_score:.0f} pts => Neto {net_score:+.1f} pts (Req: {min_required:.0f})"
        return {
            "approved": approved,
            "decision": decision,
            "strategy_tag": "TREND_BREAKOUT",
            "bull_score": round(bull_score, 1),
            "bear_score": round(bear_score, 1),
            "net_score": net_score,
            "min_required": min_required,
            "bull_arguments": bull_args,
            "bear_objections": bear_objs,
            "risk_verdict": risk_verdict,
            "summary": summary
        }

    def _apply_bear_penalty(
        self,
        res: Dict,
        pts: float,
        objection: str,
        blocked_verdict: str = "BLOQUEADO POR DEBATE",
    ) -> None:
        """Suma una penalización al agente bajista y recalcula el veredicto neto."""
        if pts <= 0:
            return
        res["bear_score"] = round(res["bear_score"] + pts, 1)
        res["net_score"] = round(res["bull_score"] - res["bear_score"], 1)
        res["bear_objections"].append(objection)
        res["approved"] = (res["net_score"] >= res["min_required"]) and (res["bull_score"] > res["bear_score"])
        res["decision"] = "BUY" if res["approved"] else "HOLD"
        res["risk_verdict"] = "APROBADO" if res["approved"] else blocked_verdict

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
        """
        Cartera Multi-Estrategia Descorrelacionada + Protecciones Freqtrade:
        - StoplossGuard / CooldownPeriod por par.
        - HIGH_VOLATILITY_SHOCK: Risk Manager veta nuevas entradas preventivamente.
        - BTC Macro Guard: penaliza entradas en altcoins si BTCEUR cae bajo EMA 50.
        - TRENDING: prioriza TREND_BREAKOUT.
        - RANGING: prioriza DCA_REVERSION.
        """
        regime_info = analysis.get("regime", {})
        regime_name = regime_info.get("regime", "RANGING")
        vol_z = float(regime_info.get("vol_zscore", 0.0))

        if pair_cooldown_active:
            return {
                "approved": False,
                "decision": "VETO",
                "strategy_tag": "COOLDOWN_GUARD",
                "regime": regime_name,
                "bull_score": 0.0,
                "bear_score": 100.0,
                "net_score": -100.0,
                "min_required": 58.0,
                "bull_arguments": [],
                "bear_objections": [f"VETO StoplossGuard/Cooldown activo en {symbol}: evitando revenge trading"],
                "risk_verdict": f"COOLDOWN ACTIVO ({symbol})",
                "summary": f"❄️ StoplossGuard/Cooldown bloquea re-entrada en {symbol}"
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
                "min_required": 50.0,
                "bull_arguments": [],
                "bear_objections": [f"VETO Risk Manager: Shock de volatilidad extrema (Vol Z={vol_z:.2f})"],
                "risk_verdict": f"VETO POR SHOCK VOLATILIDAD (Z={vol_z:.2f})",
                "summary": f"⚡ Risk Manager veta {symbol}: Shock de volatilidad (Z={vol_z:.2f})"
            }

        dca_res = self.debate_entry(symbol, analysis, cash, config, tier=tier, open_positions_count=open_positions_count)
        if dca_res.get("decision") == "VETO":
            dca_res["regime"] = regime_name
            return dca_res

        brk_res = self.debate_breakout_entry(symbol, analysis, cash, config, tier=tier, open_positions_count=open_positions_count)

        # BTC Informative Market Filter: si BTC está bajista y vamos a entrar en una altcoin, penalizar
        if not btc_healthy and symbol != "BTCEUR":
            for r in (dca_res, brk_res):
                self._apply_bear_penalty(
                    r,
                    35.0,
                    "BTC Macro Guard: BTCEUR bajo EMA 50 arrastra altcoins (-35)",
                    "BLOQUEADO POR BTC GUARD",
                )

        # Memoria de errores recientes: endurece el filtro si hay racha o patrón reciente de pérdidas
        if recent_memory:
            consec_losses = int(recent_memory.get("consecutive_losses", 0))
            if consec_losses >= 2:
                streak_pts = 25.0 if consec_losses >= 3 else 15.0
                for r in (dca_res, brk_res):
                    self._apply_bear_penalty(
                        r,
                        streak_pts,
                        f"Memoria de errores: {consec_losses} pérdidas seguidas recientes (-{streak_pts:.0f})",
                        "BLOQUEADO POR MEMORIA",
                    )

            strat_losses = recent_memory.get("strategy_losses", {})
            for r, tag in ((dca_res, "DCA_REVERSION"), (brk_res, "TREND_BREAKOUT")):
                losses_count = int(strat_losses.get(tag, 0))
                if losses_count >= 2:
                    self._apply_bear_penalty(
                        r,
                        20.0,
                        f"Memoria de errores: {tag} acumula {losses_count} pérdidas en 24h (-20)",
                        "BLOQUEADO POR MEMORIA",
                    )

            if recent_memory.get("symbol_recent_loss"):
                for r in (dca_res, brk_res):
                    self._apply_bear_penalty(
                        r,
                        10.0,
                        f"Memoria de errores: {symbol} cerró en pérdida recientemente (-10)",
                        "BLOQUEADO POR MEMORIA",
                    )

        dca_res["regime"] = regime_name
        brk_res["regime"] = regime_name

        if dca_res.get("approved") and not brk_res.get("approved"):
            return dca_res
        if brk_res.get("approved") and not dca_res.get("approved"):
            return brk_res
        if dca_res.get("approved") and brk_res.get("approved"):
            if regime_name == "TRENDING" and brk_res["net_score"] >= dca_res["net_score"] - 15.0:
                return brk_res
            if regime_name == "RANGING" and dca_res["net_score"] >= brk_res["net_score"] - 15.0:
                return dca_res
        return dca_res if dca_res.get("net_score", -999) >= brk_res.get("net_score", -999) else brk_res
