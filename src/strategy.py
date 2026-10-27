from typing import Dict, Optional, Tuple

class SmartDCAStrategy:
    def __init__(self, config: Dict):
        self.config = config

    def evaluate(self, analysis: Dict, position: Optional[Dict], cash: float) -> Tuple[str, float, str]:
        """
        Evalúa el estado del mercado y la posición actual para decidir una acción.
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
        # 1. EVALUAR VENTA (Gestión de posición abierta)
        # ----------------------------------------------------
        if position and position.get("amount", 0) > 0:
            avg_entry = position.get("avg_entry_price", price)
            gain_pct = ((price - avg_entry) / avg_entry) * 100

            # A) Take-Profit por objetivo de rentabilidad
            take_profit_target = self.config.get("take_profit_pct", 2.0)
            if gain_pct >= take_profit_target:
                return "SELL", 0.0, f"🎯 Take-Profit alcanzado: +{gain_pct:.2f}% (Objetivo: +{take_profit_target}%)"

            # B) Stop-Loss de protección máxima
            stop_loss_target = self.config.get("stop_loss_pct", -5.0)
            if gain_pct <= stop_loss_target:
                return "SELL", 0.0, f"🛑 Stop-Loss de seguridad activado: {gain_pct:.2f}%"

            # C) Salida dinámica por RSI sobrecomprado (> 65) con ganancia positiva
            rsi_sell = self.config.get("rsi_sell_threshold", 65.0)
            if rsi >= rsi_sell and gain_pct >= 0.8:
                return "SELL", 0.0, f"📈 Toma de ganancias por RSI elevado ({rsi:.1f}) y ganancia de +{gain_pct:.2f}%"

            # D) Venta si el precio supera la banda de Bollinger superior con ganancia positiva
            if bb_upper > 0 and price >= bb_upper and gain_pct >= 1.0:
                return "SELL", 0.0, f"🔔 Rebote en Banda Superior Bollinger con ganancia de +{gain_pct:.2f}%"

            # ----------------------------------------------------
            # 2. EVALUAR COMPRA DCA ESCALONADA (Promediar a la baja)
            # ----------------------------------------------------
            dca_count = position.get("dca_count", 1)
            last_buy_price = position.get("last_buy_price", avg_entry)
            price_drop = ((last_buy_price - price) / last_buy_price) * 100
            order_size = min(self.config.get("order_amount_eur", 3.0), cash)

            # Si el precio cayó respecto a la última compra y aún tenemos capital para promediar
            drop_trigger = self.config.get("price_drop_trigger_pct", 0.8)
            if dca_count < 3 and cash >= self.config.get("min_order_eur", 2.0):
                if price_drop >= drop_trigger and rsi <= 45:
                    return "BUY", order_size, f"📉 DCA #{dca_count + 1}: Compra en retroceso (-{price_drop:.2f}%) con RSI {rsi:.1f}"

            # Si ya tenemos posición y no se cumplen ventas ni compras DCA:
            return "HOLD", 0.0, f"Posición abierta: {gain_pct:+.2f}% | Esperando Take-Profit (+{take_profit_target}%)"

        # ----------------------------------------------------
        # 3. EVALUAR PRIMERA COMPRA (Sin posición abierta)
        # ----------------------------------------------------
        order_size = min(self.config.get("order_amount_eur", 3.0), cash)
        if cash < self.config.get("min_order_eur", 2.0):
            return "HOLD", 0.0, "Saldo insuficiente para abrir nueva posición"

        rsi_buy = self.config.get("rsi_buy_threshold", 40.0)

        # Condición 1: RSI en zona de sobreventa / rebote favorable
        if rsi <= rsi_buy:
            return "BUY", order_size, f"🟢 Señal de compra: RSI en sobreventa ({rsi:.1f} <= {rsi_buy})"

        # Condición 2: Toque o ruptura de la Banda Bollinger Inferior
        if bb_lower > 0 and price <= (bb_lower * 1.001):
            return "BUY", order_size, f"🟢 Señal de compra: Precio en soporte de Banda Bollinger Inferior (€{bb_lower:.2f})"

        # Condición 3: Cruce alcista de medias EMA rápida sobre lenta en niveles moderados de RSI
        if ema_fast > ema_slow and rsi <= 50 and price > ema_fast:
            return "BUY", order_size, f"🟢 Cruce alcista de medias móviles (EMA 9 > EMA 21) con RSI neutral ({rsi:.1f})"

        return "HOLD", 0.0, f"Mercado en equilibrio (RSI: {rsi:.1f}) | Esperando oportunidad de descuento"
