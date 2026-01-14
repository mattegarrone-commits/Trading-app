import requests
import time

TOKEN = "8409305386:AAHBZCHtZsSPRIbtPX2lWSSyeEn4nMOH378"
URL = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

print(f"Buscando mensajes para el bot...")

try:
    response = requests.get(URL, timeout=10)
    data = response.json()
    
    if data.get("ok"):
        results = data.get("result", [])
        if results:
            # Tomar el último mensaje
            last_msg = results[-1]
            chat_id = last_msg.get("message", {}).get("chat", {}).get("id")
            user_name = last_msg.get("message", {}).get("from", {}).get("first_name")
            
            print(f"¡ENCONTRADO!")
            print(f"Chat ID: {chat_id}")
            print(f"Usuario: {user_name}")
            
            # Guardar en .env automáticamente
            with open(".env", "a") as f:
                f.write(f"\nTELEGRAM_CHAT_ID={chat_id}")
            print("Chat ID guardado en .env correctamente.")
        else:
            print("No se encontraron mensajes. Por favor envía 'Hola' a tu bot en Telegram.")
    else:
        print(f"Error en API: {data}")

except Exception as e:
    print(f"Error de conexión: {e}")
