import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
import uvicorn
import webbrowser
import threading
import time

def open_browser(port):
    time.sleep(1.5)
    print("\n" + "=" * 60)
    print("🚀 Bot SV Inversión iniciado con éxito.")
    print(f"🌐 Dashboard disponible en: http://localhost:{port}")
    print("=" * 60 + "\n")
    try:
        if "RENDER" not in os.environ:
            webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    uvicorn.run("server:app", host=host, port=port, reload=False, log_level="info")
