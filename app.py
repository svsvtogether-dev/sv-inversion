import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# Bloque Gradio mínimo para compatibilidad con el entorno de Hugging Face
with gr.Blocks(title="SV Inversión AI") as demo:
    gr.Markdown("### SV Inversión AI - Bot de Trading Activo 24/7")

# Montar Gradio en /gradio para que la raíz '/' sea 100% nuestro Dashboard interactivo
app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    print(f"🚀 Iniciando SV Inversión en Hugging Face (Puerto {port})...")
    uvicorn.run(app, host="0.0.0.0", port=port)
