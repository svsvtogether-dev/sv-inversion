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

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = False, timeout: float = 8.0) -> Tuple[bool, Dict, str]:
        """Helper unificado para peticiones HTTP firmadas o públicas contra Binance Spot."""
        req_params = dict(params or {})
        headers = {}
        if signed:
            if not self.is_configured():
                return False, {}, "API Keys de Binance no configuradas"
            req_params.setdefault("recvWindow", 60000)
            query, signature = self._sign_request(req_params)
            full_qs = f"{query}&signature={signature}"
            headers["X-MBX-APIKEY"] = self.api_key
        else:
            full_qs = urllib.parse.urlencode(req_params)

        for base in self.BASE_URLS:
            try:
                url = f"{base}{endpoint}"
                body = None
                if method.upper() in ("POST", "PUT", "DELETE"):
                    body = full_qs.encode("utf-8") if full_qs else None
                elif full_qs:
                    url = f"{url}?{full_qs}"

                req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
                with urllib.request.urlopen(req, timeout=timeout) as res:
                    data = json.loads(res.read().decode("utf-8"))
                    return True, data, "OK"
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                return False, {}, f"Error Binance HTTP {e.code}: {err_body}"
            except Exception:
                continue

        return False, {}, "No se pudo conectar a los servidores de Binance"

    def get_book_ticker(self, symbol: str) -> Tuple[float, float]:
        """Obtiene el mejor Bid y Ask actuales del libro de órdenes."""
        ok, data, _ = self._request("GET", "/api/v3/ticker/bookTicker", {"symbol": symbol}, signed=False, timeout=4.0)
        if ok:
            return float(data.get("bidPrice", 0.0)), float(data.get("askPrice", 0.0))
        return 0.0, 0.0

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Tuple[bool, Dict, str]:
        """Envía una orden Market a Binance Spot con control de seguridad."""
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": quantity,
        }
        ok, data, msg = self._request("POST", "/api/v3/order", params, signed=True, timeout=8.0)
        return ok, data, ("Orden ejecutada con éxito" if ok else msg)

    def place_smart_order(self, symbol: str, side: str, quantity: float, wait_seconds: float = 3.2) -> Tuple[bool, Dict, str]:
        """
        Ejecución Maker-First (LIMIT_MAKER) en el mejor Bid/Ask para ahorrar comisión Taker y spread.
        Si no se llena en wait_seconds o el libro cruza, cancela el remanente y cae a MARKET.
        """
        if not self.is_configured():
            return False, {}, "API Keys de Binance no configuradas"

        bid, ask = self.get_book_ticker(symbol)
        if bid <= 0 or ask <= 0:
            return self.place_market_order(symbol, side, quantity)

        side_u = side.upper()
        maker_price = bid if side_u == "BUY" else ask
        # Ajuste limpio de decimales según magnitud del precio
        decimals = 2 if maker_price >= 100 else (4 if maker_price >= 1 else 6)
        price_str = f"{maker_price:.{decimals}f}"

        ok, order_data, _ = self._request(
            "POST",
            "/api/v3/order",
            {
                "symbol": symbol,
                "side": side_u,
                "type": "LIMIT_MAKER",
                "quantity": quantity,
                "price": price_str,
            },
            signed=True,
            timeout=6.0,
        )
        if not ok or "orderId" not in order_data:
            return self.place_market_order(symbol, side_u, quantity)

        order_id = order_data["orderId"]
        deadline = time.time() + max(0.5, wait_seconds)
        while time.time() < deadline:
            time.sleep(0.8)
            q_ok, q_data, _ = self._request(
                "GET",
                "/api/v3/order",
                {"symbol": symbol, "orderId": order_id},
                signed=True,
                timeout=4.0,
            )
            if q_ok and q_data.get("status") == "FILLED":
                return True, q_data, "Orden Maker (LIMIT_MAKER) ejecutada con ahorro de comisión"

        # Cancelar si sigue abierta y comprobar si hubo ejecución parcial
        c_ok, c_data, _ = self._request(
            "DELETE",
            "/api/v3/order",
            {"symbol": symbol, "orderId": order_id},
            signed=True,
            timeout=4.0,
        )
        executed_qty = float(c_data.get("executedQty", 0.0)) if c_ok else 0.0
        remaining_qty = max(0.0, float(quantity) - executed_qty)
        if remaining_qty <= 0 or (remaining_qty / max(float(quantity), 1e-9)) < 0.05:
            return True, c_data, "Orden Maker completada"

        return self.place_market_order(symbol, side_u, round(remaining_qty, 8))
