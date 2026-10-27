---
title: SV Inversion
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: gradio
app_file: app.py
pinned: false
---

# 🤖 SV Inversión - Bot de Inversión Automatizado (Simulación 30 €)

Bot de inversión algorítmica diseñado para operar en modo **Paper Trading** con un capital virtual inicial de **30,00 €** utilizando datos de mercado en tiempo real (Binance Spot) sin requerir claves API ni arriesgar fondos reales.

---

## 🌟 Características Principales

1. **Motor Universal Multi-Mercado:**
   - **🪙 Criptomonedas (24/7):** Bitcoin (`BTC/EUR`), Ethereum (`ETH/EUR`), Solana (`SOL/EUR`).
   - **📈 Índices & ETFs Globales:** S&P 500 (`SPY`), Nasdaq 100 (`QQQ`).
   - **🏢 Acciones Líderes:** Nvidia (`NVDA`), Apple (`AAPL`), Microsoft (`MSFT`).
   - **🥇 Materias Primas:** Oro (`GC=F`), Petróleo Crudo WTI (`CL=F`).
   - **💱 Forex / Divisas:** Euro/Dólar (`EUR/USD`), Libra/Dólar (`GBP/USD`).
   - *Conversión automática en tiempo real de divisas (USD/EUR) para contabilidad unificada.*

2. **Simulación 100% Realista con 30 €:**
   - Saldo inicial exacto de 30,00 € virtual.
   - Tamaño de orden estándar de 10,00 € por compra (permite 3 tramos de compras escalonadas).
   - Aplica comisiones reales de mercado (0.10%) para reflejar la rentabilidad neta exacta.

3. **Estrategia Smart DCA & Detección de Oportunidades:**
   - **Escáner Continuo:** Monitorea todos los mercados en tiempo real y busca el activo con mayor sobreventa o descuento ($RSI \le 40$ o apoyo en bandas de Bollinger).
   - **Promediado a la baja (DCA):** Si un activo corrige tras la compra, acumula en el siguiente tramo para mejorar el precio medio.
   - **Take-Profit Automático (+2.5%):** Asegura los beneficios en cuanto el activo sube.
   - **Stop-Loss de Protección (-5.0%):** Evita drawdowns severos ante caídas anómalas.

4. **Panel de Control Web en Vivo:**
   - Filtros por categoría de mercado y selector interactivo de activos.
   - Supervisión visual de saldo total, efectivo disponible, valor de activos y P&L neto.
   - Terminal en vivo con los pensamientos y decisiones del algoritmo.

---

## 🚀 Cómo Iniciar el Bot

### Opción 1: Doble clic (Windows)
Haz doble clic sobre el archivo `run.bat` dentro de esta carpeta.

### Opción 2: Desde la terminal
```powershell
python main.py
```
*(O si utilizas la ruta de Python 3.13 directamente:)*
```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" main.py
```

El bot iniciará el servidor local y abrirá automáticamente tu navegador en:
👉 **`http://localhost:8000`**

---

## 📁 Estructura del Proyecto

```
sv inversion/
│
├── main.py               # Punto de entrada y apertura de navegador
├── server.py             # Servidor web FastAPI y API de control
├── run.bat               # Lanzador directo de Windows
├── requirements.txt      # Dependencias (fastapi, uvicorn, requests)
│
├── src/
│   ├── config.py         # Parámetros por defecto (saldo 10€, fees, umbrales)
│   ├── market_data.py    # Conexión a datos públicos de Binance y cálculo de indicadores (RSI, EMA, Bollinger)
│   ├── portfolio.py      # Motor de simulación contable, P&L y comisiones
│   ├── strategy.py       # Algoritmo Smart DCA & Dip Buyer
│   └── bot.py            # Bucle continuo de ejecución y sincronización
│
├── static/
│   ├── index.html        # Dashboard visual moderno
│   ├── style.css         # Estilos oscuros de terminal financiera
│   └── app.js            # Lógica de actualización y llamadas a la API
│
└── data/
    └── portfolio.json    # Persistencia del saldo y operaciones entre reinicios
```

---

## ⚙️ Ajuste de Parámetros desde el Dashboard

Desde el panel web puedes personalizar:
* **Tamaño por compra (€):** Cantidad de euros que el bot invertirá en cada orden (por ejemplo, 2.50 € o 3.00 €).
* **Take-Profit (%):** El porcentaje de ganancia neta al cual el bot venderá para asegurar beneficios.
* **Stop-Loss (%):** Porcentaje máximo de caída tolerable antes de cerrar por seguridad.
* **Umbral RSI Compra:** Nivel por debajo del cual el bot considera que el activo está barato (por defecto <= 40).
* **Umbral RSI Venta:** Nivel por encima del cual el bot asegura ganancias si el mercado sube con fuerza (por defecto >= 65).
