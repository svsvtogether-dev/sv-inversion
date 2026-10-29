from pathlib import Path

# Directorios del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

# Configuración del Paper Trading / Prueba con fondos iniciales
INITIAL_CAPITAL_EUR = 15.00  # Saldo inicial: 15,00 € (ajustado a la primera inversión)
TRADING_FEE_RATE = 0.001     # Comisión Binance Spot estándar (0.10%)

# Catálogo Exclusivo de Mercados de Binance Spot (29 Pares EUR Oficiales - 24/7)
MARKETS_CATALOG = {
    "BTCEUR": {"name": "Bitcoin", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "BTC/EUR"},
    "ETHEUR": {"name": "Ethereum", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "ETH/EUR"},
    "BNBEUR": {"name": "BNB (Binance)", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "BNB/EUR"},
    "SOLEUR": {"name": "Solana", "category": "crypto", "sub_category": "top", "source": "binance", "currency": "EUR", "symbol_clean": "SOL/EUR"},
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
    "WLFIEUR": {"name": "World Liberty Financial", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "WLFI/EUR"},
    "WINEUR": {"name": "WINkLink", "category": "crypto", "sub_category": "l1", "source": "binance", "currency": "EUR", "symbol_clean": "WIN/EUR"}
}

SUPPORTED_SYMBOLS = list(MARKETS_CATALOG.keys())
DEFAULT_SYMBOL = "BTCEUR"

# Parámetros de la Estrategia Smart DCA Cuantitativa
CONFIG = {
    "symbol": DEFAULT_SYMBOL,
    "initial_capital": INITIAL_CAPITAL_EUR,
    "fee_rate": TRADING_FEE_RATE,
    "order_amount_eur": 5.00,       # Tamaño por compra DCA (€5.00 permite 3 tramos cumpliendo el MIN_NOTIONAL de Binance)
    "min_order_eur": 5.00,          # Mínimo para poder ejecutar una orden (cumple MIN_NOTIONAL de Binance)
    "take_profit_pct": 4.5,         # Objetivo de beneficio neto (+4.5% - Asimetría matemática favorable)
    "stop_loss_pct": -3.5,          # Límite de pérdida por protección estricta (-3.5%)
    "rsi_buy_threshold": 35.0,      # Comprar cuando RSI está en sobreventa real (<= 35)
    "rsi_sell_threshold": 65.0,     # Sugerir toma de beneficios si RSI >= 65 con ganancia positiva
    "price_drop_trigger_pct": 1.5,  # Si el precio cae >= 1.5% respecto a la última compra, promediar
    "candle_interval": "1m",        # Intervalo de velas para análisis
    "candle_limit": 50,             # Número de velas históricas
    "check_interval_seconds": 6,    # Frecuencia de revisión del mercado
    "active_category": "all",       # Escanea todos los mercados de Binance
    "msci_sweep_pct": 0.0           # % de las ganancias netas que se desvían a la Bóveda MSCI World
}
