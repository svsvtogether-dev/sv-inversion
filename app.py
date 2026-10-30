import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.routing import Mount
import gradio as gr
from gradio.routes import App

# ZeroGPU initialization
try:
    import spaces
    @spaces.GPU
    def _zero_gpu_keepalive():
        return True
except Exception:
    pass

from server import data_api_app, bot, STATIC_DIR

# Monkey-patch App.create_app para insertar de forma prioritaria los Mounts de FastAPI
_orig_create_app = App.create_app

def _patched_create_app(*args, **kwargs):
    app = _orig_create_app(*args, **kwargs)
    
    # 1. Mount data_api sub-app under /static/api (máxima prioridad, atraviesa el reverse proxy de Hugging Face)
    app.router.routes.insert(0, Mount("/static/api", data_api_app, name="static_api_override"))
    
    # 2. Mount static directory para /static/style.css, /static/app.js, /static/index.html
    app.router.routes.insert(1, Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static_override"))
    
    # 3. Mount data_api y api para compatibilidad
    app.router.routes.insert(2, Mount("/data_api", data_api_app, name="data_api_override"))
    app.router.routes.insert(3, Mount("/api", data_api_app, name="api_override"))
    
    return app

App.create_app = _patched_create_app

# Gradio Blocks container con iframe a pantalla completa hacia /static/index.html
with gr.Blocks(title="SV Inversión AI") as demo:
    gr.HTML('<iframe src="/static/index.html?v=10" style="position:fixed; top:0; left:0; width:100vw; height:100vh; border:none; z-index:99999; background:#0a0d14;" allow="clipboard-write"></iframe>')

if __name__ == "__main__":
    demo.launch()
