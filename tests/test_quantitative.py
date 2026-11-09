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
    pos_be = {"amount": 0.001, "avg_entry_price": 100.0, "highest_price": 101.8, "total_cost_eur": 5.0}
    an_be = {"symbol": "BTCEUR", "price": 100.20, "atr_pct": 1.0, "rsi": 50.0}
    act_be, amt_be, rsn_be = strategy.evaluate(an_be, pos_be, 10.0)
    print(f"Break-Even evaluation: {act_be} | {rsn_be}")
    assert act_be == "SELL", "Break-Even should trigger sell"
    assert "Break-Even" in rsn_be

    # Test Entry signal with HMA 50 filter:
    an_entry_ok = {
        "symbol": "BTCEUR",
        "price": 100.0,
        "rsi": 30.0,
        "rsi_prev": 29.0,
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
        {"avg_entry_price": 100.0, "highest_price": 101.8, "dca_count": 1},
        10.0,
        CONFIG
    )
    assert act_ab_be == "SELL", "AutomatonBrain should trigger Break-Even"
    assert "Break-Even" in rsn_ab_be
    print(f"AutomatonBrain Break-Even passed: {rsn_ab_be}")

    print(">>> 100% OF QUANTITATIVE UNIT TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_all()
