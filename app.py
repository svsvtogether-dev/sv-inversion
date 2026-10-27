import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import gradio as gr

# Hugging Face ZeroGPU keepalive
try:
    import spaces
    @spaces.GPU
    def gpu_ready():
        return True
    gpu_ready()
except Exception:
    pass

from server import app as fastapi_app, bot, STATIC_DIR

with gr.Blocks(
    title="SV Inversión AI - Cloud 24/7",
    theme=gr.themes.Base(),
    css="""
    footer {display: none !important;}
    .gradio-container {padding: 0 !important; margin: 0 !important; max-width: 100% !important;}
    iframe {width: 100vw; height: 100vh; border: none;}
    """
) as demo:
    gr.HTML("""
        <iframe src="/dashboard" style="position:fixed; top:0; left:0; width:100vw; height:100vh; border:none; z-index:99999;"></iframe>
    """)

# Montar las rutas en demo.app
demo.app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@demo.app.get("/dashboard")
def get_dashboard_html():
    index_file = STATIC_DIR / "index.html"
    return FileResponse(index_file)

@demo.app.get("/api/status")
def get_status():
    return bot.get_state()

@demo.app.post("/api/toggle")
def toggle_bot():
    bot.is_running = not bot.is_running
    return {"is_running": bot.is_running}

class SymbolRequest(BaseModel):
    symbol: str

@demo.app.post("/api/symbol")
def change_symbol(req: SymbolRequest):
    bot.set_symbol(req.symbol)
    return {"symbol": bot.current_symbol}

class CategoryRequest(BaseModel):
    category: str

@demo.app.post("/api/category")
def change_category(req: CategoryRequest):
    bot.set_category(req.category)
    return {"category": bot.active_category}

class ResetRequest(BaseModel):
    capital: float = 30.0

@demo.app.post("/api/reset")
def reset_portfolio(req: ResetRequest):
    bot.portfolio.reset(req.capital)
    return {"message": "Cartera reiniciada", "capital": req.capital}

@demo.app.post("/api/emergency_sell")
def emergency_sell():
    sold = bot.emergency_sell_all()
    return {"message": f"Se liquidaron {sold} posiciones"}

class ConfigUpdateRequest(BaseModel):
    order_amount_eur: float
    take_profit_pct: float
    stop_loss_pct: float
    rsi_buy_threshold: float
    rsi_sell_threshold: float
    msci_sweep_pct: float = 50.0

@demo.app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    bot.config["order_amount_eur"] = req.order_amount_eur
    bot.config["take_profit_pct"] = req.take_profit_pct
    bot.config["stop_loss_pct"] = req.stop_loss_pct
    bot.config["rsi_buy_threshold"] = req.rsi_buy_threshold
    bot.config["rsi_sell_threshold"] = req.rsi_sell_threshold
    bot.config["msci_sweep_pct"] = req.msci_sweep_pct
    bot.strategy.config = bot.config
    return {"message": "Configuración actualizada con éxito"}

if __name__ == "__main__":
    demo.launch(allowed_paths=[str(STATIC_DIR)])
