import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.bot import TradingBot

app = FastAPI(title="SV Inversión - Bot de Trading 10€")

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
    return {"category": bot.active_category}

class ResetRequest(BaseModel):
    capital: float = 10.0

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
    msci_sweep_pct: float = 50.0

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    bot.config["order_amount_eur"] = req.order_amount_eur
    bot.config["take_profit_pct"] = req.take_profit_pct
    bot.config["stop_loss_pct"] = req.stop_loss_pct
    bot.config["rsi_buy_threshold"] = req.rsi_buy_threshold
    bot.config["rsi_sell_threshold"] = req.rsi_sell_threshold
    bot.config["msci_sweep_pct"] = req.msci_sweep_pct
    bot.strategy.config = bot.config
    bot.log(f"⚙️ Parámetros actualizados (Desvío MSCI World: {req.msci_sweep_pct}%).")
    return {"message": "Configuración actualizada con éxito"}
