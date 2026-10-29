import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import gradio as gr
from server import app as fastapi_app, bot, STATIC_DIR

# Hugging Face ZeroGPU keepalive
try:
    import spaces
    @spaces.GPU
    def gpu_ready():
        return True
    gpu_ready()
except Exception:
    pass

with gr.Blocks(title="SV Inversión AI") as demo:
    gr.HTML("<script>window.location.href='/';</script>")

# Montar archivos estáticos
demo.app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Integrar automáticamente todas las rutas de FastAPI (API de Status, Environment, Live Armed, Config, etc.)
for route in fastapi_app.routes:
    if hasattr(route, "path") and route.path not in ["/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"]:
        demo.app.routes.insert(0, route)

@demo.app.get("/")
def get_root():
    return FileResponse(STATIC_DIR / "index.html")

@demo.app.get("/dashboard")
def get_dashboard_alias():
    return FileResponse(STATIC_DIR / "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_port=port)
