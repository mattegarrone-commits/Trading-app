# 📖 Guía de Usuario - IA Trading Institucional

Bienvenido a la versión **2.3 Lite** de tu plataforma de trading inteligente. Este sistema analiza el mercado utilizando modelos institucionales (SMC) e Inteligencia Artificial de vanguardia.

---

## 🛠️ Instalación (Solo la primera vez)

Para usar esta herramienta, solo necesitas instalar Python. Todo lo demás se configura automáticamente.

1.  **Descargar Python**:
    *   Ve a [python.org/downloads](https://www.python.org/downloads/).
    *   Descarga la última versión para Windows.
    *   **¡IMPORTANTE!**: Al instalar, marca la casilla que dice **"Add Python to PATH"** antes de darle a "Install Now".

2.  **Iniciar el Bot**:
    *   Haz doble clic en el archivo `start_dashboard.bat`.
    *   La primera vez tardará unos minutos instalando todo lo necesario.
    *   Se abrirá automáticamente una ventana en tu navegador con la aplicación.

---

## 🚀 Inicio Rápido

1.  **Selecciona un Mercado**: Ve a la pestaña **"Forex/Crypto"** o **"Argentina"**.
2.  **Elige Timeframe**: Selecciona `5m` (Scalping) o `15m/1h` (Day Trading).
3.  **Analizar**: Presiona **"🔍 ANALIZAR MERCADO"**.
4.  **Resultados**:
    *   **Tarjetas Verdes/Rojas**: Oportunidades claras detectadas.
    *   **Gráficos**: Muestran niveles de Entrada, Stop Loss y Take Profit.
    *   **Alertas**: Si configuraste Telegram, recibirás el aviso en tu móvil.

---

## 🤖 ¿Cómo funciona la IA?
El sistema combina tres capas de análisis:
1.  **SMC (Smart Money Concepts)**: Detecta la estructura del mercado (BOS, CHoCH), zonas de liquidez y Order Blocks.
2.  **IA DeepSeek**: Un modelo de razonamiento profundo evalúa el contexto macroeconómico, las noticias recientes y valida la calidad del setup técnico.
3.  **Gestión de Riesgo**: Filtra operaciones con baja probabilidad (<65%) o mal ratio riesgo/beneficio.

---

## 📱 Notificaciones en tu Celular (Telegram)

Puedes configurar tu propio bot para recibir las alertas de trading directamente en tu celular.

### ¿Cómo activar tus alertas?

1.  **Crea tu Bot Personal**:
    *   Abre Telegram y busca **@BotFather**.
    *   Envía `/newbot` y sigue los pasos para ponerle nombre.
    *   Copia el **TOKEN** que te da (ej: `123456:ABC...`).

2.  **Obtén tu ID**:
    *   Busca **@userinfobot** en Telegram y dale Start.
    *   Copia el número **Id** que te muestra.

3.  **Configura en la App**:
    *   Abre el menú lateral **"Configuración Avanzada"**.
    *   Pega tu **Token** y tu **Chat ID** en los campos correspondientes.
    *   Activa el interruptor **"Enviar Alertas a Telegram"**.
    *   ¡Listo! Dale a "Probar Notificación" para verificar.

---

## 🧠 Configuración de IA (DeepSeek)
Para obtener el mejor análisis fundamental, puedes usar tu propia clave API de DeepSeek (opcional pero recomendado).
1.  Regístrate en [platform.deepseek.com](https://platform.deepseek.com/).
2.  Crea una API Key.
3.  Pégala en **"Configuración Avanzada" > "Tu API Key DeepSeek"**.

---

## ⚠️ Aviso de Riesgo
Esta herramienta es un asistente de análisis. **No es un asesor financiero.**
*   El mercado tiene riesgos. Nunca operes dinero que no puedas permitirte perder.
*   Verifica siempre las señales antes de operar.
*   El rendimiento pasado no garantiza resultados futuros.

