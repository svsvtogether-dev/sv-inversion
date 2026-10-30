import os
import time
import hmac
import hashlib
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class BinanceSpotClient:
    """
    Cliente seguro para la API oficial de Binance Spot (HMAC-SHA256).
    Gestiona saldos reales, verificación de permisos y ejecución de órdenes en vivo.
    """
    BASE_URLS = [
        "https://api.binance.com",
        "https://api1.binance.com",
        "https://api3.binance.com",
    ]

    def __init__(self):
        self._load_env()
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_API_SECRET", "")
        self.last_account_cache: Dict = {}
        self.last_cache_time = 0.0

    def _load_env(self):
        """Carga claves desde .env si están disponibles localmente."""
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        if k.strip() not in os.environ:
                            os.environ[k.strip()] = v.strip()
            except Exception:
                pass

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret and len(self.api_key) > 20)

    def _sign_request(self, params: Dict) -> Tuple[str, str]:
        params["timestamp"] = int(time.time() * 1000)
        query = urllib.parse.urlencode(params)
        sig = hmac.new(self.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        return query, sig

    def get_account_summary(self, force_refresh: bool = False) -> Dict:
        """
        Obtiene el estado real de la cuenta de Binance:
        - canTrade: permisos de trading
        - balances: saldos en EUR y criptoactivos
        - saldo disponible en EUR y valor estimado
        """
        now = time.time()
        if not force_refresh and (now - self.last_cache_time < 5.0) and self.last_account_cache:
            return self.last_account_cache

        if not self.is_configured():
            return {
                "connected": False,
                "can_trade": False,
                "status": "No configurado (falta BINANCE_API_KEY)",
                "eur_cash": 0.0,
                "balances": [],
                "total_estimated_eur": 0.0
            }

        params = {"recvWindow": 60000}
        query, signature = self._sign_request(params)

        for base in self.BASE_URLS:
            try:
                url = f"{base}/api/v3/account?{query}&signature={signature}"
                req = urllib.request.Request(url, headers={"X-MBX-APIKEY": self.api_key})
                with urllib.request.urlopen(req, timeout=6.0) as res:
                    data = json.loads(res.read().decode("utf-8"))
                    can_trade = bool(data.get("canTrade", False))
                    raw_balances = data.get("balances", [])

                    eur_cash = 0.0
                    bnb_cash = 0.0
                    active_balances = []
                    for b in raw_balances:
                        free = float(b.get("free", 0.0))
                        locked = float(b.get("locked", 0.0))
                        total = free + locked
                        asset = b.get("asset", "")

                        if asset == "EUR":
                            eur_cash = free
                        elif asset == "BNB":
                            bnb_cash = free

                        if total > 0.00000001:
                            active_balances.append({
                                "asset": asset,
                                "free": free,
                                "locked": locked,
                                "total": total
                            })

                    # Control de comisiones con BNB (-25% descuento oficial Binance Spot: 0.075% vs 0.10%)
                    has_bnb_fee_discount = bnb_cash >= 0.005
                    fee_rate = 0.00075 if has_bnb_fee_discount else 0.0010

                    result = {
                        "connected": True,
                        "can_trade": can_trade,
                        "status": "Conectado y listo" if can_trade else "Conectado (Lectura)",
                        "eur_cash": round(eur_cash, 2),
                        "bnb_cash": round(bnb_cash, 4),
                        "has_bnb_fee_discount": has_bnb_fee_discount,
                        "effective_fee_rate": fee_rate,
                        "fee_discount_desc": "Descuento BNB activo: 0.075%" if has_bnb_fee_discount else "Sin BNB: tarifa base 0.10%",
                        "balances": active_balances,
                        "total_estimated_eur": round(eur_cash, 2),
                        "maker_commission": data.get("makerCommission", 10),
                        "taker_commission": data.get("takerCommission", 10)
                    }
                    self.last_account_cache = result
                    self.last_cache_time = now
                    return result
            except Exception as e:
                err_str = str(e)
                continue

        return {
            "connected": False,
            "can_trade": False,
            "status": "Error de conexión temporal con Binance",
            "eur_cash": 0.0,
            "balances": [],
            "total_estimated_eur": 0.0
        }

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Tuple[bool, Dict, str]:
        """
        Envía una orden Market a Binance Spot con control de seguridad.
        """
        if not self.is_configured():
            return False, {}, "API Keys de Binance no configuradas"

        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": quantity,
            "recvWindow": 60000
        }
        query, signature = self._sign_request(params)

        for base in self.BASE_URLS:
            try:
                url = f"{base}/api/v3/order"
                body = f"{query}&signature={signature}".encode("utf-8")
                req = urllib.request.Request(url, data=body, headers={"X-MBX-APIKEY": self.api_key}, method="POST")
                with urllib.request.urlopen(req, timeout=8.0) as res:
                    data = json.loads(res.read().decode("utf-8"))
                    return True, data, "Orden ejecutada con éxito"
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8")
                return False, {}, f"Error Binance HTTP {e.code}: {err_body}"
            except Exception as e:
                continue

        return False, {}, "No se pudo conectar a los servidores de Binance"
