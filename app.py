import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import gradio as gr
try:
    from gradio import Server
except ImportError:
    Server = None

# Hugging Face ZeroGPU keepalive
try:
    import spaces
    @spaces.GPU
    def gpu_ready():
        return True
    gpu_ready()
except Exception:
    pass

from server import bot, STATIC_DIR
from src.config import CONFIG

if Server is not None:
    app = Server()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def get_dashboard():
        index_file = STATIC_DIR / "index.html"
        return FileResponse(index_file)

    @app.get("/api/status")
    def get_status():
        return bot.get_state()

    @app.post("/api/toggle")
    def toggle_bot():
        bot.is_running = not bot.is_running
        state_str = "activo" if bot.is_running else "en pausa"
        bot.log(f"Bot marcado como {state_str} por el usuario.")
        return {"is_running": bot.is_running}

    class SymbolRequest(BaseModel):
        symbol: str

    @app.post("/api/symbol")
    def change_symbol(req: SymbolRequest):
        bot.set_symbol(req.symbol)
        return {"symbol": bot.current_symbol}

    class CategoryRequest(BaseModel):
        category: str

    @app.post("/api/category")
    def change_category(req: CategoryRequest):
        bot.set_category(req.category)
        return {"category": bot.active_category, "symbol": bot.current_symbol}

    class ResetRequest(BaseModel):
        capital: float = 250.0

    @app.post("/api/reset")
    def reset_portfolio(req: ResetRequest):
        bot.portfolio.reset(req.capital)
        bot.log(f"🔄 Cartera virtual reiniciada con €{req.capital:.2f}")
        return {"message": "Cartera reiniciada", "capital": req.capital}

    @app.post("/api/emergency_sell")
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
        app.launch()
else:
    with gr.Blocks(title="SV Inversión AI") as demo:
        gr.HTML("<script>window.location.href='/dashboard';</script>")
    demo.app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    @demo.app.get("/dashboard")
    def get_dashboard_html():
        return FileResponse(STATIC_DIR / "index.html")
    if __name__ == "__main__":
        demo.launch()
