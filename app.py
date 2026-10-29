import os
import sys
from typing import Optional
from pathlib import Path
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import gradio as gr

from server import bot, STATIC_DIR
from src.config import CONFIG

# ZeroGPU keepalive
try:
    import spaces
    @spaces.GPU
    def gpu_ready():
        return True
    gpu_ready()
except Exception:
    pass

with gr.Blocks(title="SV Inversión AI") as demo:
    gr.HTML('<iframe src="/dashboard" style="position:fixed; top:0; left:0; width:100%; height:100%; border:none; z-index:9999;" allow="clipboard-write"></iframe>')

app = demo.app

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/dashboard")
def get_dashboard():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/")
def get_root():
    return FileResponse(STATIC_DIR / "index.html")

@app.api_route("/data_api/status", methods=["GET", "POST"])
@app.api_route("/api/status", methods=["GET", "POST"])
def get_status():
    return bot.get_state()

@app.api_route("/data_api/environment", methods=["GET", "POST"])
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

@app.api_route("/data_api/live_armed", methods=["GET", "POST"])
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

@app.api_route("/data_api/toggle", methods=["GET", "POST"])
@app.api_route("/api/toggle", methods=["GET", "POST"])
def toggle_bot():
    bot.is_running = not bot.is_running
    state_str = "activo" if bot.is_running else "en pausa"
    bot.log(f"Bot marcado como {state_str} por el usuario.")
    return {"is_running": bot.is_running}

@app.api_route("/data_api/symbol", methods=["GET", "POST"])
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

@app.api_route("/data_api/category", methods=["GET", "POST"])
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

@app.api_route("/data_api/reset", methods=["GET", "POST"])
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

@app.api_route("/data_api/emergency_sell", methods=["GET", "POST"])
@app.api_route("/api/emergency_sell", methods=["GET", "POST"])
def emergency_sell():
    sold = bot.emergency_sell_all()
    return {"message": f"Se liquidaron {sold} posiciones"}

@app.api_route("/data_api/config", methods=["GET", "POST"])
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
        except Exception:
            pass
    return {"message": "Configuración actualizada con éxito"}

if __name__ == "__main__":
    demo.launch()
