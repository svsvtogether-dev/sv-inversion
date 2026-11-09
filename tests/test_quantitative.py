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
from src.config import CONFIG

def test_all():
    feed = MarketDataFeed()
    print("Testing ATR on mock candles...")
    mock_candles = [
        {"time": 1, "open": 100, "high": 105, "low": 98, "close": 103, "volume": 10},
        {"time": 2, "open": 103, "high": 108, "low": 102, "close": 107, "volume": 12},
        {"time": 3, "open": 107, "high": 110, "low": 104, "close": 105, "volume": 15},
    ]
    atr = feed.calculate_atr(mock_candles, period=2)
    assert atr > 0, "ATR should be > 0"
    print(f"Mock ATR test passed: {atr}")

    print("Testing live analyze_symbol on BTCEUR...")
    analysis = feed.analyze_symbol("BTCEUR")
    assert "atr" in analysis, "Analysis must contain atr"
    assert "atr_pct" in analysis, "Analysis must contain atr_pct"
    assert analysis["price"] > 0, "Price must be > 0"
    p = analysis["price"]
    a = analysis["atr"]
    ap = analysis["atr_pct"]
    print(f"Live BTCEUR analysis passed: Price={p}, ATR={a}, ATR_pct={ap}%")

    print("Testing SmartDCAStrategy with ATR Trailing Stop...")
    strategy = SmartDCAStrategy(CONFIG)

    # Test Trailing Stop trigger: entry 100, peak 103 (+3%), now 101 (+1%) with atr_pct 1.0% -> floor is 3.0 - 1.0 = 2.0% -> 1.0% <= 2.0% triggers
    pos = {"amount": 0.001, "avg_entry_price": 100.0, "highest_price": 103.0, "total_cost_eur": 5.0}
    an_drop = {"symbol": "BTCEUR", "price": 101.0, "atr_pct": 1.0, "rsi": 50.0}
    act, amt, rsn = strategy.evaluate(an_drop, pos, 10.0)
    print(f"Trailing Stop evaluation: {act} | {rsn}")
    assert act == "SELL", "Trailing stop should trigger sell"
    assert "Trailing Stop ATR" in rsn

    # Test Break-Even trigger: entry 100, peak 101.8 (+1.8%), now 100.20 (+0.20%) <= 0.25% triggers
    pos_be = {"amount": 0.001, "avg_entry_price": 100.0, "highest_price": 101.8, "total_cost_eur": 5.0}
    an_be = {"symbol": "BTCEUR", "price": 100.20, "atr_pct": 1.0, "rsi": 50.0}
    act_be, amt_be, rsn_be = strategy.evaluate(an_be, pos_be, 10.0)
    print(f"Break-Even evaluation: {act_be} | {rsn_be}")
    assert act_be == "SELL", "Break-Even should trigger sell"
    assert "Break-Even" in rsn_be

    print(">>> 100% OF QUANTITATIVE UNIT TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_all()
