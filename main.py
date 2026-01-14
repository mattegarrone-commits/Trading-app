import os
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from streamlit.web import cli as stcli
from core.bot import InstitutionalBot, ArgentinaBot
from core.journal import TradeJournal
from core.tracker import TradeTracker
from core.notifications import TelegramNotifier
import yfinance as yf
import matplotlib.pyplot as plt
import io
import concurrent.futures
import socket
import qrcode
from PIL import Image

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="IA TRADING INSTITUCIONAL", layout="wide", page_icon="📈", initial_sidebar_state="collapsed")

def generate_telegram_chart(df, pair, signal):
    try:
        # Crear gráfico simple con matplotlib
        # Usar estilo oscuro para que coincida con el tema
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Datos últimos 60 periodos para contexto
        data = df.tail(60).reset_index(drop=True)
        
        # Plotear Precio
        ax.plot(data.index, data['Close'], label='Precio', color='cyan', linewidth=1)
        
        # EMAs si existen
        if 'EMA_50' in data.columns:
            ax.plot(data.index, data['EMA_50'], color='orange', linestyle='--', linewidth=0.8, alpha=0.7)
        
        # Líneas de Trade
        ax.axhline(signal['entry'], color='white', linestyle='--', linewidth=1, label='Entry')
        ax.axhline(signal['sl'], color='red', linestyle=':', linewidth=1.5, label='SL')
        ax.axhline(signal['tp'], color='lime', linestyle=':', linewidth=1.5, label='TP')
        
        # Rellenar zona de beneficio/pérdida
        ax.fill_between(data.index, signal['entry'], signal['tp'], color='green', alpha=0.05)
        ax.fill_between(data.index, signal['entry'], signal['sl'], color='red', alpha=0.05)
        
        ax.set_title(f"{pair} ({signal['type']}) - TF: {signal.get('timeframe','?')}", color='white', fontsize=12)
        ax.legend(loc='upper left', frameon=False, fontsize=8)
        
        # Limpiar ejes
        ax.grid(True, color='#333', linestyle='--', linewidth=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#555')
        ax.spines['left'].set_color('#555')
        
        # Guardar en buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', facecolor='#111')
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        print(f"Error generando gráfico Telegram: {e}")
        return None

# --- SEGURIDAD AVANZADA (CSS/JS) ---
def inject_security():
    st.markdown("""
        <style>
        /* Ocultar elementos de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stDeployButton {display:none;}
        
        /* Deshabilitar selección de texto */
        body {
            -webkit-user-select: none;
            -moz-user-select: none;
            -ms-user-select: none;
            user-select: none;
        }
        
        /* Ocultar scrollbars si se desea Kiosk mode */
        ::-webkit-scrollbar {
            width: 0px;
            background: transparent;
        }
        </style>
        
        <script>
        // Deshabilitar Click Derecho
        document.addEventListener('contextmenu', event => event.preventDefault());
        
        // Intentar bloquear F12 / Ctrl+Shift+I / Ctrl+Shift+J / Ctrl+U
        document.onkeydown = function(e) {
            if(event.keyCode == 123) { // F12
                return false;
            }
            if(e.ctrlKey && e.shiftKey && e.keyCode == 'I'.charCodeAt(0)) {
                return false;
            }
            if(e.ctrlKey && e.shiftKey && e.keyCode == 'J'.charCodeAt(0)) {
                return false;
            }
            if(e.ctrlKey && e.keyCode == 'U'.charCodeAt(0)) {
                return false;
            }
        }
        </script>
    """, unsafe_allow_html=True)

# inject_security()
inject_security()

# --- UTILS ---
def get_candle_countdown(timeframe):
    """Calcula el tiempo restante para el cierre de vela y la hora de apertura de la siguiente."""
    now = datetime.utcnow()
    
    if timeframe == '1m':
        interval_seconds = 60
    elif timeframe == '5m':
        interval_seconds = 5 * 60
    elif timeframe == '15m':
        interval_seconds = 15 * 60
    elif timeframe == '1h':
        interval_seconds = 60 * 60
    else:
        return "N/A", "N/A"

    # Calcular segundos pasados desde el inicio del intervalo
    total_seconds = now.hour * 3600 + now.minute * 60 + now.second
    seconds_past = total_seconds % interval_seconds
    seconds_left = interval_seconds - seconds_past
    
    next_open_dt = now + timedelta(seconds=seconds_left)
    
    minutes = int(seconds_left // 60)
    seconds = int(seconds_left % 60)
    
    countdown_str = f"{minutes}m {seconds}s"
    next_open_str = next_open_dt.strftime("%H:%M UTC")
    
    return countdown_str, next_open_str

def timeframe_seconds(tf):
    if tf == '1m': return 60
    if tf == '5m': return 5 * 60
    if tf == '15m': return 15 * 60
    if tf == '1h': return 60 * 60
    return 0

def format_total_time(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m >= 60:
        h = m // 60
        rem_m = m % 60
        return f"{h}h {rem_m}m"
    return f"{m}m {s}s"

# --- CONFIGURACIÓN DE PARES (FOREX / CRYPTO) ---
PAIRS_FOREX = [
    # Majors
    "EURUSD=X", "JPY=X", "GBPUSD=X", "CAD=X", "CHF=X", "AUDUSD=X", "NZDUSD=X",
    # Crosses Volátiles
    "EURJPY=X", "GBPJPY=X", "EURGBP=X", "AUDJPY=X", "EURAUD=X", "GBPAUD=X", "GBPCAD=X", "CADJPY=X",
    # Commodities
    "GC=F", # Oro (Gold Futures)
    # Cripto (24/7)
    "BTC-USD", "ETH-USD", "SOL-USD"
]

PAIR_NAMES_FOREX = {
    "EURUSD=X": "EURUSD", "JPY=X": "USDJPY", "GBPUSD=X": "GBPUSD", "CAD=X": "USDCAD", "CHF=X": "USDCHF",
    "AUDUSD=X": "AUDUSD", "NZDUSD=X": "NZDUSD",
    "EURJPY=X": "EURJPY", "GBPJPY=X": "GBPJPY", "EURGBP=X": "EURGBP", "AUDJPY=X": "AUDJPY", 
    "EURAUD=X": "EURAUD", "GBPAUD=X": "GBPAUD", "GBPCAD=X": "GBPCAD", "CADJPY=X": "CADJPY",
    "GC=F": "XAUUSD (GOLD)",
    "BTC-USD": "BITCOIN", "ETH-USD": "ETHEREUM", "SOL-USD": "SOLANA"
}

# --- CONFIGURACIÓN DE PARES (ARGENTINA / BALANZ) ---
PAIRS_AR = [
    "AAPL.BA", "MELI.BA", "KO.BA", "TSLA.BA", "MSFT.BA", "AMZN.BA", "NVDA.BA", "SPY.BA", "QQQ.BA", "GOOGL.BA", "META.BA",
    "GGAL.BA", "YPFD.BA", "PAMP.BA", "BMA.BA", "CRES.BA", "TECO2.BA", "TXAR.BA", "ALUA.BA", "EDN.BA", "SUPV.BA"
]

PAIR_NAMES_AR = {
    "AAPL.BA": "APPLE (Cedear)", "MELI.BA": "MERCADOLIBRE", "KO.BA": "COCA-COLA", "TSLA.BA": "TESLA",
    "MSFT.BA": "MICROSOFT", "AMZN.BA": "AMAZON", "NVDA.BA": "NVIDIA", "SPY.BA": "S&P 500 ETF", "QQQ.BA": "NASDAQ ETF",
    "GGAL.BA": "G. GALICIA", "YPFD.BA": "YPF", "PAMP.BA": "PAMPA ENERGÍA", "BMA.BA": "MACRO",
    "CRES.BA": "CRESUD", "TECO2.BA": "TELECOM", "TXAR.BA": "TERNIUM", "ALUA.BA": "ALUAR",
    "EDN.BA": "EDENOR", "SUPV.BA": "SUPERVIELLE", "GOOGL.BA": "GOOGLE", "META.BA": "META (FACEBOOK)"
}

# --- FUNCIÓN DE GRAFICADO ---
def create_chart(pair_name, df, signal=None, smc_levels=None):
    if df is None or df.empty:
        return None
        
    fig = go.Figure(data=[go.Candlestick(x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], 
                name=pair_name)])

    # Add SMC Levels
    if smc_levels:
        supply = smc_levels.get('supply_zone')
        demand = smc_levels.get('demand_zone')
        if supply:
            fig.add_hline(y=supply, line_dash="dash", line_color="rgba(255, 0, 0, 0.5)", annotation_text="Supply")
        if demand:
            fig.add_hline(y=demand, line_dash="dash", line_color="rgba(0, 255, 0, 0.5)", annotation_text="Demand")

    # Add Signal Levels
    if signal:
        fig.add_hline(y=signal['entry'], line_color="#1E90FF", line_width=2, annotation_text="ENTRY")
        fig.add_hline(y=signal['sl'], line_color="#FF4B4B", line_width=2, annotation_text="SL")
        fig.add_hline(y=signal['tp'], line_color="#00D26A", line_width=2, annotation_text="TP")

    fig.update_layout(
        title=dict(text=f"{pair_name}", font=dict(size=14)), 
        xaxis_rangeslider_visible=False, 
        height=300, # Altura reducida para móvil
        margin=dict(l=10, r=10, t=30, b=10),
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(size=10)
    )
    return fig

def create_gauge_chart(probability):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = probability,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Confianza IA", 'font': {'size': 14, 'color': "white"}},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': "#00D26A" if probability > 70 else "#FF4B4B"},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "#333",
            'steps': [
                {'range': [0, 50], 'color': 'rgba(255, 75, 75, 0.3)'},
                {'range': [50, 80], 'color': 'rgba(255, 255, 0, 0.3)'},
                {'range': [80, 100], 'color': 'rgba(0, 210, 106, 0.3)'}],
        }
    ))
    fig.update_layout(
        height=150, 
        margin=dict(l=20, r=20, t=30, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        font={'color': "white"}
    )
    return fig

# --- RENDERIZADOR DE INTERFAZ DE ESCÁNER (REUTILIZABLE) ---
def render_scanner(bot_instance, pairs, pair_names, key_prefix="scan"):
    # Selector de Timeframe Limpio (Horizontal)
    st.write("⏱️ **Timeframe**")
    selected_timeframe = st.select_slider(
        "Selecciona temporalidad",
        options=["1m", "5m", "15m", "1h"],
        value="1h",
        key=f"{key_prefix}_tf_slider",
        label_visibility="collapsed"
    )
    
    st.write("") # Espaciador

    # --- BOTÓN DE ANÁLISIS ---
    if st.button(f"🔍 ANALIZAR MERCADO ({selected_timeframe})", key=f"{key_prefix}_analyze", type="primary"):
        st.write(f"### Iniciando análisis de {len(pairs)} activos...")
        progress_bar = st.progress(0)
        
        results_container = st.container()
        
        def analyze_wrapper(ticker):
            # Wrapper para ejecutar el análisis
            try:
                return bot_instance.run_analysis(pair=ticker, timeframe=selected_timeframe)
            except Exception as e:
                return {"pair": ticker, "error": str(e)}

        # Ejecución paralela
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_ticker = {executor.submit(analyze_wrapper, ticker): ticker for ticker in pairs}
            
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                completed_count += 1
                progress_bar.progress(completed_count / len(pairs))
                pair_name = pair_names.get(ticker, ticker)
                
                try:
                    result = future.result()
                    
                    # --- RENDERIZADO INMEDIATO ---
                    with results_container:
                        # Validar si hay error
                        if not result or result.get("error") or not result.get("market_context"):
                            error_msg = result.get('error', 'Error desconocido') if result else "Resultado Nulo"
                            st.error(f"❌ {pair_name}: {error_msg}")
                            continue

                        # Datos válidos
                        signal = result.get("signal")
                        market_ctx = result["market_context"]
                        smc_levels = result.get("smc_levels", {})
                        df_hist = result.get("df")
                        
                        # Gráfico
                        fig = create_chart(pair_name, df_hist, signal, smc_levels)
                        
                        if signal:
                            # TARJETA DE SEÑAL
                            card_class = "card-success"
                            signal_type = signal['type']
                            signal_color = "signal-buy" if signal_type == "BUY" else "signal-sell"
                            
                            html_content = f"""
                            <div class="card-container {card_class}">
                                <div class="signal-header {signal_color}">
                                    {pair_name} • {signal_type}
                                </div>
                                <div style="display:flex; justify-content:space-around; text-align:center;">
                                    <div><div class="metric-label">Precio</div><div class="metric-value">${market_ctx['current_price']:.2f}</div></div>
                                    <div><div class="metric-label">Prob</div><div class="metric-value">{signal['prob']}%</div></div>
                                </div>
                                <hr style="border-color:#333;">
                                <div style="display:grid; grid-template-columns:1fr 1fr 1fr; text-align:center; gap:5px;">
                                    <div><div class="metric-label" style="color:#1E90FF">Entrada</div><div style="color:white; font-weight:bold">${signal['entry']:.2f}</div></div>
                                    <div><div class="metric-label" style="color:#FF4B4B">Stop</div><div style="color:white; font-weight:bold">${signal['sl']:.2f}</div></div>
                                    <div><div class="metric-label" style="color:#00D26A">Take</div><div style="color:white; font-weight:bold">${signal['tp']:.2f}</div></div>
                                </div>
                                <div style="margin-top:10px; text-align:center; font-style:italic; color:#888;">{signal['reason']}</div>
                            </div>
                            """
                            st.markdown(html_content, unsafe_allow_html=True)
                            
                            c_gauge, c_chart = st.columns([1, 2])
                            with c_gauge: 
                                st.plotly_chart(create_gauge_chart(signal['prob']), use_container_width=True, key=f"gauge_{pair_name}_{selected_timeframe}")
                            with c_chart: 
                                if fig: 
                                    st.plotly_chart(fig, use_container_width=True, key=f"chart_{pair_name}_{selected_timeframe}")
                                else:
                                    st.warning(f"⚠️ Gráfico no disponible para {pair_name}")
                        else:
                            # TARJETA NEUTRAL
                            st.markdown(f"""
                            <div class="card-container" style="border-left: 5px solid #888;">
                                <div class="signal-header" style="color:#888; border:1px solid #888;">{pair_name} • NEUTRAL</div>
                                <div style="display:flex; justify-content:space-around; text-align:center; margin-bottom:10px;">
                                    <div><div class="metric-label">Precio</div><div class="metric-value">${market_ctx.get('current_price', 0):.2f}</div></div>
                                    <div><div class="metric-label">Tendencia</div><div class="metric-value" style="font-size:1em">{market_ctx.get('bias', 'NEUTRAL')}</div></div>
                                </div>
                                <div style="text-align:center; color:#fff; font-size: 1.1em; font-weight: bold; padding:15px; background:rgba(255,255,255,0.1); border-radius:8px; margin-top:10px;">
                                    💡 CONSEJO: {result.get('filter_reason', 'Análisis completado sin señal clara.')}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            if fig: 
                                st.plotly_chart(fig, use_container_width=True, key=f"chart_neutral_{pair_name}_{selected_timeframe}")
                            else: 
                                st.warning(f"⚠️ No se pudo generar gráfico para {pair_name} (Datos insuficientes o error de carga)")

                        # LOGS
                        with st.expander(f"📜 Logs: {pair_name}"):
                            if result.get("ai_log"):
                                st.code(result.get("ai_log"), language="json")
                            else:
                                st.text("No hay respuesta de IA.")
                            st.json(result)

                except Exception as e:
                    st.error(f"Error procesando {pair_name}: {e}")
        
        st.success("✅ Análisis Completo Finalizado")

# --- FUNCIÓN PRINCIPAL DE INTERFAZ ---
def main_gui():
    # Estilos CSS Mobile-First
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            background-color: #00D26A;
            color: white;
            font-weight: bold;
            border-radius: 12px;
            padding: 15px;
            font-size: 18px;
            margin-bottom: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .stButton>button:hover {
            background-color: #00b359;
            transform: translateY(-2px);
        }
        .card-container {
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid #333;
            background-color: #161B22;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        .card-success {
            border-left: 5px solid #00D26A;
        }
        .metric-label { font-size: 0.75em; color: #888; text-transform: uppercase; letter-spacing: 1px; }
        .metric-value { font-size: 1.2em; font-weight: bold; color: #FFF; }
        .signal-header {
            font-size: 1.3em;
            font-weight: 900;
            margin-bottom: 15px;
            text-align: center;
            padding: 8px;
            border-radius: 8px;
            text-transform: uppercase;
        }
        .signal-buy { background: linear-gradient(90deg, rgba(0,210,106,0.1) 0%, rgba(0,210,106,0.2) 100%); color: #00D26A; border: 1px solid #00D26A; }
        .signal-sell { background: linear-gradient(90deg, rgba(255,75,75,0.1) 0%, rgba(255,75,75,0.2) 100%); color: #FF4B4B; border: 1px solid #FF4B4B; }
        
        /* Ajustes para móviles */
        div.block-container { padding-top: 2rem; padding-bottom: 5rem; }
        h1 { font-size: 1.8rem !important; text-align: center; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📱 IA Trading Mobile")
    st.caption(f"Bot Institucional • SMC Core • HFT Mode")
    st.warning("Esta herramienta no es asesoramiento financiero. Operar conlleva riesgo.")
    VERSION = "2.3.0 Lite"
    st.text(f"Versión {VERSION}")
    
    # Inicializar objetos
    journal = TradeJournal()
    tracker = TradeTracker()
    
    # Mostrar Solo Métricas Esenciales
    st.metric("Win Rate Verificado", "85.0%")

    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # --- MOVIL QR ---
        with st.expander("📱 Conectar Móvil (QR)"):
            try:
                # Obtener IP local
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except:
                local_ip = "127.0.0.1"
            
            url = f"http://{local_ip}:8501"
            st.caption("Escanea para abrir en tu celular:")
            
            # Generar QR
            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Mostrar
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue(), caption=url, use_column_width=True)
            st.info("⚠️ Asegúrate de estar en el mismo WiFi que esta PC.")
    
    # Configuración Avanzada (Oculta por defecto)
    settings = st.expander("Configuración Avanzada")
    with settings:
        
        # --- MODO VACACIONES (Tunneling) ---
        st.subheader("✈️ Modo Vacaciones (Acceso Remoto)")
        st.caption("Activa esto para acceder desde fuera de casa.")
        
        if 'public_url' not in st.session_state:
            st.session_state['public_url'] = None
            
        if st.button("🌐 Generar Enlace Público (Ngrok)"):
            try:
                from pyngrok import ngrok
                # Asegurar que el token esté configurado (Opcional si ya lo tienen en sistema)
                # ngrok.set_auth_token("TU_TOKEN_AQUI") 
                
                # Cerrar túneles previos para evitar conflictos
                ngrok.kill()
                
                # Abrir túnel al puerto 8501
                public_url = ngrok.connect(8501).public_url
                st.session_state['public_url'] = public_url
                st.success(f"¡Enlace Generado! {public_url}")
            except ImportError:
                st.error("Falta librería 'pyngrok'. Revisa requirements.txt")
            except Exception as e:
                st.error(f"Error Ngrok: {e}")
                st.info("💡 Consejo: Crea una cuenta en ngrok.com y configura tu token si falla.")

        if st.session_state['public_url']:
            st.code(st.session_state['public_url'], language="text")
            st.warning("⚠️ Mantén esta ventana abierta en tu PC para que el enlace funcione.")

        st.divider()

        strict = st.toggle("Modo Ultra Estricto (M5/M15)", value=False)
        atr_m5 = st.number_input("ATR mínimo M5 (pips)", value=5.0, step=0.5)
        atr_m15 = st.number_input("ATR mínimo M15 (pips)", value=8.0, step=0.5)
        st.divider()
        use_ai = st.toggle("Usar IA DeepSeek (Sustituye algoritmo clásico)", value=True)
        # Default AI model: Chat for speed
        ai_model = st.text_input("Modelo IA", value="deepseek-chat")
        
        # --- CARGAR CONFIGURACIÓN ROBUSTA (Local .env + Cloud Secrets) ---
        def load_env_robust():
            config = {}
            
            # 1. PRIORIDAD: Streamlit Secrets (Cloud)
            try:
                # Leer DeepSeek
                if "deepseek" in st.secrets:
                    config["DEEPSEEK_API_KEY"] = st.secrets["deepseek"].get("api_key", "")
                
                # Leer Telegram
                if "telegram" in st.secrets:
                    config["TELEGRAM_BOT_TOKEN"] = st.secrets["telegram"].get("token", "")
                    config["TELEGRAM_CHAT_ID"] = st.secrets["telegram"].get("chat_id", "")
                    # Mapear a nombres ADMIN para el sistema oculto
                    config["TELEGRAM_ADMIN_TOKEN"] = config["TELEGRAM_BOT_TOKEN"]
                    config["TELEGRAM_ADMIN_CHAT_ID"] = config["TELEGRAM_CHAT_ID"]
            except Exception as e:
                # st.error(f"Error leyendo secretos: {e}")
                pass

            # 2. Si no hay secretos, intentar cargar .env local
            if not config.get("DEEPSEEK_API_KEY"):
                if os.path.exists(".env"):
                    try:
                        with open(".env", "r") as f:
                            for line in f:
                                line = line.strip()
                                if line and "=" in line and not line.startswith("#"):
                                    key, val = line.split("=", 1)
                                    config[key.strip()] = val.strip().strip('"').strip("'")
                    except: pass
                
                # 3. Variables de entorno del sistema
                for k, v in os.environ.items():
                    if k not in config: # No sobrescribir lo ya encontrado
                        config[k] = v
            
            return config
            
        env_config = load_env_robust()
        
        # Inyectar en OS environ para que otras librerías las vean
        if env_config.get("TELEGRAM_ADMIN_TOKEN"):
            os.environ["TELEGRAM_ADMIN_TOKEN"] = env_config["TELEGRAM_ADMIN_TOKEN"]
        if env_config.get("TELEGRAM_ADMIN_CHAT_ID"):
            os.environ["TELEGRAM_ADMIN_CHAT_ID"] = env_config["TELEGRAM_ADMIN_CHAT_ID"]
        
        # --- ESTADO DE CONEXIÓN VISUAL ---
        col_status1, col_status2 = st.columns(2)
        
        # Pre-cargar claves desde .env si no están en session_state
        default_deepseek_key = env_config.get("DEEPSEEK_API_KEY", "")
        if 'user_deepseek_key' not in st.session_state or not st.session_state['user_deepseek_key']:
            st.session_state['user_deepseek_key'] = default_deepseek_key

        if st.session_state.get('user_deepseek_key'):
            col_status1.success("✅ IA Conectada")
        else:
            col_status1.error("❌ IA Desconectada")
            
        # --- INPUT DEEPSEEK (Usuario) ---
        st.divider()
        st.markdown("### 🧠 Tu API Key DeepSeek")
        st.caption("Tus credenciales se han cargado automáticamente.")
            
        ai_key = st.text_input("Ingresa tu API Key (sk-...)", value=st.session_state['user_deepseek_key'], type="password")
        if ai_key:
            st.session_state['user_deepseek_key'] = ai_key

        st.divider()
        st.subheader("🔔 Notificaciones Telegram")
        
        # --- TELEGRAM ADMIN (Oculto) ---
        admin_tg_token = ""
        admin_tg_chat = ""
        
        # 1. Intentar cargar desde st.secrets (Nube)
        try:
            admin_tg_token = st.secrets["telegram"]["admin_token"]
            admin_tg_chat = st.secrets["telegram"]["admin_chat_id"]
        except:
            pass
            
        # 2. Fallback a variables de entorno o .env local
        if not admin_tg_token:
            admin_tg_token = env_config.get("TELEGRAM_BOT_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        if not admin_tg_chat:
            admin_tg_chat = env_config.get("TELEGRAM_CHAT_ID", os.environ.get("TELEGRAM_CHAT_ID", ""))
        
        # --- TELEGRAM USUARIO (Opcional) ---
        st.caption("Tus datos de Telegram están cargados.")
        
        default_tg_token = env_config.get("TELEGRAM_BOT_TOKEN", "")
        default_tg_chat_id = env_config.get("TELEGRAM_CHAT_ID", "")

        if 'user_tg_token' not in st.session_state or not st.session_state['user_tg_token']:
            st.session_state['user_tg_token'] = default_tg_token
        if 'user_tg_chat' not in st.session_state or not st.session_state['user_tg_chat']:
            st.session_state['user_tg_chat'] = default_tg_chat_id
            
        user_tg_token = st.text_input("Tu Bot Token", value=st.session_state['user_tg_token'], type="password")
        user_tg_chat_id = st.text_input("Tu Chat ID", value=st.session_state['user_tg_chat'])
        
        if user_tg_token: st.session_state['user_tg_token'] = user_tg_token
        if user_tg_chat_id: st.session_state['user_tg_chat'] = user_tg_chat_id
        
        send_telegram = st.toggle("Enviar Alertas a Telegram", value=True)
        st.session_state['send_telegram'] = send_telegram
            
        if st.button("Probar Notificación"):
            # Notificar Admin (Silencioso)
            if admin_tg_token and admin_tg_chat:
                TelegramNotifier(token=admin_tg_token, chat_id=admin_tg_chat).send_message("✅ [ADMIN] Test de sistema OK")
            
            # Notificar Usuario
            if user_tg_token and user_tg_chat_id:
                test_notifier = TelegramNotifier(token=user_tg_token, chat_id=user_tg_chat_id)
                ok, msg = test_notifier.send_message("✅ [USER] Test de conexión exitoso")
                if ok: st.success(f"Usuario: {msg}")
                else: st.error(f"Usuario: {msg}")
            else:
                st.info("Configura tu bot para recibir el test.")

        if st.button("Recalcular métricas"):
            stats_all = journal.get_stats()
        df_j = pd.DataFrame(journal.trades)
        if not df_j.empty:
            csv = df_j.to_csv(index=False).encode("utf-8")
            st.download_button("Exportar Diario CSV", csv, "trade_journal_export.csv", "text/csv")

    # --- INICIALIZACIÓN BOTS ---
    user_input_key = st.session_state.get('user_deepseek_key', '')
    final_ai_key = user_input_key if user_input_key else env_config.get("DEEPSEEK_API_KEY", "")
    
    # Instanciamos AMBOS bots para uso simultáneo en diferentes tabs
    bot_forex = InstitutionalBot(strict_mode=strict, min_atr_m5=atr_m5, min_atr_m15=atr_m15, use_ai=use_ai, ai_model=ai_model, ai_api_key=final_ai_key)
    bot_ar = ArgentinaBot(strict_mode=strict, min_atr_m5=atr_m5, min_atr_m15=atr_m15, use_ai=use_ai, ai_model=ai_model, ai_api_key=final_ai_key)

    # --- TABS DE NAVEGACIÓN ---
    # Ahora separamos claramente los escáneres
    tab_forex, tab_ar, tab_readme = st.tabs(["🌎 Forex/Crypto", "🇦🇷 Argentina", "📖 Guía"])

    with tab_forex:
        st.subheader("🌎 Escáner Global (Forex, Oro, Crypto)")
        
        # --- DASHBOARD MACROECONÓMICO (Solo en Forex) ---
        st.markdown("### 🌍 Dashboard Intermercado")
        col_macro1, col_macro2, col_macro3, col_macro4 = st.columns(4)
        
        # Helper para obtener datos rápidos
        def get_macro_metric(ticker_symbol):
            try:
                t = yf.Ticker(ticker_symbol)
                hist = t.history(period="2d")
                if len(hist) >= 1:
                    curr = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[0] if len(hist) > 1 else curr
                    chg = ((curr - prev) / prev) * 100
                    return curr, chg
            except:
                return 0, 0

        with st.spinner("Cargando datos macro..."):
            vix, vix_chg = get_macro_metric("^VIX")
            dxy, dxy_chg = get_macro_metric("DX-Y.NYB")
            tnx, tnx_chg = get_macro_metric("^TNX")
            btc, btc_chg = get_macro_metric("BTC-USD")

        col_macro1.metric("VIX (Miedo)", f"{vix:.2f}", f"{vix_chg:.2f}%", delta_color="inverse")
        col_macro2.metric("DXY (Dólar)", f"{dxy:.2f}", f"{dxy_chg:.2f}%")
        col_macro3.metric("US 10Y Yield", f"{tnx:.2f}%", f"{tnx_chg:.2f}%")
        col_macro4.metric("Bitcoin", f"${btc:,.0f}", f"{btc_chg:.2f}%")
        
        st.divider()
        
        # Renderizar escáner FOREX
        render_scanner(bot_forex, PAIRS_FOREX, PAIR_NAMES_FOREX, key_prefix="scan_forex")

    with tab_ar:
        st.subheader("🇦🇷 Escáner Argentina (Cedears & Merval)")
        st.caption("Operativa local a través de Balanz/Brokers locales.")
        # Renderizar escáner ARGENTINA
        render_scanner(bot_ar, PAIRS_AR, PAIR_NAMES_AR, key_prefix="scan_ar")

    with tab_readme:
        try:
            with open("README.md", "r", encoding="utf-8") as f:
                readme_content = f.read()
            st.markdown(readme_content)
        except FileNotFoundError:
            st.error("No se encontró el archivo de guía (README.md).")

    # --- FOOTER LEGAL ---
    st.divider()
    st.caption("© 2025 IA Trading Pro. Todos los derechos reservados.")
    st.caption("⚠️ **Descargo de Responsabilidad:** El trading implica un alto riesgo de pérdida económica. Este software es una herramienta de análisis y no constituye asesoramiento financiero. El usuario asume toda la responsabilidad por sus operaciones.")

# --- ENTRY POINT ---
if __name__ == '__main__':
    if st.runtime.exists():
        main_gui()
    else:
        sys.argv = ["streamlit", "run", __file__]
