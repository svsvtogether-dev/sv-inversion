import time
import requests
from typing import Dict, List, Optional, Tuple
from .config import MARKETS_CATALOG

BINANCE_ENDPOINTS = [
    "https://data-api.binance.vision/api/v3",
    "https://api.binance.com/api/v3",
]
YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

YAHOO_CRYPTO_MAP = {
    "BTCEUR": "BTC-EUR",
    "ETHEUR": "ETH-EUR",
    "SOLEUR": "SOL-EUR",
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def adaptive_round(val: Optional[float]) -> float:
    """Ajusta dinámicamente la precisión de redondeo para soportar desde micro-memecoins (< 0.0001€) hasta BTC."""
    if val is None or val == 0:
        return 0.0
    abs_val = abs(val)
    if abs_val < 0.0001:
        return round(val, 8)
    elif abs_val < 0.01:
        return round(val, 6)
    else:
        return round(val, 4)

class MarketDataFeed:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_known_prices: Dict[str, float] = {}
        self.last_known_prices_eur: Dict[str, float] = {}
        self.last_analysis_cache: Dict[str, Dict] = {}
        self.eur_usd_rate = 1.08  # Tasa base por defecto
        self.last_rate_update = 0.0

    def update_eur_usd_rate(self) -> float:
        """Obtiene la tasa de cambio en vivo EUR/USD (con caché de 60s) para convertir cotizaciones USD a Euros."""
        now = time.time()
        if now - self.last_rate_update < 60.0 and self.eur_usd_rate > 0.5:
            return self.eur_usd_rate

        try:
            url = f"{YAHOO_CHART_BASE}/EURUSD=X?interval=1d&range=1d"
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                rate = float(meta.get("regularMarketPrice", 1.08))
                if rate > 0.5:
                    self.eur_usd_rate = rate
                    self.last_rate_update = now
                    return rate
        except Exception:
            pass
        return self.eur_usd_rate

    # ----------------------------------------------------
    # FEEDS DE BINANCE (Criptomonedas 24/7 con Fallback Global)
    # ----------------------------------------------------
    def _get_binance_data(self, symbol: str) -> Tuple[Optional[float], Dict, List[Dict]]:
        price = None
        stats = {}
        candles = []

        for base_url in BINANCE_ENDPOINTS:
            try:
                # 1. Estadísticas 24h y precio actual
                s_resp = self.session.get(
                    f"{base_url}/ticker/24hr",
                    params={"symbol": symbol},
                    timeout=self.timeout
                )
                if s_resp.status_code == 200:
                    d = s_resp.json()
                    price = float(d.get("lastPrice", 0))
                    stats = {
                        "price": adaptive_round(price),
                        "priceChangePercent": round(float(d.get("priceChangePercent", 0)), 2),
                        "highPrice": adaptive_round(float(d.get("highPrice", 0))),
                        "lowPrice": adaptive_round(float(d.get("lowPrice", 0))),
                        "volume": float(d.get("volume", 0)),
                    }

                # 2. Velas
                k_resp = self.session.get(
                    f"{base_url}/klines",
                    params={"symbol": symbol, "interval": "1m", "limit": 50},
                    timeout=self.timeout
                )
                if k_resp.status_code == 200:
                    for k in k_resp.json():
                        candles.append({
                            "time": int(k[0]),
                            "open": float(k[1]),
                            "high": float(k[2]),
                            "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5]),
                        })

                if price and price > 0 and candles:
                    return price, stats, candles
            except Exception:
                continue

        # Fallback a Yahoo Finance si Binance está restringido
        yahoo_sym = YAHOO_CRYPTO_MAP.get(symbol)
        if yahoo_sym:
            return self._get_yahoo_data(yahoo_sym)

        return price, stats, candles

    # ----------------------------------------------------
    # FEEDS DE YAHOO FINANCE (Fallback secundario)
    # ----------------------------------------------------
    def _get_yahoo_data(self, symbol: str) -> Tuple[Optional[float], Dict, List[Dict]]:
        price_native = None
        stats = {}
        candles = []

        try:
            url = f"{YAHOO_CHART_BASE}/{symbol}?interval=5m&range=1d"
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                res = resp.json()["chart"]["result"][0]
                meta = res["meta"]
                price_native = float(meta.get("regularMarketPrice", 0.0))
                prev_close = float(meta.get("previousClose") or meta.get("chartPreviousClose") or price_native or 1.0)

                chg_pct = ((price_native - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
                stats = {
                    "price": adaptive_round(price_native),
                    "priceChangePercent": round(chg_pct, 2),
                    "highPrice": adaptive_round(float(meta.get("regularMarketDayHigh") or price_native)),
                    "lowPrice": adaptive_round(float(meta.get("regularMarketDayLow") or price_native)),
                    "volume": float(meta.get("regularMarketVolume") or 0),
                }

                # Velas
                quotes = res.get("indicators", {}).get("quote", [{}])[0]
                timestamps = res.get("timestamp", [])
                closes = quotes.get("close", [])
                opens = quotes.get("open", [])
                highs = quotes.get("high", [])
                lows = quotes.get("low", [])

                for i in range(len(timestamps)):
                    c = closes[i] if i < len(closes) else None
                    if c is not None:
                        candles.append({
                            "time": timestamps[i] * 1000,
                            "open": float(opens[i] if (i < len(opens) and opens[i] is not None) else c),
                            "high": float(highs[i] if (i < len(highs) and highs[i] is not None) else c),
                            "low": float(lows[i] if (i < len(lows) and lows[i] is not None) else c),
                            "close": float(c),
                            "volume": 0
                        })
        except Exception:
            pass

        return price_native, stats, candles

    # ----------------------------------------------------
    # INDICADORES TÉCNICOS
    # ----------------------------------------------------
    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(0.0, d) for d in deltas]
        losses = [max(0.0, -d) for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 2)

    @staticmethod
    def calculate_ema(closes: List[float], period: int) -> float:
        if not closes:
            return 0.0
        if len(closes) < period:
            return adaptive_round(sum(closes) / len(closes))

        multiplier = 2.0 / (period + 1)
        ema = sum(closes[:period]) / period
        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema
        return adaptive_round(ema)

    @staticmethod
    def calculate_bollinger_bands(closes: List[float], period: int = 20, num_std: float = 2.0) -> Tuple[float, float, float]:
        if len(closes) < period:
            avg = adaptive_round(sum(closes) / len(closes)) if closes else 0.0
            return avg, avg, avg

        slice_closes = closes[-period:]
        sma = sum(slice_closes) / period
        variance = sum((x - sma) ** 2 for x in slice_closes) / period
        std_dev = variance ** 0.5
        upper = adaptive_round(sma + (num_std * std_dev))
        middle = adaptive_round(sma)
        lower = adaptive_round(sma - (num_std * std_dev))
        return upper, middle, lower

    # ----------------------------------------------------
    # ANÁLISIS UNIVERSAL CON ADAPTATIVE ROUNDING
    # ----------------------------------------------------
    def analyze_symbol(self, symbol: str, interval: str = "1m", limit: int = 50) -> Dict:
        meta = MARKETS_CATALOG.get(symbol, {"name": symbol, "source": "binance", "currency": "EUR", "category": "crypto", "sub_category": "top"})
        source = meta.get("source", "binance")
        currency = meta.get("currency", "EUR")
        category = meta.get("category", "crypto")

        # Actualizar tipo de cambio EUR/USD periódicamente (con caché)
        rate = self.eur_usd_rate
        if currency == "USD" and category != "forex":
            rate = self.update_eur_usd_rate()

        if source == "binance":
            raw_price, stats_24h, candles = self._get_binance_data(symbol)
        else:
            raw_price, stats_24h, candles = self._get_yahoo_data(symbol)

        if raw_price is not None and raw_price > 0:
            self.last_known_prices[symbol] = raw_price
        else:
            raw_price = self.last_known_prices.get(symbol, 0.0)

        # Conversión a EUR si fuese necesario
        conversion_factor = (1.0 / rate) if (currency == "USD" and category != "forex" and rate > 0) else 1.0
        price_eur = raw_price * conversion_factor

        rounded_raw = adaptive_round(raw_price)
        rounded_eur = adaptive_round(price_eur)

        if price_eur > 0:
            self.last_known_prices_eur[symbol] = rounded_eur

        if not candles:
            cached = self.last_analysis_cache.get(symbol)
            if cached and cached.get("price", 0) > 0:
                return cached
            return {
                "symbol": symbol,
                "name": meta.get("name", symbol),
                "category": category,
                "sub_category": meta.get("sub_category", "top"),
                "clean_symbol": meta.get("symbol_clean", symbol),
                "currency": currency,
                "native_price": rounded_raw,
                "price": rounded_eur,
                "rsi": 50.0,
                "ema_fast": rounded_eur,
                "ema_slow": rounded_eur,
                "bb_upper": 0.0,
                "bb_lower": 0.0,
                "stats_24h": stats_24h,
                "candles": []
            }

        closes_eur = [c["close"] * conversion_factor for c in candles]
        rsi = self.calculate_rsi(closes_eur, period=14)
        ema_fast = self.calculate_ema(closes_eur, period=9)
        ema_slow = self.calculate_ema(closes_eur, period=21)
        bb_upper, bb_mid, bb_lower = self.calculate_bollinger_bands(closes_eur, period=20, num_std=2.0)

        result = {
            "symbol": symbol,
            "name": meta.get("name", symbol),
            "category": category,
            "sub_category": meta.get("sub_category", "top"),
            "clean_symbol": meta.get("symbol_clean", symbol),
            "currency": currency,
            "native_price": rounded_raw,
            "price": rounded_eur,
            "rsi": rsi,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "bb_upper": bb_upper,
            "bb_middle": bb_mid,
            "bb_lower": bb_lower,
            "stats_24h": stats_24h,
            "candles": candles[-20:]
        }
        self.last_analysis_cache[symbol] = result
        return result
