import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import gradio as gr

# Garantizar compatibilidad con UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Importar el servidor y el bot existentes
from server import app as fastapi_app, bot, STATIC_DIR

# Crear bloque Gradio con visor del Dashboard integrado
with gr.Blocks(
    title="SV Inversión AI - Cloud 24/7",
    theme=gr.themes.Base(),
    css="""
    footer {display: none !important;}
    .gradio-container {padding: 0 !important; margin: 0 !important; max-width: 100% !important;}
    iframe {width: 100vw; height: 100vh; border: none;}
    """
) as demo:
    gr.HTML("""
        <iframe src="/dashboard" style="position:fixed; top:0; left:0; width:100vw; height:100vh; border:none; z-index:99999;"></iframe>
    """)

# Añadir ruta /dashboard para que el iframe sirva index.html directamente
@fastapi_app.get("/dashboard")
def get_dashboard_html():
    index_file = STATIC_DIR / "index.html"
    return FileResponse(index_file)

# Montar Gradio en FastAPI
app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    print(f"🚀 Iniciando SV Inversión en Hugging Face (Puerto {port})...")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
