import math
from typing import Dict, Tuple

class BinanceRulesEngine:
    """
    Control institucional de reglas de exchange para Binance Spot:
    - Validación de MIN_NOTIONAL (evita rechazos por órdenes inferiores a 5€).
    - Ajuste al stepSize exacto (LOT_SIZE) con redondeo HACIA ABAJO (floor) para evitar errores de insuficiencia por comisiones.
    - Manejo y prevención de "polvo" de criptomonedas (crypto dust).
    """

    # Parámetros oficiales de filtros de Binance Spot para los 29 pares EUR
    FILTER_RULES: Dict[str, Dict[str, float]] = {
        "BTCEUR": {"step_size": 1e-05, "min_qty": 1e-05, "min_notional": 5.0, "quote_precision": 8},
        "ETHEUR": {"step_size": 0.0001, "min_qty": 0.0001, "min_notional": 5.0, "quote_precision": 8},
        "BNBEUR": {"step_size": 0.001, "min_qty": 0.001, "min_notional": 5.0, "quote_precision": 8},
        "SOLEUR": {"step_size": 0.001, "min_qty": 0.001, "min_notional": 5.0, "quote_precision": 8},
        "XRPEUR": {"step_size": 0.1, "min_qty": 0.1, "min_notional": 5.0, "quote_precision": 8},
        "DOGEEUR": {"step_size": 1.0, "min_qty": 1.0, "min_notional": 1.0, "quote_precision": 8},
        "ADAEUR": {"step_size": 0.1, "min_qty": 0.1, "min_notional": 5.0, "quote_precision": 8},
        "AVAXEUR": {"step_size": 0.01, "min_qty": 0.01, "min_notional": 5.0, "quote_precision": 8},
        "LINKEUR": {"step_size": 0.01, "min_qty": 0.01, "min_notional": 5.0, "quote_precision": 8},
        "DOTEUR": {"step_size": 0.01, "min_qty": 0.01, "min_notional": 5.0, "quote_precision": 8},
        "SUIEUR": {"step_size": 0.1, "min_qty": 0.1, "min_notional": 5.0, "quote_precision": 8},
        "PEPEEUR": {"step_size": 1.0, "min_qty": 1.0, "min_notional": 1.0, "quote_precision": 8},
        "SHIBEUR": {"step_size": 1.0, "min_qty": 1.0, "min_notional": 1.0, "quote_precision": 8},
        "NEAREUR": {"step_size": 0.1, "min_qty": 0.1, "min_notional": 5.0, "quote_precision": 8},
        "POLEUR": {"step_size": 0.1, "min_qty": 0.1, "min_notional": 5.0, "quote_precision": 8},
        "RENDEREUR": {"step_size": 0.01, "min_qty": 0.01, "min_notional": 5.0, "quote_precision": 8},
        "LTCEUR": {"step_size": 0.001, "min_qty": 0.001, "min_notional": 5.0, "quote_precision": 8},
        "BCHEUR": {"step_size": 0.001, "min_qty": 0.001, "min_notional": 5.0, "quote_precision": 8},
        "WLDEUR": {"step_size": 0.1, "min_qty": 0.1, "min_notional": 5.0, "quote_precision": 8},
        "ATOMEUR": {"step_size": 0.01, "min_qty": 0.01, "min_notional": 5.0, "quote_precision": 8},
        "XLMEUR": {"step_size": 1.0, "min_qty": 1.0, "min_notional": 5.0, "quote_precision": 8},
        "TRXEUR": {"step_size": 1.0, "min_qty": 1.0, "min_notional": 5.0, "quote_precision": 8},
        "APTEUR": {"step_size": 0.01, "min_qty": 0.01, "min_notional": 5.0, "quote_precision": 8},
        "ICPEUR": {"step_size": 0.01, "min_qty": 0.01, "min_notional": 5.0, "quote_precision": 8},
        "VETEUR": {"step_size": 0.01, "min_qty": 0.01, "min_notional": 5.0, "quote_precision": 8},
        "EGLDEUR": {"step_size": 0.01, "min_qty": 0.01, "min_notional": 5.0, "quote_precision": 8},
        "SEUR": {"step_size": 0.1, "min_qty": 0.1, "min_notional": 5.0, "quote_precision": 8},
        "WLFIEUR": {"step_size": 0.1, "min_qty": 0.1, "min_notional": 5.0, "quote_precision": 8},
        "WINEUR": {"step_size": 1.0, "min_qty": 1.0, "min_notional": 5.0, "quote_precision": 8},
    }

    # Reglas por defecto para otros activos
    DEFAULT_RULE = {
        "step_size": 0.0001,
        "min_qty": 0.0001,
        "min_notional": 5.0,
        "quote_precision": 8
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
        decimals = max(0, -int(math.floor(math.log10(step))))
        adjusted_qty = round(math.floor(raw_qty / step) * step, decimals)

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
