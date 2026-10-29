import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.routing import Route, Mount
import gradio as gr

# ZeroGPU initialization
try:
    import spaces
    @spaces.GPU
    def _zero_gpu_keepalive():
        return True
except Exception:
    pass

from server import app as fastapi_app, bot, STATIC_DIR

# Gradio Blocks base container for ZeroGPU hosting compatibility
with gr.Blocks(title="SV Inversión AI") as demo:
    pass

# Direct overrides at the very top of router table so they take absolute priority over Gradio catch-alls:
# 1. Mount static files directory at /static
demo.app.router.routes.insert(0, Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static_override"))

# 2. Direct root / and /dashboard routes to serve index.html directly
async def serve_index(request):
    return FileResponse(STATIC_DIR / "index.html")

demo.app.router.routes.insert(0, Route("/dashboard", serve_index, methods=["GET"]))
demo.app.router.routes.insert(0, Route("/", serve_index, methods=["GET"]))

# 3. Include all full FastAPI backend endpoints (/data_api/* and /api/*)
demo.app.include_router(fastapi_app.router)

if __name__ == "__main__":
    demo.launch()
