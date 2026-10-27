import time
import requests
from typing import Dict, List, Optional, Tuple
from .config import MARKETS_CATALOG

BINANCE_API_BASE = "https://api.binance.com/api/v3"
YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class MarketDataFeed:
    def __init__(self, timeout: float = 6.0):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_known_prices: Dict[str, float] = {}
        self.eur_usd_rate = 1.08  # Tasa base por defecto

    def update_eur_usd_rate(self) -> float:
        """Obtiene la tasa de cambio en vivo EUR/USD para convertir cotizaciones de Wall Street a Euros."""
        try:
            url = f"{YAHOO_CHART_BASE}/EURUSD=X?interval=1d&range=1d"
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                rate = float(meta.get("regularMarketPrice", 1.08))
                if rate > 0.5:
                    self.eur_usd_rate = rate
                    return rate
        except Exception as e:
            pass
        return self.eur_usd_rate

    # ----------------------------------------------------
    # FEEDS DE BINANCE (Criptomonedas 24/7)
    # ----------------------------------------------------
    def _get_binance_data(self, symbol: str) -> Tuple[Optional[float], Dict, List[Dict]]:
        price = None
        stats = {}
        candles = []

        try:
            # 1. Precio actual
            p_resp = self.session.get(f"{BINANCE_API_BASE}/ticker/price", params={"symbol": symbol}, timeout=self.timeout)
            if p_resp.status_code == 200:
                price = float(p_resp.json()["price"])

            # 2. Estadísticas 24h
            s_resp = self.session.get(f"{BINANCE_API_BASE}/ticker/24hr", params={"symbol": symbol}, timeout=self.timeout)
            if s_resp.status_code == 200:
                d = s_resp.json()
                stats = {
                    "price": float(d.get("lastPrice", price or 0)),
                    "priceChangePercent": float(d.get("priceChangePercent", 0)),
                    "highPrice": float(d.get("highPrice", 0)),
                    "lowPrice": float(d.get("lowPrice", 0)),
                    "volume": float(d.get("volume", 0)),
                }

            # 3. Velas
            k_resp = self.session.get(f"{BINANCE_API_BASE}/klines", params={"symbol": symbol, "interval": "1m", "limit": 50}, timeout=self.timeout)
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
        except Exception as e:
            print(f"[Error Binance {symbol}]: {e}")

        return price, stats, candles

    # ----------------------------------------------------
    # FEEDS DE YAHOO FINANCE (Acciones, Índices, Oro, Forex)
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
                prev_close = float(meta.get("previousClose", price_native or 1.0))

                chg_pct = ((price_native - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
                stats = {
                    "price": price_native,
                    "priceChangePercent": chg_pct,
                    "highPrice": float(meta.get("regularMarketDayHigh", price_native)),
                    "lowPrice": float(meta.get("regularMarketDayLow", price_native)),
                    "volume": float(meta.get("regularMarketVolume", 0)),
                }

                # Velas
                quotes = res.get("indicators", {}).get("quote", [{}])[0]
                timestamps = res.get("timestamp", [])
                closes = quotes.get("close", [])
                opens = quotes.get("open", [])
                highs = quotes.get("high", [])
                lows = quotes.get("low", [])

                for i in range(len(timestamps)):
                    c = closes[i]
                    if c is not None:
                        candles.append({
                            "time": timestamps[i] * 1000,
                            "open": float(opens[i] if opens[i] is not None else c),
                            "high": float(highs[i] if highs[i] is not None else c),
                            "low": float(lows[i] if lows[i] is not None else c),
                            "close": float(c),
                            "volume": 0
                        })
        except Exception as e:
            print(f"[Error Yahoo {symbol}]: {e}")

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
            return sum(closes) / len(closes)

        multiplier = 2.0 / (period + 1)
        ema = sum(closes[:period]) / period
        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema
        return round(ema, 4)

    @staticmethod
    def calculate_bollinger_bands(closes: List[float], period: int = 20, num_std: float = 2.0) -> Tuple[float, float, float]:
        if len(closes) < period:
            avg = sum(closes) / len(closes) if closes else 0.0
            return avg, avg, avg

        slice_closes = closes[-period:]
        sma = sum(slice_closes) / period
        variance = sum((x - sma) ** 2 for x in slice_closes) / period
        std_dev = variance ** 0.5
        return round(sma + (num_std * std_dev), 4), round(sma, 4), round(sma - (num_std * std_dev), 4)

    # ----------------------------------------------------
    # ANÁLISIS UNIVERSAL CON CONVERSIÓN A EUR
    # ----------------------------------------------------
    def analyze_symbol(self, symbol: str, interval: str = "1m", limit: int = 50) -> Dict:
        meta = MARKETS_CATALOG.get(symbol, {"name": symbol, "source": "binance", "currency": "EUR", "category": "crypto"})
        source = meta.get("source", "binance")
        currency = meta.get("currency", "EUR")

        # Actualizar tipo de cambio EUR/USD periódicamente
        rate = self.eur_usd_rate
        if currency == "USD":
            rate = self.update_eur_usd_rate()

        if source == "binance":
            raw_price, stats_24h, candles = self._get_binance_data(symbol)
        else:
            raw_price, stats_24h, candles = self._get_yahoo_data(symbol)

        if raw_price is not None:
            self.last_known_prices[symbol] = raw_price
        else:
            raw_price = self.last_known_prices.get(symbol, 0.0)

        # Si cotiza en USD, convertir a EUR para la contabilidad unificada
        conversion_factor = (1.0 / rate) if (currency == "USD" and rate > 0) else 1.0
        price_eur = raw_price * conversion_factor

        if not candles:
            return {
                "symbol": symbol,
                "name": meta.get("name", symbol),
                "category": meta.get("category", "crypto"),
                "clean_symbol": meta.get("symbol_clean", symbol),
                "currency": currency,
                "native_price": round(raw_price, 4),
                "price": round(price_eur, 4),
                "rsi": 50.0,
                "ema_fast": round(price_eur, 4),
                "ema_slow": round(price_eur, 4),
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

        return {
            "symbol": symbol,
            "name": meta.get("name", symbol),
            "category": meta.get("category", "crypto"),
            "clean_symbol": meta.get("symbol_clean", symbol),
            "currency": currency,
            "native_price": round(raw_price, 4),
            "price": round(price_eur, 4),
            "rsi": rsi,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "bb_upper": bb_upper,
            "bb_middle": bb_mid,
            "bb_lower": bb_lower,
            "stats_24h": stats_24h,
            "candles": candles[-20:]
        }
