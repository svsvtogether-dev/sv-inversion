import os
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.market_data import MarketDataFeed
from src.automaton_brain import AutomatonBrain
from src.trading_council import TradingCouncil
from src.signals import evaluate_breakout_entry_signal, evaluate_breakout_exit_signal
from src.robustness_backtester import RobustnessBacktester
from src.binance_client import BinanceSpotClient
from src.shadow_tracker import ShadowTracker
from src.news_filter import EconomicNewsFilter
from src.portfolio import Portfolio
from src.config import CONFIG
import server


def test_all():
    feed = MarketDataFeed()

    # 1. Test WMA & HMA
    wma = feed.calculate_wma([10.0, 20.0, 30.0], period=3)
    assert abs(wma - 23.333333) < 0.001
    uptrend_closes = [100.0 + i * 1.5 for i in range(60)]
    hma_val, _, slope = feed.calculate_hma(uptrend_closes, period=20)
    assert hma_val > 0 and slope == "UP"
    print("1. WMA & HMA tests passed")

    # 2. Test Live BTCEUR 4h analysis
    live_btc = feed.analyze_symbol("BTCEUR", interval="4h", limit=250)
    assert live_btc["price"] > 0 and live_btc["ema_200"] > 0 and live_btc["donchian_high_20"] > 0
    print(f"2. Live BTCEUR 4h analysis passed: Price={live_btc['price']} | EMA200={live_btc['ema_200']}")

    # 3. PASO 1 - Single Source of Truth (signals.py == TradingCouncil == AutomatonBrain)
    breakout_btc = {
        "symbol": "BTCEUR",
        "price": 65000.0,
        "rsi": 62.0,
        "ema_trend": 63500.0,
        "ema_200": 60000.0,
        "hma_50": 63800.0,
        "hma_50_prev": 63400.0,
        "hma_50_slope": "UP",
        "donchian_high_20": 64500.0,
        "volume_ratio": 1.35,
        "atr": 900.0,
        "atr_pct": 1.4,
        "regime": {"regime": "TRENDING", "adx": 30.0, "vol_zscore": 0.5},
        "news_status": {"is_shield_active": False},
    }
    council = TradingCouncil()
    sig_direct = evaluate_breakout_entry_signal("BTCEUR", breakout_btc, open_positions_count=0)
    sig_council = council.debate_multi_strategy("BTCEUR", breakout_btc, 50.0, CONFIG, open_positions_count=0)
    assert sig_direct["approved"] is True and sig_council["approved"] is True
    assert sig_direct["decision"] == sig_council["decision"] == "BUY"
    assert sig_direct["strategy_tag"] == sig_council["strategy_tag"] == "TREND_BREAKOUT"

    # Exit parity: Trailing 2.0x ATR
    with tempfile.TemporaryDirectory() as tmp_b:
        brain = AutomatonBrain(Path(tmp_b))
        brain.tier = "CRITICAL"  # PASO 2: Fixed params, must NOT change SL/trailing!
        pos = {"avg_entry_price": 60000.0, "highest_price": 64000.0, "strategy_tag": "TREND_BREAKOUT"}
        exit_analysis = {"price": 62000.0, "rsi": 55.0, "atr_pct": 1.5, "ema_trend": 61000.0}
        should_sell, reason_sig, _, _ = evaluate_breakout_exit_signal(
            price=62000.0, entry_price=60000.0, highest_price=64000.0, atr_pct=1.5, ema_50=61000.0
        )
        act_brain, _, reason_brain = brain.evaluate_position_management("BTCEUR", exit_analysis, pos, 0.0, CONFIG)
        assert should_sell is True and act_brain == "SELL"
        assert reason_sig in reason_brain
    # Fixed SL (-4.5%) even in CRITICAL tier
    sl_sell, _, _, _ = evaluate_breakout_exit_signal(
        price=57200.0, entry_price=60000.0, highest_price=60000.0, atr_pct=1.5, ema_50=61000.0, sl_pct=-4.5
    )
    assert sl_sell is True
    print("3. PASO 1 & PASO 2 (Single Source of Truth + Fixed Params) passed")

    # 4. PASO 3 - Anti Look-Ahead Test (Donchian excludes current bar & future bars)
    base_candles = [
        {"open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 10.0}
        for _ in range(30)
    ]
    bt = RobustnessBacktester(CONFIG)
    snap_a = bt._build_bar_analysis("BTCEUR", base_candles)
    mutated_current = [dict(c) for c in base_candles]
    mutated_current[-1]["high"] = 999.0  # Current candle spike must NOT inflate donchian_high_20
    snap_b = bt._build_bar_analysis("BTCEUR", mutated_current)
    assert snap_a["donchian_high_20"] == snap_b["donchian_high_20"] == 102.0
    print("4. PASO 3 (Anti Look-Ahead Donchian shift 1) passed")

    # 5. PASO 4 - Drawdown Kill-Switch (-15%) in AutomatonBrain & Backtester
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_brain = AutomatonBrain(Path(tmpdir))
        tmp_brain.update_equity_drawdown(60.0)
        assert tmp_brain.update_equity_drawdown(50.5) is True
        _, _, amt_dd, reason_dd = tmp_brain.evaluate_new_entry({"BTCEUR": breakout_btc}, 50.0, CONFIG)
        assert amt_dd == 0.0 and "Drawdown Kill-Switch" in reason_dd
        tmp_brain.reset_session(50.0)
        assert tmp_brain.drawdown_kill_switch is False

        # Test Backtester also respects -15% drawdown kill-switch
        crash_candles = []
        for idx in range(250):
            p = 100.0 + (idx * 0.4 if idx < 215 else -4.0 * (idx - 214))
            p = max(20.0, p)
            crash_candles.append({"open": p, "high": p + 1.0, "low": max(1.0, p - 1.0), "close": p, "volume": 100.0})
        res_bt = bt.simulate_strategy(crash_candles, symbol="BTCEUR", initial_capital=50.0)
        assert "max_drawdown_pct" in res_bt and "trades_count" in res_bt
    print("5. PASO 4 (Drawdown Kill-Switch -15% in Brain & Backtester) passed")

    # 6. PASO 5 - Execution Robustness (Idempotent ClientOrderId on Network Cut + Startup Reconciliation)
    b_client = BinanceSpotClient()
    calls = {"post": 0, "get_order": 0}

    def fake_request(method, path, params=None, signed=False, timeout=5.0):
        if method == "POST" and path == "/api/v3/order":
            calls["post"] += 1
            return False, {}, "Read timed out"  # Simulated network cut
        if method == "GET" and path == "/api/v3/order" and "origClientOrderId" in (params or {}):
            calls["get_order"] += 1
            return True, {"orderId": 987654, "clientOrderId": params["origClientOrderId"], "status": "FILLED"}, "OK"
        if method == "GET" and path == "/api/v3/account":
            return True, {"balances": [{"asset": "EUR", "free": "50.0"}, {"asset": "BTC", "free": "0.0"}]}, "OK"
        if method == "GET" and path == "/api/v3/openOrders":
            return True, [], "OK"
        return False, {}, "Unexpected"

    b_client.api_key = "test_api_key_123456789012345"
    b_client.api_secret = "test_api_secret_123456789012345"
    b_client._request = fake_request
    ok_ord, ord_data, ord_msg = b_client.place_market_order("BTCEUR", "BUY", 0.001, client_order_id="sv_test_unique_1")
    assert ok_ord is True and ord_data["orderId"] == 987654 and calls["post"] == 1 and calls["get_order"] == 1
    assert "sin duplicado" in ord_msg
    rec = b_client.reconcile_startup("BTCEUR")
    assert rec["ok"] is True and rec["eur_free"] == 50.0 and rec["open_orders_count"] == 0, f"Unexpected rec: {rec}"
    print("6. PASO 5 (Network-cut Idempotency & Startup Reconciliation) passed")

    # 7. PASO 6 - CSV Trade History + Authenticated /export_csv
    with tempfile.TemporaryDirectory() as tmp_csv_dir:
        tmp_port = Portfolio(storage_path=Path(tmp_csv_dir) / "p.json", environment="simulation", initial_capital=50.0)
        tmp_port.buy("BTCEUR", 50.0, 60000.0, "Test Breakout", strategy_tag="TREND_BREAKOUT")
        csv_text = tmp_port.export_trades_csv_text()
        assert "slippage_eur" in csv_text and "BTCEUR" in csv_text

    os.environ["EXPORT_API_KEY"] = "super_secret_export_key"
    client = TestClient(server.data_api_app)
    r_unauth = client.get("/export_csv")
    assert r_unauth.status_code == 401
    r_bad = client.get("/export_csv", headers={"X-API-Key": "wrong"})
    assert r_bad.status_code == 401
    r_ok = client.get("/export_csv", headers={"X-API-Key": "super_secret_export_key"})
    assert r_ok.status_code == 200 and "slippage_eur" in r_ok.text
    print("7. PASO 6 (CSV History & Authenticated Export Endpoint) passed")

    # 8. News Shield & ShadowTracker
    nf = EconomicNewsFilter()
    assert "is_shield_active" in nf.get_news_status()
    with tempfile.TemporaryDirectory() as tmp_st:
        st = ShadowTracker(Path(tmp_st))
        assert st.record_veto("BTCEUR", 100.0, {"approved": False, "decision": "VETO"}, tp_pct=25.0, sl_pct=-4.5) is True
    print("8. News Shield & ShadowTracker tests passed")

    server.bot.stop()
    print(">>> 100% OF QUANTITATIVE UNIT TESTS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    test_all()
