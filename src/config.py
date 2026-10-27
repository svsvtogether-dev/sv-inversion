from pathlib import Path

# Directorios del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

# Configuración del Paper Trading
INITIAL_CAPITAL_EUR = 30.00   # Saldo inicial virtual: 30 €
TRADING_FEE_RATE = 0.001      # Comisión estándar estimada (0.1%)

# Catálogo Universal de Mercados (Cripto, Índices, Acciones, Materias Primas y Forex)
MARKETS_CATALOG = {
    # 1. Criptomonedas (Binance Spot EUR - 24/7)
    "BTCEUR": {"name": "Bitcoin", "category": "crypto", "source": "binance", "currency": "EUR", "symbol_clean": "BTC/EUR"},
    "ETHEUR": {"name": "Ethereum", "category": "crypto", "source": "binance", "currency": "EUR", "symbol_clean": "ETH/EUR"},
    "SOLEUR": {"name": "Solana", "category": "crypto", "source": "binance", "currency": "EUR", "symbol_clean": "SOL/EUR"},

    # 2. Índices Bursátiles Globales & ETFs (Wall Street / Global)
    "SPY": {"name": "S&P 500 (ETF)", "category": "indices", "source": "yahoo", "currency": "USD", "symbol_clean": "S&P 500"},
    "QQQ": {"name": "Nasdaq 100 (ETF)", "category": "indices", "source": "yahoo", "currency": "USD", "symbol_clean": "Nasdaq 100"},

    # 3. Acciones Líderes (Equities)
    "NVDA": {"name": "Nvidia Corp", "category": "stocks", "source": "yahoo", "currency": "USD", "symbol_clean": "Nvidia"},
    "AAPL": {"name": "Apple Inc", "category": "stocks", "source": "yahoo", "currency": "USD", "symbol_clean": "Apple"},
    "MSFT": {"name": "Microsoft", "category": "stocks", "source": "yahoo", "currency": "USD", "symbol_clean": "Microsoft"},

    # 4. Materias Primas / Commodities
    "GC=F": {"name": "Oro (Gold Futures)", "category": "commodities", "source": "yahoo", "currency": "USD", "symbol_clean": "Oro"},
    "CL=F": {"name": "Petróleo Crudo (WTI)", "category": "commodities", "source": "yahoo", "currency": "USD", "symbol_clean": "Petróleo"},

    # 5. Forex / Divisas
    "EURUSD=X": {"name": "Euro / Dólar", "category": "forex", "source": "yahoo", "currency": "USD", "symbol_clean": "EUR/USD"},
    "GBPUSD=X": {"name": "Libra / Dólar", "category": "forex", "source": "yahoo", "currency": "USD", "symbol_clean": "GBP/USD"}
}

SUPPORTED_SYMBOLS = list(MARKETS_CATALOG.keys())
DEFAULT_SYMBOL = "BTCEUR"

# Parámetros de la Estrategia Smart DCA
CONFIG = {
    "symbol": DEFAULT_SYMBOL,
    "initial_capital": INITIAL_CAPITAL_EUR,
    "fee_rate": TRADING_FEE_RATE,
    "order_amount_eur": 10.00,      # Tamaño por compra DCA (€10 permite 3 tramos con €30)
    "min_order_eur": 5.00,          # Mínimo para poder ejecutar una orden
    "take_profit_pct": 2.5,         # Objetivo de beneficio neto (+2.5%)
    "stop_loss_pct": -5.0,          # Límite de pérdida por protección (-5.0%)
    "rsi_buy_threshold": 40.0,      # Comprar cuando RSI está en sobreventa o retroceso (<= 40)
    "rsi_sell_threshold": 65.0,     # Sugerir toma de beneficios si RSI > 65
    "price_drop_trigger_pct": 0.8,  # Si el precio cae > 0.8% respecto a la última compra, promediar
    "candle_interval": "1m",        # Intervalo de velas para análisis
    "candle_limit": 50,             # Número de velas históricas
    "check_interval_seconds": 6,    # Frecuencia de revisión del mercado
    "active_category": "all",       # "all", "crypto", "indices", "stocks", "commodities", "forex"
    "msci_sweep_pct": 50.0          # % de las ganancias netas que se desvían a la Bóveda MSCI World (Ahorro a Largo Plazo)
}
