import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import gradio as gr

from server import bot, STATIC_DIR
from src.config import CONFIG

# Modelos Pydantic para peticiones
class EnvironmentRequest(BaseModel):
    environment: str

class LiveArmedRequest(BaseModel):
    armed: bool

class SymbolRequest(BaseModel):
    symbol: str

class CategoryRequest(BaseModel):
    category: str

class ResetRequest(BaseModel):
    capital: float = 250.0

class ConfigUpdateRequest(BaseModel):
    order_amount_eur: float
    take_profit_pct: float
    stop_loss_pct: float
    rsi_buy_threshold: float
    rsi_sell_threshold: float
    msci_sweep_pct: float = 0.0

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
    gr.HTML("<script>window.location.href='/dashboard';</script>")

# Registrar endpoints directamente en demo.app
app = demo.app

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def get_root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/dashboard")
def get_dashboard():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/status")
def get_status():
    return bot.get_state()

@app.post("/api/environment")
def change_environment(req: EnvironmentRequest):
    bot.set_environment(req.environment)
    return {"active_environment": bot.active_environment}

@app.post("/api/live_armed")
def change_live_armed(req: LiveArmedRequest):
    bot.set_live_armed(req.armed)
    return {"live_trading_armed": bot.live_trading_armed}

@app.post("/api/toggle")
def toggle_bot():
    bot.is_running = not bot.is_running
    state_str = "activo" if bot.is_running else "en pausa"
    bot.log(f"Bot marcado como {state_str} por el usuario.")
    return {"is_running": bot.is_running}

@app.post("/api/symbol")
def change_symbol(req: SymbolRequest):
    bot.set_symbol(req.symbol)
    return {"symbol": bot.current_symbol}

@app.post("/api/category")
def change_category(req: CategoryRequest):
    bot.set_category(req.category)
    return {"category": bot.active_category, "symbol": bot.current_symbol}

@app.post("/api/reset")
def reset_portfolio(req: ResetRequest):
    bot.portfolio.reset(req.capital)
    bot.log(f"🔄 Cartera ({bot.active_environment.upper()}) reiniciada con €{req.capital:.2f}")
    return {"message": "Cartera reiniciada", "capital": req.capital}

@app.post("/api/emergency_sell")
def emergency_sell():
    sold = bot.emergency_sell_all()
    return {"message": f"Se liquidaron {sold} posiciones"}

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    for key in ["order_amount_eur", "take_profit_pct", "stop_loss_pct", "rsi_buy_threshold", "rsi_sell_threshold", "msci_sweep_pct"]:
        val = getattr(req, key)
        bot.config[key] = val
        CONFIG[key] = val
    bot.strategy.config = bot.config
    bot.log(f"⚙️ Parámetros actualizados (Orden: €{req.order_amount_eur:.1f} | TP: +{req.take_profit_pct}% | Desvío MSCI World: {req.msci_sweep_pct}%).")
    return {"message": "Configuración actualizada con éxito"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_port=port)
