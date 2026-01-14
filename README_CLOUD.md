# ☁️ Guía de Despliegue en la Nube (Gratis)

Para tener tu bot funcionando 24/7 sin tu PC, usaremos **Streamlit Cloud**.

### Paso 1: Subir código a GitHub
1.  Crea una cuenta en [github.com](https://github.com).
2.  Crea un **New Repository** (Ponle nombre, ej: `ia-trading-bot` y márcalo como **Private** si no quieres que nadie vea el código).
3.  Sube todos los archivos de esta carpeta (EXCEPTO `.env`, `.venv_mobile`, y `.git`).
    *   Puedes hacerlo arrastrando los archivos a la web de GitHub o usando GitHub Desktop.

### Paso 2: Conectar a Streamlit Cloud
1.  Ve a [share.streamlit.io](https://share.streamlit.io/).
2.  Inicia sesión con tu cuenta de GitHub.
3.  Dale a **"New app"**.
4.  Selecciona el repositorio que creaste (`ia-trading-bot`).
5.  En "Main file path", escribe: `main.py`.
6.  Dale a **"Deploy!"**.

### Paso 3: Configurar Secretos (La parte importante)
Como no subimos el archivo `.env` por seguridad, tenemos que configurar las claves en la nube.

1.  En tu panel de Streamlit Cloud, ve a tu app.
2.  Haz clic en los tres puntitos `⋮` (Settings) -> **"Secrets"**.
3.  Copia y pega el siguiente bloque, rellenando con TUS datos reales:

```toml
[telegram]
token = "8409305386:AAHBZCHtZsSPRIbtPX2lWSSyeEn4nMOH378"
chat_id = "6955184680"

[deepseek]
api_key = "sk-4385aefc4d1944218ad51cc8319cb55e"
```

4.  Dale a **Save**.

### ¡Listo! 🚀
Tu bot se reiniciará y ahora vivirá en internet. Podrás acceder a él desde la URL que te da Streamlit (ej: `https://ia-trading-bot.streamlit.app`) desde cualquier celular o PC, las 24 horas del día.
