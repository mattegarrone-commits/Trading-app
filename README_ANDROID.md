# GUÍA DEFINITIVA: APP PARA VIAJES (SIN COMPUTADORA)

Si te vas de viaje y NO llevas la computadora, la única forma de que la app funcione es **subiéndola a Internet (La Nube)**. Si la dejas en tu PC, se apagará cuando la PC se apague o hiberne.

Sigue estos pasos EXACTOS para tenerla en tu celular 24/7 gratis.

## PASO 1: Subir código a GitHub (Si no tienes cuenta, crea una gratis)
1. Entra a github.com y crea un repositorio nuevo llamado `ia-trading-bot`.
2. Sube todos los archivos de esta carpeta (excepto `.env` y la carpeta `venv`).
   - Puedes usar "Upload files" en la web de GitHub si no sabes usar Git.

## PASO 2: Desplegar en Streamlit Cloud (Gratis)
1. Entra a [share.streamlit.io](https://share.streamlit.io/).
2. Conecta tu cuenta de GitHub.
3. Dale a "New app".
4. Selecciona el repositorio `ia-trading-bot`.
5. En "Main file path", escribe `streamlit_app.py` (o `main.py`).
6. **IMPORTANTE - SECRETOS:**
   - Dale clic a "Advanced settings" -> "Secrets".
   - Copia y pega el contenido de tu archivo `.env` local aquí. Debe verse así:
     ```toml
     DEEPSEEK_API_KEY = "tu-clave-aqui"
     TELEGRAM_BOT_TOKEN = "tu-token-aqui"
     TELEGRAM_CHAT_ID = "tu-chat-id-aqui"
     ```
7. Dale clic a **"Deploy!"**.

## PASO 3: INSTALAR EN EL MÓVIL (Como App Real)
Una vez que Streamlit te de la URL (ej: `https://ia-trading-bot.streamlit.app`):

1. **Abre esa URL en Chrome en tu celular.**
2. Toca el menú de 3 puntos (⋮) arriba a la derecha.
3. Toca **"Agregar a la pantalla principal"** (o "Instalar aplicación").
4. Ponle de nombre "IA Trading".

¡LISTO! Ahora tienes un ícono en tu celular que abre la app DIRECTAMENTE desde la nube.
- Funciona 24/7.
- No necesitas tu PC encendida.
- Es gratis.

## OPCIONAL: ¿Realmente quieres un APK?
Si insistes en un archivo `.apk` instalable:
1. Copia tu URL de Streamlit Cloud (`https://...`).
2. Ve a **webintoapp.com** (es gratis).
3. Pega la URL.
4. Descarga el APK e instálalo.
   (Pero la opción de "Agregar a pantalla principal" es mejor y más rápida).
