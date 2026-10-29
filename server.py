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

# Instancia global del bot
bot = TradingBot()
bot.start()

# Rutas estáticas
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def get_dashboard():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return {"message": "El dashboard se está construyendo..."}
    return FileResponse(index_file)

@app.api_route("/api/status", methods=["GET", "POST"])
def get_status():
    return bot.get_state()

@app.api_route("/api/toggle", methods=["GET", "POST"])
def toggle_bot():
    bot.is_running = not bot.is_running
    state_str = "activo" if bot.is_running else "en pausa"
    bot.log(f"Bot marcado como {state_str} por el usuario.")
    return {"is_running": bot.is_running}

class EnvironmentRequest(BaseModel):
    environment: Optional[str] = None

@app.api_route("/api/environment", methods=["GET", "POST"])
async def change_environment(request: Request, env: Optional[str] = None):
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

class LiveArmedRequest(BaseModel):
    armed: Optional[bool] = None

@app.api_route("/api/live_armed", methods=["GET", "POST"])
async def change_live_armed(request: Request, armed: Optional[bool] = None):
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

class SymbolRequest(BaseModel):
    symbol: Optional[str] = None

@app.api_route("/api/symbol", methods=["GET", "POST"])
async def change_symbol(request: Request, symbol: Optional[str] = None):
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

class CategoryRequest(BaseModel):
    category: Optional[str] = None

@app.api_route("/api/category", methods=["GET", "POST"])
async def change_category(request: Request, category: Optional[str] = None):
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

class ResetRequest(BaseModel):
    capital: float = 250.0

@app.api_route("/api/reset", methods=["GET", "POST"])
async def reset_portfolio(request: Request, capital: float = 250.0):
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

@app.api_route("/api/emergency_sell", methods=["GET", "POST"])
def emergency_sell():
    sold = bot.emergency_sell_all()
    return {"message": f"Se liquidaron {sold} posiciones"}

class ConfigUpdateRequest(BaseModel):
    order_amount_eur: float
    take_profit_pct: float
    stop_loss_pct: float
    rsi_buy_threshold: float
    rsi_sell_threshold: float
    msci_sweep_pct: float = 0.0

@app.api_route("/api/config", methods=["GET", "POST"])
async def update_config(request: Request):
    if request.method == "POST":
        try:
            body = await request.json()
            for key in ["order_amount_eur", "take_profit_pct", "stop_loss_pct", "rsi_buy_threshold", "rsi_sell_threshold", "msci_sweep_pct"]:
                if key in body:
                    val = float(body[key])
                    bot.config[key] = val
                    CONFIG[key] = val
            bot.strategy.config = bot.config
            bot.log(f"⚙️ Parámetros actualizados.")
        except Exception as e:
            pass
    return {"message": "Configuración actualizada con éxito", "config": bot.config}
