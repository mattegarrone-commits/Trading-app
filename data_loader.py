import yfinance as yf
import pandas as pd
from datetime import datetime, time
import pytz

def load_data(pair, timeframe, limit=1000):
    """
    Descarga datos de Yahoo Finance.
    Timeframes soportados por yfinance: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    """
    try:
        print(f"Descargando datos para {pair} ({timeframe})...")
        
        # Mapeo de timeframes para yfinance
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", 
            "1h": "1h", "4h": "1h", "1d": "1d"
        }
        
        yf_interval = interval_map.get(timeframe, "1h")
        period = "7d" if timeframe in ["1m", "5m"] else "60d"
        if timeframe == "1d": period = "1y"

        # USAR SESSION: yfinance actual prefiere manejar su propia sesión o requiere curl_cffi.
        # Eliminamos la sesión manual de requests que causa conflictos.
        
        # FORZAR descarga sin hilos y con progresa desactivado para evitar errores de NoneType en UI
        ticker = yf.Ticker(pair)
        df = ticker.history(period=period, interval=yf_interval)

        if df.empty:
            # Intento secundario con yf.download directo si Ticker() falla
            df = yf.download(pair, period=period, interval=yf_interval, progress=False, threads=False)

        if df is None or df.empty:
            print(f"[ERROR] No se pudieron cargar datos para {pair} ({timeframe})")
            return None

        # Reset index para tener 'Date' como columna
        df.reset_index(inplace=True)

        # Normalizar nombres de columnas (yfinance a veces devuelve 'Datetime' o 'Date')
        if 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'Date'}, inplace=True)
        elif 'Date' not in df.columns:
            # Si el índice es la fecha pero no tiene nombre
            df['Date'] = df.index

        # Asegurar que las columnas numéricas sean float
        cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in cols:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        # Eliminar filas con NaN
        df.dropna(inplace=True)

        # Añadir información de sesión (Londres/NY)
        df = add_session_info(df)

        return df

    except Exception as e:
        print(f"Excepción al descargar datos de {pair}: {e}")
        return None

def add_session_info(df):
    """
    Añade columnas booleanas para sesiones de Londres y Nueva York.
    """
    if df is None or df.empty:
        return df

    try:
        # Asegurar que el índice es datetime y tiene zona horaria
        if df.index.name != 'Date' and 'Date' in df.columns:
             df.set_index('Date', inplace=True, drop=False)
        
        if df.index.tz is None:
            # Asumimos que yfinance devuelve UTC
            df.index = df.index.tz_localize('UTC')
        else:
            df.index = df.index.tz_convert('UTC')

        # Definir horarios (simplificado)
        # Londres (aprox 7am/8am UTC start)
        df['is_london'] = (df.index.hour >= 8) & (df.index.hour < 17)
        
        # NY (aprox 13pm/14pm UTC start)
        df['is_ny'] = (df.index.hour >= 13) & (df.index.hour < 22)
        
        # Killzones (Solapamiento de alta volatilidad Londres/NY: 13:00 - 17:00 UTC)
        df['is_killzone'] = df['is_london'] & df['is_ny']
    except Exception as e:
        print(f"Error calculating session info: {e}")
        # Fill with False to avoid KeyErrors downstream
        df['is_london'] = False
        df['is_ny'] = False
        df['is_killzone'] = False
    
    return df
