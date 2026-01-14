import os
import time
import socket
import sys

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def main():
    try:
        import qrcode
        from colorama import init, Fore, Style
    except ImportError:
        print("Error: Ejecuta 'pip install qrcode[pil] colorama' primero.")
        return

    init()
    
    # Limpiar consola
    os.system('cls' if os.name == 'nt' else 'clear')
    
    ip = get_local_ip()
    port = 8501
    url = f"http://{ip}:{port}"
    
    print(f"\n{Fore.GREEN}╔════════════════════════════════════════╗")
    print(f"║       🤖 IA TRADING - MODO MÓVIL       ║")
    print(f"╚════════════════════════════════════════╝{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}ℹ️  Streamlit no genera archivos .apk nativos.{Style.RESET_ALL}")
    print(f"   Pero puedes usar la app en tu móvil AHORA MISMO así:\n")
    
    print(f"{Fore.CYAN}1. Asegúrate que tu móvil esté en el mismo Wi-Fi que esta PC.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}2. Escanea este código QR con tu cámara:{Style.RESET_ALL}\n")
    
    # Generar QR
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    
    print(f"\n{Fore.GREEN}🔗 O entra manualmente a: {Style.BRIGHT}{url}{Style.RESET_ALL}\n")
    
    print(f"{Fore.WHITE}📲 {Style.BRIGHT}COMO INSTALARLO COMO APP:{Style.RESET_ALL}")
    print(f"   En el navegador de tu móvil, abre el menú y selecciona:")
    print(f"   {Fore.YELLOW}⭐️ 'Agregar a la pantalla principal' (Android){Style.RESET_ALL}")
    print(f"   {Fore.YELLOW}⭐️ 'Agregar al inicio' (iOS){Style.RESET_ALL}")
    print(f"   Esto creará un ícono idéntico a una App real.\n")
    
    print(f"{Fore.MAGENTA}🚀 Iniciando servidor... (Presiona Ctrl+C para salir){Style.RESET_ALL}")
    time.sleep(2)
    
    # Ejecutar Streamlit
    os.system(f"streamlit run main.py --server.address 0.0.0.0 --server.port {port}")

if __name__ == "__main__":
    main()
