import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import gradio as gr

from server import app as fastapi_app, bot, STATIC_DIR

# ZeroGPU keepalive
try:
    import spaces
    @spaces.GPU
    def gpu_ready():
        return True
    gpu_ready()
except Exception:
    pass

# Gradio container con iframe a pantalla completa
with gr.Blocks(
    title="SV Inversión AI",
    css="footer {visibility: hidden !important;} .gradio-container {padding: 0 !important; margin: 0 !important; max-width: 100% !important; background: #0a0d14 !important;}"
) as demo:
    gr.HTML('<iframe src="/dashboard" style="position:fixed; top:0; left:0; width:100vw; height:100vh; border:none; z-index:9999; background:#0a0d14;" allow="clipboard-write"></iframe>')

# Insertar las rutas completas de FastAPI al INICIO para que tengan prioridad sobre el catch-all de Gradio
for r in reversed(fastapi_app.routes):
    demo.app.routes.insert(0, r)

if __name__ == "__main__":
    demo.launch()
