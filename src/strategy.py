from typing import Dict, Optional, Tuple

class SmartDCAStrategy:
    def __init__(self, config: Dict):
        self.config = config

    def evaluate(self, analysis: Dict, position: Optional[Dict], cash: float) -> Tuple[str, float, str]:
        """
        Evalúa el estado del mercado y la posición actual para decidir una acción con estricta jerarquía cuantitativa,
        protección de Break-Even, filtro de tendencia y confirmación de rebote.
        Retorna: (accion: 'BUY' | 'SELL' | 'HOLD', cantidad_eur: float, razon: str)
        """
        symbol = analysis.get("symbol", "")
        price = analysis.get("price", 0.0)
        rsi = analysis.get("rsi", 50.0)
        rsi_prev = analysis.get("rsi_prev", rsi)
        ema_fast = analysis.get("ema_fast", price)
        ema_slow = analysis.get("ema_slow", price)
        ema_trend = analysis.get("ema_trend", price)
        sma_val = analysis.get("sma_50", ema_trend if ema_trend > 0 else price)
        bb_lower = analysis.get("bb_lower", 0.0)
        bb_upper = analysis.get("bb_upper", 0.0)
        candle_bullish = analysis.get("candle_bullish", False)
        hma_50 = analysis.get("hma_50", sma_val)
        hma_50_prev = analysis.get("hma_50_prev", hma_50)
        hma_slope = analysis.get("hma_50_slope", "FLAT")
        session_info = analysis.get("session_info", {})
        is_institutional = session_info.get("is_institutional_window", False)
        liquidity_tier = session_info.get("liquidity_tier", "HIGH")
        min_order = self.config.get("min_order_eur", 5.0)

        if price <= 0:
            return "HOLD", 0.0, "Esperando datos de precio válidos"

        # ----------------------------------------------------
        # 1. EVALUAR VENTA (Gestión de posición abierta)
        # ----------------------------------------------------
        if position and position.get("amount", 0) > 0:
            avg_entry = position.get("avg_entry_price", price)
            gain_pct = ((price - avg_entry) / avg_entry) * 100

            # Seguimiento de máxima ganancia alcanzada para Trailing Break-Even
            highest_price = position.get("highest_price", avg_entry)
            if price > highest_price:
                position["highest_price"] = price
                highest_price = price
            max_gain_pct = ((highest_price - avg_entry) / avg_entry) * 100

            # JERARQUÍA 1: BREAK-EVEN PROTECTOR (Bloquea beneficios y no permite que un trade ganador acabe en pérdida)
            breakeven_trigger = self.config.get("breakeven_trigger_pct", 1.6)
            if max_gain_pct >= breakeven_trigger:
                if gain_pct <= 0.25:
                    return "SELL", 0.0, f"🛡️ Break-Even Protector ejecutado: asegurado +{gain_pct:.2f}% (Máximo alcanzado: +{max_gain_pct:.2f}%)"

            # JERARQUÍA 2: STOP-LOSS ESTRICTO (Protección de Capital Inviolable)
            stop_loss_target = self.config.get("stop_loss_pct", -3.0)
            if gain_pct <= stop_loss_target:
                return "SELL", 0.0, f"🛑 Stop-Loss de protección ejecutado: {gain_pct:.2f}% (Límite: {stop_loss_target}%)"

            # JERARQUÍA 3: TRAILING STOP DINÁMICO POR ATR (Acompaña impulsos alcistas y asegura ganancias ante giros bruscos)
            atr_pct = analysis.get("atr_pct", 1.5)
            if max_gain_pct >= 2.0:
                trailing_distance = max(0.8, atr_pct * 1.0)
                trailing_floor = max_gain_pct - trailing_distance
                if trailing_floor >= 0.5 and gain_pct <= trailing_floor:
                    return "SELL", 0.0, f"🚀 Trailing Stop ATR ejecutado: capturado +{gain_pct:.2f}% (Pico máximo: +{max_gain_pct:.2f}% | Margen ATR: {trailing_distance:.2f}%)"

            # JERARQUÍA 4: TAKE-PROFIT OBJETIVO (+3.5%)
            take_profit_target = self.config.get("take_profit_pct", 3.5)
            if gain_pct >= take_profit_target:
                return "SELL", 0.0, f"🎯 Take-Profit alcanzado: +{gain_pct:.2f}% (Objetivo: +{take_profit_target}%)"

            # JERARQUÍA 5: TOMA DE GANANCIAS TÉCNICA DINÁMICA (Solo con ganancia asegurada >= early_take_profit_pct)
            early_tp_min = self.config.get("early_take_profit_pct", 2.4)
            rsi_sell = self.config.get("rsi_sell_threshold", 68.0)
            if rsi >= rsi_sell and gain_pct >= early_tp_min:
                return "SELL", 0.0, f"📈 Toma de beneficios por RSI en sobrecompra ({rsi:.1f}) y ganancia de +{gain_pct:.2f}%"

            if bb_upper > 0 and price >= bb_upper and gain_pct >= early_tp_min:
                return "SELL", 0.0, f"🔔 Rebote en Banda Superior Bollinger con ganancia de +{gain_pct:.2f}%"

            # ----------------------------------------------------
            # 2. EVALUAR COMPRA DCA ESCALONADA (Promediar en retrocesos calculados)
            # ----------------------------------------------------
            dca_count = position.get("dca_count", 1)
            last_buy_price = position.get("last_buy_price", avg_entry)
            price_drop = ((last_buy_price - price) / last_buy_price) * 100
            order_size = min(self.config.get("order_amount_eur", 5.0), cash)

            # Protección de saldo mínimo para DCA: si el saldo libre es insuficiente para MIN_NOTIONAL, bloquear entradas
            if cash < min_order:
                status_extra = f" | Break-Even Activo (+{max_gain_pct:.2f}%)" if max_gain_pct >= breakeven_trigger else ""
                return "HOLD", 0.0, f"Esperando cierre de posición (Saldo libre €{cash:.2f} < €{min_order:.2f} MIN_NOTIONAL){status_extra}"

            drop_trigger = self.config.get("price_drop_trigger_pct", 2.0)
            rsi_buy = self.config.get("rsi_buy_threshold", 32.0)
            if dca_count < 3 and cash >= min_order:
                if price_drop >= drop_trigger and rsi <= (rsi_buy + 4.0):
                    return "BUY", order_size, f"📉 DCA #{dca_count + 1}: Compra en retroceso (-{price_drop:.2f}%) con RSI favorable ({rsi:.1f})"

            status_extra = f" | Break-Even Activo (+{max_gain_pct:.2f}%)" if max_gain_pct >= breakeven_trigger else ""
            return "HOLD", 0.0, f"Posición abierta: {gain_pct:+.2f}% | Esperando TP (+{take_profit_target}%) o SL ({stop_loss_target}%){status_extra}"

        # ----------------------------------------------------
        # 3. EVALUAR PRIMERA COMPRA (Sin posición abierta)
        # ----------------------------------------------------
        # Protección de Saldo Mínimo: Bloquear nuevas entradas si saldo libre < MIN_NOTIONAL
        if cash < min_order:
            return "HOLD", 0.0, f"Esperando cierre de posición (Saldo libre €{cash:.2f} < €{min_order:.2f} MIN_NOTIONAL)"

        order_size = min(self.config.get("order_amount_eur", 5.0), cash)
        base_rsi_buy = self.config.get("rsi_buy_threshold", 32.0)

        # Filtro de Sesión y Liquidez Institucional:
        # En la ventana institucional (13-17 UTC) operamos con umbral estándar (32.0).
        # En horas nocturnas / baja liquidez exigimos mayor descuento (<= 30.0) para no caer en trampas.
        if liquidity_tier == "LOW":
            effective_rsi_buy = min(base_rsi_buy, 30.0)
            session_tag = "[Sesión Nocturna: Exigencia Estricta]"
        elif is_institutional:
            effective_rsi_buy = base_rsi_buy
            session_tag = "[Sesión Institucional NY/Londres: Alta Liquidez]"
        else:
            effective_rsi_buy = base_rsi_buy
            session_tag = "[Sesión Regular]"

        # Filtro de Tendencia Dinámica de Hull (HMA 50 - Cero Retraso) y Macro SMA:
        # Condición: Precio sobre HMA 50 o HMA 50 con pendiente alcista ('UP')
        is_hma_bullish = (hma_50 >= hma_50_prev or hma_slope == "UP")
        is_reclaiming_hma = (price >= hma_50 or (price >= hma_50 * 0.995 and is_hma_bullish)) if hma_50 > 0 else True
        is_above_sma = (price >= sma_val) if sma_val > 0 else True
        is_converging_sma = (price >= sma_val * 0.992 and (rsi >= rsi_prev or candle_bullish)) if sma_val > 0 else True
        trend_valid = is_reclaiming_hma or is_above_sma or is_converging_sma

        # Setup 1: Sobreventa cuantitativa con rebote confirmado y filtro HMA / SMA
        if rsi <= effective_rsi_buy:
            if not trend_valid:
                return "HOLD", 0.0, f"Filtro HMA/SMA bloquea entrada: RSI {rsi:.1f} pero precio (€{price:,.2f}) bajo HMA 50 (€{hma_50:,.2f}) en pendiente bajista"
            if rsi >= rsi_prev or candle_bullish or (bb_lower > 0 and price <= bb_lower * 1.002):
                return "BUY", order_size, f"🟢 Señal de compra {session_tag}: Sobreventa ({rsi:.1f} <= {effective_rsi_buy}) con HMA 50 (€{hma_50:,.2f} | {hma_slope}) y rebote confirmado"

        # Setup 2: Rebote validado en Banda Bollinger Inferior en zona de sobreventa con filtro de tendencia HMA
        if bb_lower > 0 and price <= (bb_lower * 1.002) and rsi <= min(35.0, effective_rsi_buy + 3.0) and trend_valid:
            if candle_bullish or rsi >= rsi_prev:
                return "BUY", order_size, f"🟢 Señal de compra {session_tag}: Soporte en Bollinger Inferior (€{bb_lower:,.2f}) y RSI {rsi:.1f} con HMA 50 validada"

        return "HOLD", 0.0, f"Mercado en espera (RSI: {rsi:.1f} | HMA50: €{hma_50:,.2f} [{hma_slope}] | {session_info.get('session_name', 'Mercado')}) | Esperando zona óptima (<= {effective_rsi_buy})"
