from pathlib import Path

# Directorios del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

# Configuración del Paper Trading / Prueba con fondos iniciales
INITIAL_CAPITAL_EUR = 50.00  # Saldo inicial: 50,00 € (ajustado para la simulación de Automaton)
TRADING_FEE_RATE = 0.001     # Comisión Binance Spot estándar (0.10%)

# Catálogo Exclusivo de Mercados de Binance Spot (29 Pares EUR Oficiales - 24/7)
MARKETS_CATALOG = {
    "BTCEUR": {"name": "Bitcoin", "category": "crypto", "sub_category": "top4", "source": "binance", "currency": "EUR", "symbol_clean": "BTC/EUR"},
    "ETHEUR": {"name": "Ethereum", "category": "crypto", "sub_category": "top4", "source": "binance", "currency": "EUR", "symbol_clean": "ETH/EUR"},
    "BNBEUR": {"name": "BNB (Binance)", "category": "crypto", "sub_category": "top4", "source": "binance", "currency": "EUR", "symbol_clean": "BNB/EUR"},
    "SOLEUR": {"name": "Solana", "category": "crypto", "sub_category": "top4", "source": "binance", "currency": "EUR", "symbol_clean": "SOL/EUR"},
    "XRPEUR": {"name": "XRP (Ripple)", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "XRP/EUR"},
    "DOGEEUR": {"name": "Dogecoin", "category": "crypto", "sub_category": "memes", "source": "binance", "currency": "EUR", "symbol_clean": "DOGE/EUR"},
    "ADAEUR": {"name": "Cardano", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "ADA/EUR"},
    "AVAXEUR": {"name": "Avalanche", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "AVAX/EUR"},
    "LINKEUR": {"name": "Chainlink", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "LINK/EUR"},
    "DOTEUR": {"name": "Polkadot", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "DOT/EUR"},
    "SUIEUR": {"name": "Sui", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "SUI/EUR"},
    "PEPEEUR": {"name": "Pepe", "category": "crypto", "sub_category": "memes", "source": "binance", "currency": "EUR", "symbol_clean": "PEPE/EUR"},
    "SHIBEUR": {"name": "Shiba Inu", "category": "crypto", "sub_category": "memes", "source": "binance", "currency": "EUR", "symbol_clean": "SHIB/EUR"},
    "NEAREUR": {"name": "NEAR Protocol", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "NEAR/EUR"},
    "POLEUR": {"name": "Polygon (POL)", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "POL/EUR"},
    "RENDEREUR": {"name": "Render", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "RENDER/EUR"},
    "LTCEUR": {"name": "Litecoin", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "LTC/EUR"},
    "BCHEUR": {"name": "Bitcoin Cash", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "BCH/EUR"},
    "WLDEUR": {"name": "Worldcoin", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "WLD/EUR"},
    "ATOMEUR": {"name": "Cosmos", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "ATOM/EUR"},
    "XLMEUR": {"name": "Stellar", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "XLM/EUR"},
    "TRXEUR": {"name": "TRON", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "TRX/EUR"},
    "APTEUR": {"name": "Aptos", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "APT/EUR"},
    "ICPEUR": {"name": "Internet Computer", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "ICP/EUR"},
    "VETEUR": {"name": "VeChain", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "VET/EUR"},
    "EGLDEUR": {"name": "MultiversX", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "EGLD/EUR"},
    "SEUR": {"name": "Sonic (S)", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "S/EUR"},
    "WINEUR": {"name": "WINkLink", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "WIN/EUR"}
}

SUPPORTED_SYMBOLS = list(MARKETS_CATALOG.keys())
TOP4_SYMBOLS = ["BTCEUR", "ETHEUR", "BNBEUR", "SOLEUR"]
DEFAULT_SYMBOL = "BTCEUR"

# Parámetros de la Estrategia Smart DCA Cuantitativa Optimizada para Win Rate > 65%
CONFIG = {
    "symbol": DEFAULT_SYMBOL,
    "initial_capital": INITIAL_CAPITAL_EUR,
    "fee_rate": TRADING_FEE_RATE,
    "order_amount_eur": 50.00,      # 1 posición única con el capital disponible (sin promediar a la baja)
    "min_order_eur": 5.00,          # Mínimo para poder ejecutar una orden (cumple MIN_NOTIONAL de Binance)
    "take_profit_pct": 25.0,        # Sin techo corto: Trailing Stop 2.0x ATR deja correr las tendencias
    "stop_loss_pct": -4.5,          # Límite de pérdida ajustado a volatilidad 4H (-4.5%)
    "breakeven_trigger_pct": 2.8,   # Al subir >= +2.8%, el SL sube a +0.50% (sin ahogar ganadoras tempranas)
    "early_take_profit_pct": 3.5,   # Ganancia mínima para salidas técnicas dinámicas
    "rsi_buy_threshold": 29.0,      # Comprar solo cuando RSI entra en sobreventa genuina (<= 29)
    "rsi_sell_threshold": 85.0,     # No cortar tendencias por RSI temprano; manda el Trailing Stop 2.0x ATR
    "breakout_donchian_period": 20, # Ventana Donchian validada en Walk-Forward (shift 1, sin look-ahead)
    "breakout_atr_mult": 2.0,       # Multiplicador ATR del Trailing Stop (validado 2.0x)
    "breakout_min_trail_pct": 2.0,  # Margen mínimo del Trailing Stop (2.0%)
    "breakout_ema_exit_factor": 0.985, # Cierre si pierde EMA 50 por >1.5%
    "breakout_volume_min_ratio": 1.1,  # Volumen mínimo confirmado (>= 1.10x media 20)
    "max_drawdown_pct": 15.0,       # Freno por drawdown total (-15% desde máximo exige reinicio manual)
    "sma_period": 50,               # Período de la Media Móvil Simple (SMA) para filtro de tendencia macro
    "hma_period": 50,               # Período de la Media Móvil de Hull (HMA) de respuesta rápida sin retraso
    "session_filter_enabled": True, # Filtro de liquidez horaria institucional (Sesión NY / Londres 13-17 UTC)
    "price_drop_trigger_pct": 3.0,  # Si el precio cae >= 3.0% respecto a la última compra, promediar
    "candle_interval": "4h",        # Temporalidad 4H (filtra ruido aleatorio y comisiones excesivas)
    "candle_limit": 250,            # 250 velas históricas (permite calcular EMA 200 macro)
    "check_interval_seconds": 6,    # Frecuencia de revisión del mercado
    "active_category": "top4",      # Estrategia recomendada: Top 4 Líderes Blue-Chips (BTC, ETH, BNB, SOL)
    "msci_sweep_pct": 0.0           # % de las ganancias netas que se desvían a la Bóveda MSCI World
}
