# IA Trading Institucional - Deploy Guide

Esta aplicación está lista para ser desplegada en la nube y funcionar 24/7.

## Opción Recomendada: Streamlit Cloud (Gratis y Estable)

Esta opción mantiene tu bot activo siempre, sin necesidad de tener tu PC encendida.

### Pasos para Activar:

1.  **Crear cuenta en GitHub**: Ve a [github.com](https://github.com) y crea una cuenta gratuita.
2.  **Subir el código**:
    *   Crea un nuevo repositorio (llámalo `ia-trading-bot`).
    *   Sube todos los archivos de esta carpeta al repositorio (puedes arrastrarlos en la web de GitHub o usar Git Desktop).
    *   Asegúrate de incluir `requirements.txt`.
3.  **Conectar con Streamlit Cloud**:
    *   Ve a [share.streamlit.io](https://share.streamlit.io) y regístrate con tu cuenta de GitHub.
    *   Haz clic en "New app".
    *   Selecciona tu repositorio `ia-trading-bot`.
    *   En "Main file path", escribe `main.py`.
    *   Haz clic en **Deploy!**.

### Configuración de Seguridad (Secretos)

Para que el login y las notificaciones funcionen sin exponer tus claves, configura los "Secrets" en el panel de Streamlit Cloud:

1.  En tu app desplegada, ve a **Settings** (o los tres puntos) -> **Secrets**.
2.  Copia y pega el siguiente contenido, reemplazando con tus datos reales:

```toml
[auth]
# Usuarios permitidos (Formato lista)
allowed_users = ["MG12", "OTROUSER"]
# Contraseña mensual
password = "7xR9mK2pQ5wL"

[telegram]
# Token de tu bot Admin (el que recibe copias de todo)
admin_token = "TU_TOKEN_DE_TELEGRAM_AQUI"
admin_chat_id = "TU_CHAT_ID_AQUI"
```

3.  Guarda los cambios. La app se reiniciará automáticamente.

## Opción 2: Ejecución Local (Tu PC como Servidor)

Si prefieres usar tu propia PC (debe estar encendida 24/7):

1.  Abre la terminal en la carpeta del proyecto.
2.  Ejecuta: `streamlit run main.py`
3.  Para acceder desde internet, necesitarás una herramienta como `ngrok` o configurar el reenvío de puertos (Port Forwarding) en tu router (Puerto 8501).

**Nota:** La opción de Streamlit Cloud es mucho más segura y fiable para un servicio "siempre activo".
