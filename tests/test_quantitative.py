import sys
from pathlib import Path
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.market_data import MarketDataFeed
from src.strategy import SmartDCAStrategy
from src.automaton_brain import AutomatonBrain
from src.trading_council import TradingCouncil
from src.robustness_backtester import RobustnessBacktester
from src.binance_client import BinanceSpotClient
from src.kronos_oracle import KronosOracle
from src.news_filter import EconomicNewsFilter
from src.config import CONFIG

def test_all():
    feed = MarketDataFeed()

    # 1. Test WMA
    print("Testing calculate_wma...")
    wma = feed.calculate_wma([10.0, 20.0, 30.0], period=3)
    expected_wma = (10.0*1 + 20.0*2 + 30.0*3) / 6.0
    assert abs(wma - expected_wma) < 0.001, f"WMA mismatch: {wma} vs {expected_wma}"
    print(f"WMA test passed: {wma:.4f}")

    # 2. Test HMA (Hull Moving Average)
    print("Testing calculate_hma on synthetic trending data...")
    uptrend_closes = [100.0 + i * 1.5 for i in range(60)]
    hma_val, hma_prev, slope = feed.calculate_hma(uptrend_closes, period=20)
    assert hma_val > 0, "HMA should be > 0"
    assert slope == "UP", f"Expected slope UP on uptrend, got {slope}"
    print(f"HMA Uptrend test passed: HMA={hma_val}, Prev={hma_prev}, Slope={slope}")

    downtrend_closes = [200.0 - i * 1.5 for i in range(60)]
    hma_down, hma_down_prev, slope_down = feed.calculate_hma(downtrend_closes, period=20)
    assert slope_down == "DOWN", f"Expected slope DOWN on downtrend, got {slope_down}"
    print(f"HMA Downtrend test passed: HMA={hma_down}, Prev={hma_down_prev}, Slope={slope_down}")

    # 3. Test Market Session Info
    print("Testing get_market_session_info...")
    sinfo = feed.get_market_session_info()
    assert "utc_time" in sinfo, "sinfo must contain utc_time"
    assert "is_institutional_window" in sinfo, "sinfo must contain is_institutional_window"
    assert sinfo["liquidity_tier"] in ["INSTITUTIONAL", "HIGH", "LOW"]
    print(f"Session info test passed: {sinfo['session_name']} (Tier: {sinfo['liquidity_tier']})")

    # 4. Test ATR on mock candles
    print("Testing ATR on mock candles...")
    mock_candles = [
        {"time": 1, "open": 100, "high": 105, "low": 98, "close": 103, "volume": 10},
        {"time": 2, "open": 103, "high": 108, "low": 102, "close": 107, "volume": 12},
        {"time": 3, "open": 107, "high": 110, "low": 104, "close": 105, "volume": 15},
    ]
    atr = feed.calculate_atr(mock_candles, period=2)
    assert atr > 0, "ATR should be > 0"
    print(f"Mock ATR test passed: {atr}")

    # 5. Test Live BTCEUR Analysis
    print("Testing live analyze_symbol on BTCEUR...")
    analysis = feed.analyze_symbol("BTCEUR")
    assert "atr" in analysis, "Analysis must contain atr"
    assert "atr_pct" in analysis, "Analysis must contain atr_pct"
    assert "hma_50" in analysis, "Analysis must contain hma_50"
    assert "hma_50_slope" in analysis, "Analysis must contain hma_50_slope"
    assert "session_info" in analysis, "Analysis must contain session_info"
    assert analysis["price"] > 0, "Price must be > 0"
    print(f"Live BTCEUR analysis passed: Price={analysis['price']}, HMA50={analysis['hma_50']} ({analysis['hma_50_slope']}), ATR={analysis['atr']}")

    # 6. Test SmartDCAStrategy with HMA 50 and Session
    print("Testing SmartDCAStrategy with HMA 50 and ATR Trailing Stop...")
    strategy = SmartDCAStrategy(CONFIG)

    # Test Trailing Stop trigger:
    pos = {"amount": 0.001, "avg_entry_price": 100.0, "highest_price": 103.0, "total_cost_eur": 5.0}
    an_drop = {"symbol": "BTCEUR", "price": 101.0, "atr_pct": 1.0, "rsi": 50.0}
    act, amt, rsn = strategy.evaluate(an_drop, pos, 10.0)
    print(f"Trailing Stop evaluation: {act} | {rsn}")
    assert act == "SELL", "Trailing stop should trigger sell"
    assert "Trailing Stop ATR" in rsn

    # Test Break-Even trigger:
    pos_be = {"amount": 0.001, "avg_entry_price": 100.0, "highest_price": 102.9, "total_cost_eur": 5.0}
    an_be = {"symbol": "BTCEUR", "price": 100.20, "atr_pct": 1.0, "rsi": 50.0}
    act_be, amt_be, rsn_be = strategy.evaluate(an_be, pos_be, 10.0)
    print(f"Break-Even evaluation: {act_be} | {rsn_be}")
    assert act_be == "SELL", "Break-Even should trigger sell"
    assert "Break-Even" in rsn_be

    # Test Entry signal with HMA 50 filter:
    an_entry_ok = {
        "symbol": "BTCEUR",
        "price": 100.0,
        "rsi": 28.0,
        "rsi_prev": 27.0,
        "hma_50": 99.5,
        "hma_50_prev": 99.0,
        "hma_50_slope": "UP",
        "sma_50": 98.0,
        "bb_lower": 100.0,
        "session_info": {"is_institutional_window": True, "liquidity_tier": "INSTITUTIONAL"}
    }
    act_buy, amt_buy, rsn_buy = strategy.evaluate(an_entry_ok, None, 20.0)
    print(f"HMA Entry evaluation (favorable): {act_buy} | {rsn_buy}")
    assert act_buy == "BUY", "Should trigger BUY with oversold RSI and rising HMA 50"

    # Test Entry blocked when falling heavily below HMA with slope DOWN:
    an_entry_blocked = {
        "symbol": "BTCEUR",
        "price": 90.0,
        "rsi": 30.0,
        "rsi_prev": 31.0,
        "hma_50": 100.0,
        "hma_50_prev": 102.0,
        "hma_50_slope": "DOWN",
        "sma_50": 100.0,
        "bb_lower": 0.0,
        "candle_bullish": False,
        "session_info": {"is_institutional_window": False, "liquidity_tier": "LOW"}
    }
    act_hold, amt_hold, rsn_hold = strategy.evaluate(an_entry_blocked, None, 20.0)
    print(f"HMA Entry evaluation (blocked): {act_hold} | {rsn_hold}")
    assert act_hold == "HOLD", "Should block entry when price is falling under descending HMA 50"

    # 7. Test AutomatonBrain Position Management (Break-Even & ATR Trailing Stop parity)
    print("Testing AutomatonBrain evaluate_position_management...")
    brain = AutomatonBrain(Path(__file__).resolve().parent.parent / "data")
    act_ab_be, amt_ab_be, rsn_ab_be = brain.evaluate_position_management(
        "BTCEUR",
        {"price": 100.20, "rsi": 50.0, "atr_pct": 1.0},
        {"avg_entry_price": 100.0, "highest_price": 102.9, "dca_count": 1},
        10.0,
        CONFIG
    )
    assert act_ab_be == "SELL", "AutomatonBrain should trigger Break-Even"
    assert "Break-Even" in rsn_ab_be
    print(f"AutomatonBrain Break-Even passed: {rsn_ab_be}")

    # 8. Test Kronos Foundation Market Oracle
    print("Testing Kronos Foundation Market Oracle...")
    kronos_oracle = KronosOracle(pred_len=6, sample_count=50)
    mock_series = [
        {"time": i * 300, "open": 100.0 + i*0.2, "high": 101.0 + i*0.2, "low": 99.5 + i*0.2, "close": 100.5 + i*0.2, "volume": 1000 + i*10}
        for i in range(25)
    ]
    pred_res = kronos_oracle.predict(mock_series, current_price=105.0)
    assert "bullish_prob" in pred_res, "Kronos prediction must contain bullish_prob"
    assert "expected_return_pct" in pred_res, "Kronos prediction must contain expected_return_pct"
    assert "verdict" in pred_res, "Kronos prediction must contain verdict"
    assert pred_res["verdict"] in ["BULLISH_BIAS", "BEARISH_BIAS", "NEUTRAL"], f"Invalid verdict: {pred_res['verdict']}"
    print(f"Kronos standalone test passed: {pred_res['summary']}")

    # Test live Kronos integration in feed
    assert "kronos" in analysis, "Live analysis must contain kronos"
    live_kronos = analysis["kronos"]
    print(f"Live BTCEUR Kronos test passed: {live_kronos['summary']}")

    # Test Strategy blocking on Kronos Bearish Bias
    an_bearish_kronos = {
        "symbol": "BTCEUR",
        "price": 100.0,
        "rsi": 30.0,
        "rsi_prev": 29.0,
        "hma_50": 100.0,
        "hma_50_prev": 99.0,
        "hma_50_slope": "UP",
        "sma_50": 98.0,
        "bb_lower": 100.0,
        "session_info": {"is_institutional_window": True, "liquidity_tier": "INSTITUTIONAL"},
        "kronos": {"verdict": "BEARISH_BIAS", "bullish_prob": 20.0, "expected_return_pct": -1.5}
    }
    act_kb, amt_kb, rsn_kb = strategy.evaluate(an_bearish_kronos, None, 20.0)
    assert act_kb == "HOLD", "Should block entry when Kronos predicts severe bearish breakdown"
    assert "Oráculo Kronos bloquea" in rsn_kb
    print(f"Strategy Kronos protection passed: {act_kb} | {rsn_kb}")

    # 9. Test EconomicNewsFilter (Forex Factory)
    print("Testing EconomicNewsFilter (Forex Factory)...")
    from datetime import timedelta, datetime, timezone
    news_filter = EconomicNewsFilter()
    calendar_status = news_filter.get_news_status()
    assert "is_shield_active" in calendar_status, "Must contain is_shield_active"
    assert "summary" in calendar_status, "Must contain summary"
    print(f"Live Forex Factory calendar test passed: {calendar_status['summary']}")

    # Test shield activation when an event is in 5 minutes
    fake_now = datetime.now(timezone.utc)
    imminent_event_time = fake_now + timedelta(minutes=5)
    news_filter.cached_events = [{
        "title": "US CPI m/m (Simulado)",
        "country": "USD",
        "impact": "High",
        "datetime_utc": imminent_event_time
    }]
    shield_status = news_filter.get_news_status(now_override=fake_now)
    assert shield_status["is_shield_active"] is True, "Shield should be active for event in 5 minutes"
    assert shield_status["active_event"]["title"] == "US CPI m/m (Simulado)"
    print(f"News shield activation test passed: {shield_status['summary']}")

    # Test Strategy blocking on active News Shield
    an_news_shield = {
        "symbol": "BTCEUR",
        "price": 100.0,
        "rsi": 30.0,
        "rsi_prev": 29.0,
        "hma_50": 100.0,
        "hma_50_prev": 99.0,
        "hma_50_slope": "UP",
        "sma_50": 98.0,
        "bb_lower": 100.0,
        "session_info": {"is_institutional_window": True, "liquidity_tier": "INSTITUTIONAL"},
        "news_status": shield_status
    }
    act_ns, amt_ns, rsn_ns = strategy.evaluate(an_news_shield, None, 20.0)
    assert act_ns == "HOLD", "Should block entry when news shield is active"
    assert "Escudo Forex Factory activo" in rsn_ns
    print(f"Strategy News Shield test passed: {act_ns} | {rsn_ns}")

    # 8. Test TradingCouncil (Bull vs. Bear + Risk Manager Debate)
    council = TradingCouncil()
    favorable_dip = {
        "symbol": "BTCEUR",
        "price": 79000.0,
        "rsi": 28.0,
        "hma_50": 80000.0,
        "hma_slope": 12.0,
        "hma_50_prev": 79988.0,
        "macd": 10.0,
        "macd_signal": 5.0,
        "macd_hist": 5.0,
        "bb_lower": 79200.0,
        "bb_upper": 82000.0,
        "ema_200": 78000.0,
        "candle_bullish": True,
        "atr": 400.0,
        "atr_pct": 0.5,
        "session_info": {"is_peak_liquidity": True, "session": "NY_OVERLAP"},
        "kronos": {"available": True, "signal": "BULLISH", "expected_return_pct": 1.2, "confidence": 0.72},
        "news_shield": {"blocked": False, "reason": "Clear"},
    }
    res_buy = council.debate_entry("BTCEUR", favorable_dip, 50.0, CONFIG, tier="NORMAL", open_positions_count=0)
    assert res_buy["approved"] is True, f"Expected BUY approval on favorable dip, got: {res_buy}"
    assert res_buy["decision"] == "BUY"
    print(f"TradingCouncil BUY test passed: {res_buy['decision']} (net={res_buy['net_score']})")

    falling_knife = {
        "symbol": "ETHEUR",
        "price": 2000.0,
        "rsi": 48.0,
        "hma_50": 2100.0,
        "hma_slope": -25.0,
        "hma_50_prev": 2125.0,
        "macd": -15.0,
        "macd_signal": -5.0,
        "macd_hist": -10.0,
        "bb_lower": 1950.0,
        "bb_upper": 2150.0,
        "atr": 120.0,
        "atr_pct": 6.0,
        "session_info": {"is_peak_liquidity": False, "session": "ASIA"},
        "kronos": {"available": True, "signal": "BEARISH", "expected_return_pct": -1.5, "confidence": 0.8},
        "news_shield": {"blocked": False, "reason": "Clear"},
    }
    res_hold = council.debate_entry("ETHEUR", falling_knife, 50.0, CONFIG, tier="NORMAL", open_positions_count=2)
    assert res_hold["approved"] is False, f"Expected HOLD rejection on falling knife, got: {res_hold}"
    assert res_hold["decision"] == "HOLD"
    print(f"TradingCouncil HOLD test passed: {res_hold['decision']} (net={res_hold['net_score']})")

    veto_analysis = dict(favorable_dip)
    veto_analysis["news_status"] = {"is_shield_active": True, "active_event": {"title": "High-Impact USD CPI"}}
    res_veto = council.debate_entry("BTCEUR", veto_analysis, 50.0, CONFIG, tier="NORMAL", open_positions_count=0)
    assert res_veto["approved"] is False
    assert res_veto["decision"] == "VETO"
    print(f"TradingCouncil VETO test passed: {res_veto['decision']} ({res_veto['risk_verdict']})")

    brain.evaluate_new_entry({"BTCEUR": favorable_dip}, 50.0, CONFIG, open_positions_count=0)
    status_dict = brain.get_status_dict()
    assert "council_debate" in status_dict and status_dict["council_debate"].get("decision") == "BUY"
    assert "BTCEUR" in status_dict["council_debate"].get("summary", "")
    print(f"AutomatonBrain council_debate populated: {status_dict['council_debate'].get('decision')}")

    # 9. Test Multi-Strategy Trend Breakout (Donchian 20 + HMA UP + Volume Expansion)
    breakout_setup = {
        "symbol": "SOLEUR",
        "price": 152.0,
        "rsi": 62.0,
        "hma_50": 146.0,
        "hma_50_prev": 145.0,
        "hma_50_slope": "UP",
        "donchian_high_20": 150.0,
        "volume_ratio": 1.45,
        "bb_lower": 142.0,
        "bb_upper": 153.0,
        "atr": 2.0,
        "atr_pct": 1.3,
        "session_info": {"is_institutional_window": True, "liquidity_tier": "HIGH"},
        "kronos": {"available": True, "signal": "BULLISH"},
        "news_status": {"is_shield_active": False},
    }
    res_brk = council.debate_multi_strategy("SOLEUR", breakout_setup, 50.0, CONFIG, tier="NORMAL", open_positions_count=0)
    assert res_brk["approved"] is True, f"Expected TREND_BREAKOUT approval, got: {res_brk}"
    assert res_brk["strategy_tag"] == "TREND_BREAKOUT"
    print(f"Multi-Strategy Trend Breakout test passed: {res_brk['strategy_tag']} (net={res_brk['net_score']})")

    # 10. Test RobustnessBacktester (Walk-Forward + Monte Carlo) on synthetic & live BTCEUR
    import math
    synth_bars = []
    for idx in range(220):
        base = 100.0 + idx * 0.08 + math.sin(idx / 5.0) * 3.5
        synth_bars.append({
            "time": idx * 3600000,
            "open": base - 0.3,
            "high": base + 1.2,
            "low": base - 1.2,
            "close": base,
            "volume": 1000.0 + (400.0 if idx % 7 == 0 else 0.0),
        })
    tester = RobustnessBacktester(CONFIG)
    synth_report = tester.evaluate_robustness(symbol="SYNTHEUR", candles=synth_bars, strategy_mode="MULTI")
    assert "walk_forward" in synth_report and "monte_carlo" in synth_report
    assert synth_report["monte_carlo"]["iterations"] >= 0
    print(f"RobustnessBacktester synthetic test passed: verdict={synth_report['verdict']} score={synth_report['robustness_score']}")

    live_report = tester.evaluate_robustness(symbol="BTCEUR", interval="1h", limit=240, strategy_mode="MULTI")
    assert live_report["candles_analyzed"] >= 200
    print(f"RobustnessBacktester live BTCEUR 1H passed: verdict={live_report['verdict']} | trades={live_report['full_backtest']['trades_count']} | MC p95 DD={live_report['monte_carlo']['mc_p95_drawdown_pct']}%")

    # 11. Test SMC Signals (Liquidity Sweep + Fair Value Gap) & TradingCouncil integration
    smc_candles = [{"open": 102.0, "high": 103.0, "low": 100.0, "close": 101.0} for _ in range(25)]
    # Sweep below 100.0 (low=98.5), followed by strong displacement forming bullish FVG (candle[-3].high=100.5 < candle[-1].low=102.0)
    smc_candles.append({"open": 100.0, "high": 100.5, "low": 98.5, "close": 100.2})
    smc_candles.append({"open": 100.3, "high": 102.5, "low": 100.2, "close": 102.2})
    smc_candles.append({"open": 102.2, "high": 103.5, "low": 102.0, "close": 103.0})
    smc_res = MarketDataFeed.calculate_smc_signals(smc_candles)
    assert smc_res["bullish_sweep"] is True and smc_res["bullish_fvg"] is True, f"Expected sweep+FVG, got: {smc_res}"

    smc_bear_candles = [{"open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0} for _ in range(10)]
    smc_bear_candles.append({"open": 101.5, "high": 102.0, "low": 101.0, "close": 101.1})
    smc_bear_candles.append({"open": 101.0, "high": 101.1, "low": 99.0, "close": 99.2})
    smc_bear_candles.append({"open": 99.2, "high": 99.8, "low": 98.8, "close": 99.5})
    smc_bear_res = MarketDataFeed.calculate_smc_signals(smc_bear_candles)
    assert smc_bear_res["bearish_fvg_overhead"] is True, f"Expected bearish FVG overhead, got: {smc_bear_res}"

    smc_boost_analysis = dict(favorable_dip)
    smc_boost_analysis["smc"] = {"bullish_sweep": True, "bullish_fvg": True, "bearish_fvg_overhead": False}
    res_smc = council.debate_entry("BTCEUR", smc_boost_analysis, 50.0, CONFIG)
    assert res_smc["bull_score"] >= res_buy["bull_score"] + 20.0
    print(f"SMC Liquidity Sweep + FVG test passed: Bull={res_smc['bull_score']} (+20 SMC boost)")

    # 12. Test Market Regime Detector (TRENDING vs RANGING vs HIGH_VOLATILITY_SHOCK)
    trend_candles = [{"open": 100.0 + i * 1.5, "high": 101.0 + i * 1.5, "low": 99.5 + i * 1.5, "close": 100.8 + i * 1.5} for i in range(60)]
    reg_trend = MarketDataFeed.calculate_regime(trend_candles)
    assert reg_trend["regime"] == "TRENDING" and reg_trend["adx"] >= 25.0, f"Expected TRENDING, got: {reg_trend}"

    shock_candles = [{"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0} for _ in range(55)]
    shock_candles.append({"open": 100.0, "high": 118.0, "low": 82.0, "close": 115.0})
    reg_shock = MarketDataFeed.calculate_regime(shock_candles)
    assert reg_shock["regime"] == "HIGH_VOLATILITY_SHOCK", f"Expected HIGH_VOLATILITY_SHOCK, got: {reg_shock}"

    shock_analysis = dict(favorable_dip)
    shock_analysis["regime"] = reg_shock
    res_shock_veto = council.debate_multi_strategy("BTCEUR", shock_analysis, 50.0, CONFIG)
    assert res_shock_veto["decision"] == "VETO" and res_shock_veto["strategy_tag"] == "SHOCK_GUARD"
    print(f"Regime Detector test passed: Trend ADX={reg_trend['adx']} | Shock VETO Z={reg_shock['vol_zscore']}")

    # 13. Test BinanceSpotClient BookTicker & Maker-First guard
    b_client = BinanceSpotClient()
    bid, ask = b_client.get_book_ticker("BTCEUR")
    assert bid > 0 and ask >= bid, f"Expected valid BTCEUR book ticker, got bid={bid}, ask={ask}"
    print(f"Binance BookTicker Maker-First test passed: BTCEUR Bid={bid} | Ask={ask}")

    print(">>> 100% OF QUANTITATIVE UNIT TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_all()
