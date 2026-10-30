import os
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.bot import TradingBot
from src.config import CONFIG

app = FastAPI(title="SV Inversión AI - Bot de Trading Universal")
data_api_app = FastAPI(title="SV Inversión AI - Data API")

# Instancia global del bot
bot = TradingBot()
bot.start()

# Directorio estático
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

# Definición de endpoints en data_api_app (para paths relativos a /data_api o /static/api)
@data_api_app.api_route("/status", methods=["GET", "POST"])
def data_status():
    return bot.get_state()

@data_api_app.api_route("/toggle", methods=["GET", "POST"])
def data_toggle():
    bot.is_running = not bot.is_running
    state_str = "activo" if bot.is_running else "en pausa"
    bot.log(f"Bot marcado como {state_str} por el usuario.")
    return {"is_running": bot.is_running}

@data_api_app.api_route("/environment", methods=["GET", "POST"])
async def data_environment(request: Request, env: Optional[str] = None):
    chosen_env = env
    if request.method == "POST":
        try:
            body = await request.json()
            if body and "environment" in body:
                chosen_env = body["environment"]
        except Exception:
            pass
    if chosen_env in ["simulation", "live"]:
        bot.set_environment(chosen_env)
    return {"active_environment": bot.active_environment}

@data_api_app.api_route("/live_armed", methods=["GET", "POST"])
async def data_live_armed(request: Request, armed: Optional[bool] = None):
    chosen_armed = armed
    if request.method == "POST":
        try:
            body = await request.json()
            if body and "armed" in body:
                chosen_armed = bool(body["armed"])
        except Exception:
            pass
    if chosen_armed is not None:
        bot.set_live_armed(chosen_armed)
    return {"live_trading_armed": bot.live_trading_armed}

@data_api_app.api_route("/symbol", methods=["GET", "POST"])
async def data_symbol(request: Request, symbol: Optional[str] = None):
    chosen_symbol = symbol
    if request.method == "POST":
        try:
            body = await request.json()
            if body and "symbol" in body:
                chosen_symbol = body["symbol"]
        except Exception:
            pass
    if chosen_symbol:
        bot.set_symbol(chosen_symbol)
    return {"symbol": bot.current_symbol}

@data_api_app.api_route("/category", methods=["GET", "POST"])
async def data_category(request: Request, category: Optional[str] = None):
    chosen_cat = category
    if request.method == "POST":
        try:
            body = await request.json()
            if body and "category" in body:
                chosen_cat = body["category"]
        except Exception:
            pass
    if chosen_cat:
        bot.set_category(chosen_cat)
    return {"category": bot.active_category, "symbol": bot.current_symbol}

@data_api_app.api_route("/reset", methods=["GET", "POST"])
async def data_reset(request: Request, capital: float = 15.0):
    if request.method == "POST":
        try:
            body = await request.json()
            if body and "capital" in body:
                capital = float(body["capital"])
        except Exception:
            pass
    bot.portfolio.reset(capital)
    bot.log(f"🔄 Cartera ({bot.active_environment.upper()}) reiniciada con €{capital:.2f}")
    return {"message": "Cartera reiniciada", "capital": capital}

@data_api_app.api_route("/emergency_sell", methods=["GET", "POST"])
def data_emergency_sell():
    sold = bot.emergency_sell_all()
    return {"message": f"Se liquidaron {sold} posiciones"}

@data_api_app.api_route("/config", methods=["GET", "POST"])
async def data_config(request: Request):
    if request.method == "POST":
        try:
            body = await request.json()
            for key in [
                "order_amount_eur", "take_profit_pct", "stop_loss_pct", 
                "rsi_buy_threshold", "rsi_sell_threshold", "msci_sweep_pct",
                "breakeven_trigger_pct", "early_take_profit_pct", "price_drop_trigger_pct",
                "sma_period"
            ]:
                if key in body:
                    val = float(body[key])
                    bot.config[key] = val
                    CONFIG[key] = val
            if "symbol" in body and body["symbol"]:
                bot.set_symbol(str(body["symbol"]))
            bot.strategy.config = bot.config
            bot.log("⚙️ Parámetros actualizados.")
        except Exception:
            pass
    return {"message": "Configuración actualizada con éxito", "config": bot.config}

# Montar data_api_app en subrutas universales (incluyendo /static/api para compatibilidad HF proxy)
app.mount("/static/api", data_api_app)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/data_api", data_api_app)
app.mount("/api", data_api_app)

@app.get("/")
def get_dashboard():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return {"message": "El dashboard se está construyendo..."}
    return FileResponse(index_file)

@app.get("/dashboard")
def get_dashboard_alias():
    return FileResponse(STATIC_DIR / "index.html")
