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

# Bloque Gradio mínimo para compatibilidad con el runtime de Hugging Face
with gr.Blocks(title="SV Inversión AI") as demo:
    pass

# Montar Gradio en una ruta secundaria para que FastAPI tenga control prioritario absoluto de / y /api/
app = gr.mount_gradio_app(fastapi_app, demo, path="/_gradio")

@fastapi_app.get("/dashboard")
def get_dashboard_alias():
    return FileResponse(STATIC_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
