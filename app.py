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

# Monkey-patch App.create_app so that WHENEVER Hugging Face or Gradio builds the ASGI App,
# our static files, dashboard routes, and data_api routes are permanently placed at index 0
_orig_create_app = App.create_app

def _patched_create_app(*args, **kwargs):
    app = _orig_create_app(*args, **kwargs)
    
    # 1. Mount static directory
    app.router.routes.insert(0, Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static_override"))
    
    # 2. Direct handlers for / and /dashboard
    async def serve_index(request):
        return FileResponse(STATIC_DIR / "index.html")
        
    app.router.routes.insert(0, Route("/dashboard", serve_index, methods=["GET"]))
    app.router.routes.insert(0, Route("/", serve_index, methods=["GET"]))
    
    # 3. Include full FastAPI backend endpoints
    app.include_router(fastapi_app.router)
    return app

App.create_app = _patched_create_app

# Gradio container
with gr.Blocks(title="SV Inversión AI") as demo:
    pass

if __name__ == "__main__":
    demo.launch()
