import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.routing import Route, Mount
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

from server import app as fastapi_app, bot, STATIC_DIR

# Monkey-patch App.create_app so that ALL FastAPI routes (static files, /dashboard, /data_api/*)
# are inserted at index 0 of the router table before Gradio's catch-all router can intercept them
_orig_create_app = App.create_app

def _patched_create_app(*args, **kwargs):
    app = _orig_create_app(*args, **kwargs)
    
    # Insert all routes from server.py at index 0 in reverse order so original order is preserved
    for r in reversed(fastapi_app.router.routes):
        app.router.routes.insert(0, r)
        
    return app

App.create_app = _patched_create_app

# Gradio Blocks container with seamless iframe to /static/index.html as robust fallback
with gr.Blocks(
    title="SV Inversión AI",
    css="footer {display: none !important;} .gradio-container {padding: 0 !important; margin: 0 !important; max-width: 100% !important; background: #0a0d14 !important;}"
) as demo:
    gr.HTML('<iframe src="/static/index.html" style="position:fixed; top:0; left:0; width:100vw; height:100vh; border:none; z-index:99999; background:#0a0d14;" allow="clipboard-write"></iframe>')

if __name__ == "__main__":
    demo.launch()
