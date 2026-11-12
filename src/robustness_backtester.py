import random
from typing import Dict, List, Optional
from .market_data import MarketDataFeed
from .trading_council import TradingCouncil
from .config import CONFIG, TRADING_FEE_RATE


class RobustnessBacktester:
    """
    Motor de Validación Cuantitativa y Robustez (Inspirado en @hobbiecode):
    1. Simulación histórica barra a barra sin look-ahead bias (con comisiones reales).
    2. Walk-Forward Testing (In-Sample vs Out-of-Sample) para detectar sobreoptimización.
    3. Simulación Monte Carlo (N iteraciones con permutación de trades y ruido de slippage)
       para medir el Drawdown en el peor 5% de escenarios (p95) y la probabilidad de beneficio.
    """

    def __init__(self, config: Optional[Dict] = None, fee_rate: float = TRADING_FEE_RATE):
        self.config = config or dict(CONFIG)
        self.fee_rate = fee_rate
        self.council = TradingCouncil()

    def fetch_binance_klines(self, symbol: str = "BTCEUR", interval: str = "1h", limit: int = 500) -> List[Dict]:
        """Descarga velas históricas reales de Binance reutilizando MarketDataFeed."""
        feed = MarketDataFeed()
        _, _, candles = feed._get_binance_data(symbol=symbol, interval=interval, limit=min(max(limit, 100), 1000))
        return candles or []

    def _build_bar_analysis(self, symbol: str, window: List[Dict]) -> Dict:
        """Construye el snapshot técnico de una barra usando solo velas pasadas (cero look-ahead)."""
        closes = [c["close"] for c in window]
        last_c = window[-1]
        price = float(last_c["close"])
        rsi = MarketDataFeed.calculate_rsi(closes, period=14)
        rsi_prev = MarketDataFeed.calculate_rsi(closes[:-1], period=14) if len(closes) > 15 else rsi
        ema_trend = MarketDataFeed.calculate_ema(closes, period=50)
        ema_200 = MarketDataFeed.calculate_ema(closes, period=200) if len(closes) >= 200 else ema_trend
        hma_50, hma_50_prev, hma_slope = MarketDataFeed.calculate_hma(closes, period=50)
        bb_upper, bb_mid, bb_lower = MarketDataFeed.calculate_bollinger_bands(closes, period=20, num_std=2.0)
        atr = MarketDataFeed.calculate_atr(window, period=14, conversion_factor=1.0)
        atr_pct = round((atr / price * 100.0), 2) if price > 0 else 1.5

        prev_20 = window[-21:-1] if len(window) > 1 else window
        donchian_high = max(float(c["high"]) for c in prev_20)
        vols = [float(c.get("volume", 0.0)) for c in prev_20 if float(c.get("volume", 0.0)) > 0]
        avg_vol = (sum(vols) / len(vols)) if vols else 0.0
        cur_vol = float(last_c.get("volume", 0.0))
        volume_ratio = round(cur_vol / avg_vol, 2) if (avg_vol > 0 and cur_vol > 0) else 1.0

        return {
            "symbol": symbol,
            "price": price,
            "rsi": rsi,
            "rsi_prev": rsi_prev,
            "ema_trend": ema_trend,
            "ema_200": ema_200,
            "hma_50": hma_50,
            "hma_50_prev": hma_50_prev,
            "hma_50_slope": hma_slope,
            "bb_upper": bb_upper,
            "bb_middle": bb_mid,
            "bb_lower": bb_lower,
            "donchian_high_20": donchian_high,
            "volume_ratio": volume_ratio,
            "atr": atr,
            "atr_pct": atr_pct,
            "candle_bullish": float(last_c["close"]) >= float(last_c["open"]),
            "session_info": {"is_institutional_window": True, "liquidity_tier": "HIGH"},
            "kronos": {"available": False},
            "news_status": {"is_shield_active": False},
            "smc": MarketDataFeed.calculate_smc_signals(window, conversion_factor=1.0),
            "regime": MarketDataFeed.calculate_regime(window),
        }

    def simulate_strategy(
        self,
        candles: List[Dict],
        symbol: str = "BTCEUR",
        strategy_mode: str = "MULTI",
        initial_capital: float = 100.0,
    ) -> Dict:
        """
        Simula barra a barra la estrategia elegida:
        - 'DCA_REVERSION'
        - 'TREND_BREAKOUT'
        - 'MULTI' (cartera descorrelacionada que combina ambas)
        """
        warmup = 205 if len(candles) >= 260 else 55
        if len(candles) <= warmup + 5:
            return {
                "trades_count": 0,
                "total_return_pct": 0.0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "trade_returns_pct": [],
                "strategy_breakdown": {},
            }

        equity = initial_capital
        peak_equity = initial_capital
        max_dd_pct = 0.0
        position: Optional[Dict] = None
        trade_returns: List[float] = []
        breakdown: Dict[str, int] = {"DCA_REVERSION": 0, "TREND_BREAKOUT": 0}

        tp_base = float(self.config.get("take_profit_pct", 3.5))
        sl_base = float(self.config.get("stop_loss_pct", -3.0))
        be_trigger = float(self.config.get("breakeven_trigger_pct", 1.6))
        rsi_sell = float(self.config.get("rsi_sell_threshold", 68.0))

        for i in range(warmup, len(candles)):
            window = candles[: i + 1]
            analysis = self._build_bar_analysis(symbol, window)
            price = analysis["price"]

            if position is not None:
                entry_price = position["entry_price"]
                if price > position["highest_price"]:
                    position["highest_price"] = price

                raw_pnl_pct = ((price - entry_price) / entry_price) * 100.0
                max_gain_pct = ((position["highest_price"] - entry_price) / entry_price) * 100.0
                tag = position["strategy_tag"]
                atr_pct = analysis["atr_pct"]

                exit_triggered = False
                if tag == "TREND_BREAKOUT":
                    trail_floor = max_gain_pct - max(2.0, atr_pct * 2.5)
                    ema_trend = float(analysis.get("ema_trend", 0.0))
                    if (max_gain_pct >= 1.5 and raw_pnl_pct <= trail_floor) or (ema_trend > 0 and price < ema_trend * 0.985) or raw_pnl_pct <= -5.0:
                        exit_triggered = True
                else:
                    if max_gain_pct >= be_trigger and raw_pnl_pct <= 0.50:
                        exit_triggered = True
                    elif max_gain_pct >= 3.0:
                        trail_floor = max_gain_pct - max(1.2, atr_pct * 1.2)
                        if trail_floor >= 0.8 and raw_pnl_pct <= trail_floor:
                            exit_triggered = True
                    if not exit_triggered:
                        bb_mid = float(analysis.get("bb_middle", 0.0))
                        if raw_pnl_pct >= tp_base or raw_pnl_pct <= sl_base:
                            exit_triggered = True
                        elif bb_mid > 0 and price >= bb_mid and raw_pnl_pct >= 1.5:
                            exit_triggered = True
                        elif analysis["rsi"] >= rsi_sell and raw_pnl_pct >= 2.0:
                            exit_triggered = True

                if exit_triggered or i == len(candles) - 1:
                    net_ret_pct = raw_pnl_pct - (self.fee_rate * 2.0 * 100.0)
                    equity *= 1.0 + (net_ret_pct / 100.0)
                    trade_returns.append(round(net_ret_pct, 4))
                    breakdown[tag] = breakdown.get(tag, 0) + 1
                    position = None

                    if equity > peak_equity:
                        peak_equity = equity
                    dd = ((peak_equity - equity) / peak_equity) * 100.0 if peak_equity > 0 else 0.0
                    if dd > max_dd_pct:
                        max_dd_pct = dd
            else:
                if strategy_mode == "DCA_REVERSION":
                    debate = self.council.debate_entry(symbol, analysis, equity, self.config)
                elif strategy_mode == "TREND_BREAKOUT":
                    debate = self.council.debate_breakout_entry(symbol, analysis, equity, self.config)
                else:
                    debate = self.council.debate_multi_strategy(symbol, analysis, equity, self.config)

                if debate.get("approved"):
                    position = {
                        "entry_price": price,
                        "highest_price": price,
                        "strategy_tag": debate.get("strategy_tag", "DCA_REVERSION"),
                    }

        wins = [r for r in trade_returns if r > 0]
        losses = [abs(r) for r in trade_returns if r < 0]
        gross_win = sum(wins)
        gross_loss = sum(losses)
        profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (round(gross_win, 2) if gross_win > 0 else 0.0)
        win_rate = round((len(wins) / len(trade_returns)) * 100.0, 1) if trade_returns else 0.0
        total_ret = round(((equity - initial_capital) / initial_capital) * 100.0, 2)

        return {
            "trades_count": len(trade_returns),
            "total_return_pct": total_ret,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown_pct": round(max_dd_pct, 2),
            "trade_returns_pct": trade_returns,
            "strategy_breakdown": breakdown,
        }

    def run_walk_forward(
        self,
        candles: List[Dict],
        symbol: str = "BTCEUR",
        strategy_mode: str = "MULTI",
        train_ratio: float = 0.65,
    ) -> Dict:
        """Divide el histórico en In-Sample (IS) y Out-of-Sample (OOS) para validar consistencia futura."""
        split_idx = int(len(candles) * train_ratio)
        is_candles = candles[:split_idx]
        oos_candles = candles[max(0, split_idx - 55) :]  # conserva warmup técnico sin filtrar señales futuras

        is_res = self.simulate_strategy(is_candles, symbol=symbol, strategy_mode=strategy_mode)
        oos_res = self.simulate_strategy(oos_candles, symbol=symbol, strategy_mode=strategy_mode)

        is_ret = is_res["total_return_pct"]
        oos_ret = oos_res["total_return_pct"]
        if is_ret > 0:
            wfe = round(oos_ret / is_ret, 2)
        else:
            wfe = 1.0 if oos_ret >= 0 else 0.0

        return {
            "in_sample": {k: v for k, v in is_res.items() if k != "trade_returns_pct"},
            "out_of_sample": {k: v for k, v in oos_res.items() if k != "trade_returns_pct"},
            "walk_forward_efficiency": wfe,
            "oos_passed": oos_ret >= 0.0 and oos_res["trades_count"] >= 1,
        }

    def run_monte_carlo(self, trade_returns_pct: List[float], iterations: int = 300, seed: int = 42) -> Dict:
        """Permuta el orden de las operaciones y añade ruido de slippage para medir riesgo real."""
        if len(trade_returns_pct) < 2:
            return {
                "iterations": 0,
                "mc_median_return_pct": round(sum(trade_returns_pct), 2),
                "mc_p95_drawdown_pct": 0.0,
                "mc_prob_profit_pct": 100.0 if sum(trade_returns_pct) > 0 else 0.0,
            }

        rng = random.Random(seed)
        final_returns: List[float] = []
        max_drawdowns: List[float] = []

        for _ in range(iterations):
            shuffled = list(trade_returns_pct)
            rng.shuffle(shuffled)
            eq = 100.0
            peak = 100.0
            worst_dd = 0.0
            for ret in shuffled:
                jitter = rng.uniform(-0.05, 0.05)
                eq *= 1.0 + ((ret + jitter) / 100.0)
                if eq > peak:
                    peak = eq
                dd = ((peak - eq) / peak) * 100.0 if peak > 0 else 0.0
                if dd > worst_dd:
                    worst_dd = dd
            final_returns.append(eq - 100.0)
            max_drawdowns.append(worst_dd)

        final_returns.sort()
        max_drawdowns.sort()
        median_ret = final_returns[len(final_returns) // 2]
        p95_idx = min(len(max_drawdowns) - 1, int(len(max_drawdowns) * 0.95))
        p95_dd = max_drawdowns[p95_idx]
        prob_profit = (sum(1 for r in final_returns if r > 0) / len(final_returns)) * 100.0

        return {
            "iterations": iterations,
            "mc_median_return_pct": round(median_ret, 2),
            "mc_p95_drawdown_pct": round(p95_dd, 2),
            "mc_prob_profit_pct": round(prob_profit, 1),
        }

    def evaluate_robustness(
        self,
        symbol: str = "BTCEUR",
        interval: str = "4h",
        limit: int = 1000,
        candles: Optional[List[Dict]] = None,
        strategy_mode: str = "MULTI",
    ) -> Dict:
        """Ejecuta el pipeline completo: Backtest + Walk-Forward + Monte Carlo."""
        bars = candles if candles is not None else self.fetch_binance_klines(symbol=symbol, interval=interval, limit=limit)
        if len(bars) < 80:
            return {
                "symbol": symbol,
                "strategy_mode": strategy_mode,
                "candles_analyzed": len(bars),
                "verdict": "INSUFFICIENT_DATA",
                "robustness_score": 0.0,
            }

        full_sim = self.simulate_strategy(bars, symbol=symbol, strategy_mode=strategy_mode)
        wf = self.run_walk_forward(bars, symbol=symbol, strategy_mode=strategy_mode)
        mc = self.run_monte_carlo(full_sim["trade_returns_pct"])

        score = 0.0
        if full_sim["trades_count"] >= 3:
            score += 20.0
        if full_sim["total_return_pct"] > 0:
            score += 20.0
        if full_sim["profit_factor"] >= 1.2:
            score += 15.0
        if wf["oos_passed"]:
            score += 25.0
        if mc["mc_prob_profit_pct"] >= 55.0:
            score += 10.0
        if mc["mc_p95_drawdown_pct"] <= 15.0:
            score += 10.0

        if full_sim["trades_count"] < 2:
            verdict = "INSUFFICIENT_TRADES"
        elif score >= 70.0:
            verdict = "ROBUST"
        elif score >= 45.0:
            verdict = "MODERATE"
        else:
            verdict = "FRAGILE"

        return {
            "symbol": symbol,
            "interval": interval,
            "strategy_mode": strategy_mode,
            "candles_analyzed": len(bars),
            "full_backtest": {k: v for k, v in full_sim.items() if k != "trade_returns_pct"},
            "walk_forward": wf,
            "monte_carlo": mc,
            "robustness_score": round(score, 1),
            "verdict": verdict,
        }
