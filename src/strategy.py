from typing import Dict, Optional, Tuple

class SmartDCAStrategy:
    def __init__(self, config: Dict):
        self.config = config

    def evaluate(self, analysis: Dict, position: Optional[Dict], cash: float) -> Tuple[str, float, str]:
        """
        Evalúa el estado del mercado y la posición actual para decidir una acción con estricta jerarquía cuantitativa.
        Retorna: (accion: 'BUY' | 'SELL' | 'HOLD', cantidad_eur: float, razon: str)
        """
        symbol = analysis.get("symbol", "")
        price = analysis.get("price", 0.0)
        rsi = analysis.get("rsi", 50.0)
        ema_fast = analysis.get("ema_fast", price)
        ema_slow = analysis.get("ema_slow", price)
        bb_lower = analysis.get("bb_lower", 0.0)
        bb_upper = analysis.get("bb_upper", 0.0)

        if price <= 0:
            return "HOLD", 0.0, "Esperando datos de precio válidos"

        # ----------------------------------------------------
        # 1. EVALUAR VENTA (Gestión de posición abierta con Jerarquía Estricta)
        # ----------------------------------------------------
        if position and position.get("amount", 0) > 0:
            avg_entry = position.get("avg_entry_price", price)
            gain_pct = ((price - avg_entry) / avg_entry) * 100

            # JERARQUÍA 1: STOP-LOSS ESTRICTO (-3.5%) - Protección de Capital Inviolable
            stop_loss_target = self.config.get("stop_loss_pct", -3.5)
            if gain_pct <= stop_loss_target:
                return "SELL", 0.0, f"🛑 Stop-Loss de protección ejecutado: {gain_pct:.2f}% (Límite: {stop_loss_target}%)"

            # JERARQUÍA 2: TAKE-PROFIT OBJETIVO (+4.5%) - Máxima Rentabilidad
            take_profit_target = self.config.get("take_profit_pct", 4.5)
            if gain_pct >= take_profit_target:
                return "SELL", 0.0, f"🎯 Take-Profit alcanzado: +{gain_pct:.2f}% (Objetivo: +{take_profit_target}%)"

            # JERARQUÍA 3: TOMA DE GANANCIAS TÉCNICA DINÁMICA (Solo con ganancia positiva >= +1.5%)
            rsi_sell = self.config.get("rsi_sell_threshold", 65.0)
            if rsi >= rsi_sell and gain_pct >= 1.5:
                return "SELL", 0.0, f"📈 Toma de beneficios por RSI en sobrecompra ({rsi:.1f}) y ganancia de +{gain_pct:.2f}%"

            # JERARQUÍA 4: REBOTE EN BANDA BOLLINGER SUPERIOR (Solo con ganancia positiva >= +1.5%)
            if bb_upper > 0 and price >= bb_upper and gain_pct >= 1.5:
                return "SELL", 0.0, f"🔔 Rebote en Banda Superior Bollinger con ganancia asegurada de +{gain_pct:.2f}%"

            # ----------------------------------------------------
            # 2. EVALUAR COMPRA DCA ESCALONADA (Promediar a la baja en retrocesos)
            # ----------------------------------------------------
            dca_count = position.get("dca_count", 1)
            last_buy_price = position.get("last_buy_price", avg_entry)
            price_drop = ((last_buy_price - price) / last_buy_price) * 100
            order_size = min(self.config.get("order_amount_eur", 25.0), cash)

            # Promediar solo si la caída es notable (>= 1.5%), RSI favorable y hay capital suficiente
            drop_trigger = self.config.get("price_drop_trigger_pct", 1.5)
            rsi_buy = self.config.get("rsi_buy_threshold", 35.0)
            if dca_count < 3 and cash >= self.config.get("min_order_eur", 5.0):
                if price_drop >= drop_trigger and rsi <= (rsi_buy + 5.0):
                    return "BUY", order_size, f"📉 DCA #{dca_count + 1}: Compra en retroceso (-{price_drop:.2f}%) con RSI favorable ({rsi:.1f})"

            # Si ya tenemos posición y no se cumplen ventas ni compras DCA:
            return "HOLD", 0.0, f"Posición abierta: {gain_pct:+.2f}% | Esperando Take-Profit (+{take_profit_target}%) o Stop-Loss ({stop_loss_target}%)"

        # ----------------------------------------------------
        # 3. EVALUAR PRIMERA COMPRA (Sin posición abierta)
        # ----------------------------------------------------
        order_size = min(self.config.get("order_amount_eur", 25.0), cash)
        if cash < self.config.get("min_order_eur", 5.0):
            return "HOLD", 0.0, "Saldo insuficiente para abrir nueva posición"

        rsi_buy = self.config.get("rsi_buy_threshold", 35.0)

        # Condición 1: RSI en sobreventa real (<= 35.0)
        if rsi <= rsi_buy:
            return "BUY", order_size, f"🟢 Señal de compra: RSI en sobreventa estricta ({rsi:.1f} <= {rsi_buy})"

        # Condición 2: Soporte en Banda Bollinger Inferior con RSI moderado (<= 40)
        if bb_lower > 0 and price <= (bb_lower * 1.001) and rsi <= 40.0:
            return "BUY", order_size, f"🟢 Señal de compra: Soporte en Banda Bollinger Inferior (€{bb_lower:,.2f}) y RSI {rsi:.1f}"

        # Condición 3: Cruce alcista de medias móviles con RSI saludable (<= 45)
        if ema_fast > ema_slow and rsi <= 45.0 and price > ema_fast:
            return "BUY", order_size, f"🟢 Cruce alcista de medias móviles (EMA 9 > EMA 21) con RSI moderado ({rsi:.1f})"

        return "HOLD", 0.0, f"Mercado en equilibrio (RSI: {rsi:.1f}) | Esperando zona de descuento (RSI <= {rsi_buy})"
