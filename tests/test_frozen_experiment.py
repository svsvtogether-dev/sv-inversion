import csv
import os
import sys
import tempfile
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from src.config import FROZEN_EXPERIMENT, FROZEN_CONFIG_HASH, verify_frozen_config
from src.bot import TradingBot
from src.signals import evaluate_daily_sma200_signal
from src.experiment_tracker import ExperimentTracker, run_daily_sma200_replica


def test_paso1_frozen_config_and_hash():
    h = verify_frozen_config()
    assert h == FROZEN_CONFIG_HASH
    assert FROZEN_EXPERIMENT["version"] == "v1.0-frozen"
    assert FROZEN_EXPERIMENT["start_date"] == "2026-11-14"
    assert FROZEN_EXPERIMENT["review_date"] == "2027-05-14"

    tampered = dict(FROZEN_EXPERIMENT)
    tampered["sma_period"] = 150
    try:
        verify_frozen_config(tampered, FROZEN_CONFIG_HASH)
        assert False, "Debió fallar al alterar la regla congelada"
    except RuntimeError as e:
        assert "hash alterado" in str(e)
    print(f"1. PASO 1 (Congelado v1.0-frozen hash={h[:12]}...) passed")


def test_paso2_live_blocked():
    bot = TradingBot()
    bot.set_environment("live")
    bot.set_live_armed(True)
    assert bot.active_environment == "simulation"
    assert bot.live_trading_armed is False
    print("2. PASO 2 (Dinero real bloqueado live_armed=False) passed")


def test_paso3_replica_2023_12_to_2026_11():
    c1d = []
    cur = int(datetime(2023, 4, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime(2026, 11, 15, tzinfo=timezone.utc).timestamp() * 1000)
    while cur < end:
        r = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCEUR", "interval": "1d", "startTime": cur, "limit": 1000},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        for x in data:
            ts = int(x[0])
            if ts <= end:
                c1d.append({"timestamp": ts, "open": float(x[1]), "close": float(x[4])})
        if len(data) < 1000:
            break
        cur = int(data[-1][0]) + 1

    ts_start = int(datetime(2023, 12, 1, tzinfo=timezone.utc).timestamp() * 1000)
    ts_end = int(datetime(2026, 11, 14, 23, 59, tzinfo=timezone.utc).timestamp() * 1000)
    start_idx = next(i for i, x in enumerate(c1d) if x["timestamp"] >= ts_start)
    end_idx = max(i for i, x in enumerate(c1d) if x["timestamp"] <= ts_end) + 1

    res = run_daily_sma200_replica(c1d, start_idx, end_idx, initial_eur=50.0, monthly_deposit_eur=0.0, cost_rate=0.0015)
    assert res["trades"] == 13, f"Esperado 13 ops, obtenido {res['trades']}"
    assert abs(res["ret_pct"] - 57.16) < 0.10, f"Esperado +57.16%, obtenido {res['ret_pct']:.2f}%"
    print(f"3. PASO 3 (Réplica live signals.py == offline: {res['trades']} ops, {res['ret_pct']:+.2f}%) passed")


def test_paso4_5_7_daily_csv_weekly_and_final_report():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = ExperimentTracker(data_dir=Path(tmp), initial_eur=50.0, cost_rate=0.0015)
        # Simular 8 días + fecha de revisión 2027-05-14
        bars = [
            ("2026-11-14", 60000.0, 61000.0, 60000.0),  # BUY al cierre -> exec en open 2026-11-15
            ("2026-11-15", 61000.0, 62000.0, 60050.0),
            ("2026-11-16", 62000.0, 63000.0, 60100.0),
            ("2026-11-17", 63000.0, 59000.0, 60150.0),  # SELL al cierre -> exec en open 2026-11-18
            ("2026-11-18", 59000.0, 58500.0, 60100.0),
            ("2026-11-19", 58500.0, 58000.0, 60050.0),
            ("2026-11-20", 58000.0, 59500.0, 60000.0),  # 7o día -> genera weekly_summary.md
            ("2027-05-14", 59500.0, 60500.0, 60000.0),  # Fecha de revisión -> genera final_report
        ]
        for d, o, c, s in bars:
            tracker.process_daily_bar(d, o, c, s)

        # Intentar duplicar fecha
        dup = tracker.process_daily_bar("2026-11-14", 60000.0, 61000.0, 60000.0)
        assert dup is None

        with open(tracker.csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 8
        assert list(rows[0].keys()) == tracker.CSV_FIELDS
        assert rows[0]["senal"] == "BUY"
        assert rows[1]["posicion"] == "BTC"
        assert rows[3]["senal"] == "SELL"
        assert rows[4]["posicion"] == "EUR"

        assert tracker.weekly_path.exists()
        assert tracker.final_report_path.exists()
        report_txt = tracker.final_report_path.read_text(encoding="utf-8")
        assert "C1 (Funcionamiento)" in report_txt
        assert "C2 (Riesgo)" in report_txt
        assert "C3 (Informativo)" in report_txt
        assert "CUMPLE" in report_txt
    print("4. PASO 4, 5 & 7 (CSV diario, no duplicados, resumen semanal e informe 2027-05-14) passed")


def test_paso6_header_only_auth_and_live_403():
    os.environ["ADMIN_API_KEY"] = "frozen_admin_key_2026"
    import server

    client = TestClient(server.data_api_app)
    for ep in ["/toggle", "/reset", "/emergency_sell", "/live_armed", "/environment", "/export_csv"]:
        r = client.post(ep) if ep != "/export_csv" else client.get(ep)
        assert r.status_code == 401, f"{ep} sin cabecera devolvió {r.status_code}"

    # ?token= en URL debe ser rechazado (401)
    r_url = client.get("/export_csv?token=frozen_admin_key_2026")
    assert r_url.status_code == 401, f"?token= debió devolver 401 y devolvió {r_url.status_code}"

    # Cabecera X-API-Key válida -> 200 en export_csv, 403 si intenta activar live
    r_ok = client.get("/export_csv", headers={"X-API-Key": "frozen_admin_key_2026"})
    assert r_ok.status_code == 200

    r_live = client.post("/live_armed?armed=true", headers={"X-API-Key": "frozen_admin_key_2026"})
    assert r_live.status_code == 403
    r_env = client.post("/environment?env=live", headers={"X-API-Key": "frozen_admin_key_2026"})
    assert r_env.status_code == 403

    server.bot.stop()
    print("5. PASO 6 (401 sin clave, 401 con ?token=, 200 con X-API-Key, 403 live) passed")


if __name__ == "__main__":
    test_paso1_frozen_config_and_hash()
    test_paso2_live_blocked()
    test_paso3_replica_2023_12_to_2026_11()
    test_paso4_5_7_daily_csv_weekly_and_final_report()
    test_paso6_header_only_auth_and_live_403()
    print(">>> 100% OF FROZEN EXPERIMENT v1.0-frozen TESTS PASSED! <<<")
