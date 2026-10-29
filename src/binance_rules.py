import math
from typing import Dict, Tuple

class BinanceRulesEngine:
    """
    Control institucional de reglas de exchange para Binance Spot:
    - Validación de MIN_NOTIONAL (evita rechazos por órdenes inferiores a 5€).
    - Ajuste al stepSize exacto (LOT_SIZE) con redondeo HACIA ABAJO (floor) para evitar errores de insuficiencia por comisiones.
    - Manejo y prevención de "polvo" de criptomonedas (crypto dust).
    """

    # Parámetros oficiales de filtros de Binance Spot para pares EUR
    FILTER_RULES: Dict[str, Dict[str, float]] = {
        "BTCEUR": {
            "step_size": 0.00001,      # Precisión mínima de cantidad (5 decimales)
            "min_qty": 0.00001,
            "min_notional": 5.0,        # Mínimo valor de orden en Euros
            "quote_precision": 2        # Precisión de precio (€0.01)
        },
        "ETHEUR": {
            "step_size": 0.0001,       # 4 decimales
            "min_qty": 0.0001,
            "min_notional": 5.0,
            "quote_precision": 2
        },
        "SOLEUR": {
            "step_size": 0.01,         # 2 decimales
            "min_qty": 0.01,
            "min_notional": 5.0,
            "quote_precision": 2
        }
    }

    # Reglas por defecto para otros activos
    DEFAULT_RULE = {
        "step_size": 0.0001,
        "min_qty": 0.0001,
        "min_notional": 5.0,
        "quote_precision": 2
    }

    @classmethod
    def get_rule(cls, symbol: str) -> Dict[str, float]:
        return cls.FILTER_RULES.get(symbol, cls.DEFAULT_RULE)

    @classmethod
    def validate_buy_order(cls, symbol: str, amount_eur: float, price: float) -> Tuple[bool, float, str]:
        """
        Valida que una orden de compra supere el MIN_NOTIONAL y calcula la cantidad neta admisible.
        """
        rule = cls.get_rule(symbol)
        min_notional = rule["min_notional"]

        if amount_eur < min_notional:
            return False, 0.0, f"Importe €{amount_eur:.2f} inferior al MIN_NOTIONAL del exchange (€{min_notional:.2f})"

        if price <= 0:
            return False, 0.0, "Precio de mercado inválido"

        raw_qty = amount_eur / price
        step = rule["step_size"]
        # Redondear hacia abajo según stepSize
        adjusted_qty = math.floor(raw_qty / step) * step

        if adjusted_qty < rule["min_qty"]:
            return False, 0.0, f"Cantidad resultante {adjusted_qty} inferior a minQty {rule['min_qty']}"

        return True, adjusted_qty, "OK"

    @classmethod
    def adjust_quantity_for_sell(cls, symbol: str, raw_qty: float, price: float) -> Tuple[bool, float, str]:
        """
        Ajusta la cantidad a vender al stepSize exacto redondeando hacia abajo.
        Previene errores de INSUFFICIENT_BALANCE causados por deducción de comisiones.
        """
        rule = cls.get_rule(symbol)
        step = rule["step_size"]

        if raw_qty <= 0 or price <= 0:
            return False, 0.0, "Cantidad o precio inválido para venta"

        # Truncado matemático estricto hacia abajo (floor)
        decimals = max(0, -int(math.floor(math.log10(step))))
        adjusted_qty = round(math.floor(raw_qty / step) * step, decimals)

        if adjusted_qty < rule["min_qty"]:
            return False, 0.0, f"Cantidad tras redondeo ({adjusted_qty}) inferior a minQty ({rule['min_qty']})"

        notional_eur = adjusted_qty * price
        if notional_eur < rule["min_notional"]:
            return False, adjusted_qty, f"Valor de venta (€{notional_eur:.2f}) por debajo de MIN_NOTIONAL (€{rule['min_notional']:.2f})"

        return True, adjusted_qty, "OK"
