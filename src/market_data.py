import time
import math
from datetime import datetime, timezone
import requests
from typing import Dict, List, Optional, Tuple
from .config import MARKETS_CATALOG
from .kronos_oracle import KronosOracle
from .news_filter import EconomicNewsFilter

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
        self.kronos = KronosOracle(pred_len=6, sample_count=50)
        self.news_filter = EconomicNewsFilter()

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
    def _get_binance_data(self, symbol: str, interval: str = "5m", limit: int = 100) -> Tuple[Optional[float], Dict, List[Dict]]:
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

                # 2. Velas con intervalo optimizado
                k_resp = self.session.get(
                    f"{base_url}/klines",
                    params={"symbol": symbol, "interval": interval, "limit": limit},
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

        if avg_loss == 0 and avg_gain == 0:
            return 50.0
        if avg_loss == 0:
            return 100.0
        if avg_gain == 0:
            return 10.0  # Evita lectura anómala de 0.0 que confunde al bot con una oportunidad irreal

        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 2)

    @staticmethod
    def calculate_sma(closes: List[float], period: int = 50) -> float:
        """Calcula la Media Móvil Simple (SMA) para filtros de tendencia macro."""
        if not closes:
            return 0.0
        if len(closes) < period:
            return adaptive_round(sum(closes) / len(closes))
        return adaptive_round(sum(closes[-period:]) / period)

    @staticmethod
    def calculate_wma(closes: List[float], period: int) -> float:
        """Calcula la Media Móvil Ponderada (WMA) dando mayor peso a las velas más recientes."""
        if not closes:
            return 0.0
        p = min(period, len(closes))
        if p <= 0:
            return 0.0
        sub = closes[-p:]
        denom = p * (p + 1) / 2.0
        weighted_sum = sum((idx + 1) * val for idx, val in enumerate(sub))
        return weighted_sum / denom

    @classmethod
    def calculate_hma(cls, closes: List[float], period: int = 50) -> Tuple[float, float, str]:
        """
        Calcula la Media Móvil de Hull (HMA) de respuesta inmediata sin retraso (zero-lag):
        HMA = WMA(2 * WMA(n/2) - WMA(n), sqrt(n))
        Retorna: (hma_actual, hma_previo, pendiente: 'UP' | 'DOWN' | 'FLAT')
        """
        if not closes:
            return 0.0, 0.0, "FLAT"
        if len(closes) < 5:
            last = adaptive_round(closes[-1])
            return last, last, "FLAT"

        n = min(period, len(closes))
        n2 = max(1, n // 2)
        sq = max(1, int(math.isqrt(n)))

        points_needed = sq + 3
        diff_series = []
        start_idx = max(n, len(closes) - points_needed + 1)
        for end_idx in range(start_idx, len(closes) + 1):
            sub = closes[:end_idx]
            wma_half = cls.calculate_wma(sub, n2)
            wma_full = cls.calculate_wma(sub, n)
            diff = 2.0 * wma_half - wma_full
            diff_series.append(diff)

        if not diff_series:
            wma_val = adaptive_round(cls.calculate_wma(closes, n))
            return wma_val, wma_val, "FLAT"

        hma_current = cls.calculate_wma(diff_series, sq)
        if len(diff_series) >= sq + 1:
            hma_prev = cls.calculate_wma(diff_series[:-1], sq)
        else:
            hma_prev = hma_current

        hma_current_r = adaptive_round(hma_current)
        hma_prev_r = adaptive_round(hma_prev)

        if hma_current_r > hma_prev_r * 1.0001:
            slope = "UP"
        elif hma_current_r < hma_prev_r * 0.9999:
            slope = "DOWN"
        else:
            slope = "FLAT"

        return hma_current_r, hma_prev_r, slope

    @staticmethod
    def get_market_session_info() -> Dict:
        """
        Analiza la ventana de liquidez y volumen institucional global (13:00 a 17:00 UTC: Solapamiento NY y Londres).
        """
        now_utc = datetime.now(timezone.utc)
        hour_utc = now_utc.hour
        minute_utc = now_utc.minute

        # Ventana dorada institucional: 13:00 - 17:00 UTC (8:00 - 12:00 AM NY)
        is_institutional = (13 <= hour_utc < 17)
        # Horas activas regulares: 07:00 - 20:00 UTC
        is_active_hours = (7 <= hour_utc < 20)

        if is_institutional:
            session_name = "Sesión Institucional NY / Londres"
            liquidity_tier = "INSTITUTIONAL"
            desc = "Máximo volumen y dirección fiable"
        elif is_active_hours:
            session_name = "Sesión Europa / América"
            liquidity_tier = "HIGH"
            desc = "Volumen saludable y spreads óptimos"
        else:
            session_name = "Sesión Nocturna / Asiática"
            liquidity_tier = "LOW"
            desc = "Bajo volumen institucional - Mayor riesgo de mechas y trampas"

        return {
            "utc_time": f"{hour_utc:02d}:{minute_utc:02d} UTC",
            "utc_hour": hour_utc,
            "is_institutional_window": is_institutional,
            "is_active_hours": is_active_hours,
            "session_name": session_name,
            "liquidity_tier": liquidity_tier,
            "description": desc
        }

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
    def calculate_smc_signals(candles: List[Dict], conversion_factor: float = 1.0) -> Dict:
        """
        Detección Smart Money Concepts (SMC) determinista (coste cero):
        - bullish_sweep: Barrido de liquidez por debajo del mínimo reciente (24 velas previas) con recuperación.
        - bullish_fvg: Fair Value Gap alcista (vela[i-2].high < vela[i].low) sin invalidar.
        - bearish_fvg_overhead: Fair Value Gap bajista sin mitigar justo encima del precio actual (resistencia).
        """
        default_res = {"bullish_sweep": False, "bullish_fvg": False, "bearish_fvg_overhead": False}
        if not candles or len(candles) < 8:
            return default_res

        cur_close = float(candles[-1].get("close", 0.0)) * conversion_factor
        if cur_close <= 0:
            return default_res

        # 1. Barrido de Liquidez Alcista (Liquidity Sweep)
        ref_window = candles[-27:-3] if len(candles) >= 27 else candles[:-3]
        bullish_sweep = False
        if ref_window:
            swing_low = min(float(c.get("low", 0.0)) * conversion_factor for c in ref_window)
            recent_low = min(float(c.get("low", 0.0)) * conversion_factor for c in candles[-3:])
            if swing_low > 0 and recent_low < swing_low and cur_close > swing_low:
                bullish_sweep = True

        # 2. Fair Value Gaps (FVG) en las últimas 12 velas
        scan = candles[-12:]
        bullish_fvg = False
        bearish_fvg_overhead = False
        for i in range(2, len(scan)):
            c0_high = float(scan[i - 2].get("high", 0.0)) * conversion_factor
            c0_low = float(scan[i - 2].get("low", 0.0)) * conversion_factor
            c2_low = float(scan[i].get("low", 0.0)) * conversion_factor
            c2_high = float(scan[i].get("high", 0.0)) * conversion_factor

            if c0_high > 0 and c0_high < c2_low and cur_close >= c0_high:
                bullish_fvg = True
            if c2_high > 0 and c0_low > c2_high:
                # FVG bajista sin mitigar por encima del precio (actúa como techo)
                if cur_close < c0_low and ((c0_low - cur_close) / cur_close) <= 0.03:
                    bearish_fvg_overhead = True

        return {
            "bullish_sweep": bullish_sweep,
            "bullish_fvg": bullish_fvg,
            "bearish_fvg_overhead": bearish_fvg_overhead,
        }

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

    @staticmethod
    def calculate_atr(candles: List[Dict], period: int = 14, conversion_factor: float = 1.0) -> float:
        """Calcula el Average True Range (ATR) para calibrar el stop y el trailing dinámico según volatilidad."""
        if len(candles) < 2:
            return 0.0

        tr_list = []
        for i in range(1, len(candles)):
            high = candles[i]["high"] * conversion_factor
            low = candles[i]["low"] * conversion_factor
            prev_close = candles[i - 1]["close"] * conversion_factor
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)

        if not tr_list:
            return 0.0

        if len(tr_list) < period:
            return adaptive_round(sum(tr_list) / len(tr_list))

        atr = sum(tr_list[:period]) / period
        for tr in tr_list[period:]:
            atr = (atr * (period - 1) + tr) / period
        return adaptive_round(atr)

    # ----------------------------------------------------
    # ANÁLISIS UNIVERSAL CON ADAPTATIVE ROUNDING
    # ----------------------------------------------------
    def analyze_symbol(self, symbol: str, interval: str = "5m", limit: int = 100) -> Dict:
        meta = MARKETS_CATALOG.get(symbol, {"name": symbol, "source": "binance", "currency": "EUR", "category": "crypto", "sub_category": "top"})
        source = meta.get("source", "binance")
        currency = meta.get("currency", "EUR")
        category = meta.get("category", "crypto")

        # Actualizar tipo de cambio EUR/USD periódicamente (con caché)
        rate = self.eur_usd_rate
        if currency == "USD" and category != "forex":
            rate = self.update_eur_usd_rate()

        if source == "binance":
            raw_price, stats_24h, candles = self._get_binance_data(symbol, interval=interval, limit=limit)
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
                "rsi_prev": 50.0,
                "ema_fast": rounded_eur,
                "ema_slow": rounded_eur,
                "ema_trend": rounded_eur,
                "sma_50": rounded_eur,
                "sma_200": rounded_eur,
                "hma_50": rounded_eur,
                "hma_50_prev": rounded_eur,
                "hma_50_slope": "FLAT",
                "session_info": self.get_market_session_info(),
                "kronos": self.kronos.predict([], rounded_eur),
                "news_status": self.news_filter.get_news_status(),
                "smc": {"bullish_sweep": False, "bullish_fvg": False, "bearish_fvg_overhead": False},
                "bb_upper": 0.0,
                "bb_lower": 0.0,
                "donchian_high_20": rounded_eur,
                "donchian_low_20": rounded_eur,
                "volume_ratio": 1.0,
                "atr": 0.0,
                "atr_pct": 1.5,
                "candle_bullish": False,
                "stats_24h": stats_24h,
                "candles": []
            }

        closes_eur = [c["close"] * conversion_factor for c in candles]
        rsi = self.calculate_rsi(closes_eur, period=14)
        rsi_prev = self.calculate_rsi(closes_eur[:-1], period=14) if len(closes_eur) > 15 else rsi
        ema_fast = self.calculate_ema(closes_eur, period=9)
        ema_slow = self.calculate_ema(closes_eur, period=21)
        ema_trend = self.calculate_ema(closes_eur, period=50)
        sma_50 = self.calculate_sma(closes_eur, period=50)
        sma_200 = self.calculate_sma(closes_eur, period=200) if len(closes_eur) >= 200 else sma_50
        hma_50, hma_50_prev, hma_50_slope = self.calculate_hma(closes_eur, period=50)
        bb_upper, bb_mid, bb_lower = self.calculate_bollinger_bands(closes_eur, period=20, num_std=2.0)
        atr = self.calculate_atr(candles, period=14, conversion_factor=conversion_factor)
        atr_pct = round((atr / rounded_eur * 100), 2) if rounded_eur > 0 else 1.5
        session_info = self.get_market_session_info()
        kronos_data = self.kronos.predict(candles, rounded_eur)
        news_status = self.news_filter.get_news_status()
        smc_signals = self.calculate_smc_signals(candles, conversion_factor=conversion_factor)

        last_c = candles[-1] if candles else {}
        candle_bullish = float(last_c.get("close", 0)) >= float(last_c.get("open", 0))

        # Canal Donchian (20 velas previas) y Ratio de Volumen para detección de Trend Breakouts
        prev_window = candles[-21:-1] if len(candles) > 1 else candles
        donchian_high_20 = adaptive_round(max(float(c.get("high", 0)) * conversion_factor for c in prev_window)) if prev_window else rounded_eur
        donchian_low_20 = adaptive_round(min(float(c.get("low", 0)) * conversion_factor for c in prev_window)) if prev_window else rounded_eur
        vols = [float(c.get("volume", 0)) for c in prev_window if float(c.get("volume", 0)) > 0]
        avg_vol_20 = (sum(vols) / len(vols)) if vols else 0.0
        cur_vol = float(last_c.get("volume", 0))
        volume_ratio = round(cur_vol / avg_vol_20, 2) if (avg_vol_20 > 0 and cur_vol > 0) else 1.0

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
            "rsi_prev": rsi_prev,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ema_trend": ema_trend,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "hma_50": hma_50,
            "hma_50_prev": hma_50_prev,
            "hma_50_slope": hma_50_slope,
            "session_info": session_info,
            "kronos": kronos_data,
            "news_status": news_status,
            "smc": smc_signals,
            "bb_upper": bb_upper,
            "bb_middle": bb_mid,
            "bb_lower": bb_lower,
            "donchian_high_20": donchian_high_20,
            "donchian_low_20": donchian_low_20,
            "volume_ratio": volume_ratio,
            "atr": atr,
            "atr_pct": atr_pct,
            "candle_bullish": candle_bullish,
            "stats_24h": stats_24h,
            "candles": candles[-20:]
        }
        self.last_analysis_cache[symbol] = result
        return result
