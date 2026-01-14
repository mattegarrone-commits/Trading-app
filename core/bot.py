try:
    from data_loader import load_data
except ModuleNotFoundError:
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from data_loader import load_data
from analysis.smc import SMCAnalyzer
from core.risk import RiskManager
from core.journal import TradeJournal
import pandas as pd
import numpy as np
import json
from urllib.request import Request, urlopen
from datetime import datetime
import yfinance as yf

class InstitutionalBot:
    def __init__(self, strict_mode=False, min_atr_m5=5.0, min_atr_m15=8.0, use_ai=False, ai_model="deepseek-reasoner", ai_api_key=None, ai_provider="deepseek"):
        self.smc = SMCAnalyzer()
        self.risk = RiskManager()
        self.journal = TradeJournal()
        self.htf_timeframe = "1h"
        self.strict_mode = strict_mode
        self.min_atr_m5 = min_atr_m5
        self.min_atr_m15 = min_atr_m15
        self.use_ai = use_ai
        self.ai_model = ai_model
        self.ai_api_key = ai_api_key
        self.ai_provider = ai_provider

    def run_analysis(self, pair="EURUSD=X", timeframe="1h", output_file=None):
        """
        Ejecuta el análisis. Si output_file se proporciona, escribe el resultado en ese archivo.
        Devuelve un diccionario con los datos estructurados para su uso en interfaces (Streamlit).
        Timeframe puede ser: "1m", "5m", "15m", "1h".
        """
        result_data = {
            "pair": pair,
            "timeframe": timeframe,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "market_context": {},
            "smc_levels": {},
            "signal": None,
            "df": None
        }

        output_lines = []
        
        def log(msg):
            print(msg)
            output_lines.append(msg)

        log(f"============================================================")
        log(f"   REPORTE INSTITUCIONAL ({timeframe}): {pair}")
        log(f"   FECHA: {result_data['timestamp']}")
        log(f"============================================================")
        
        # 1. Cargar Datos
        df = load_data(pair, timeframe)
        if df is None or df.empty:
            msg = f"[ERROR] No se pudieron cargar datos para {pair} ({timeframe})"
            log(msg)
            result_data["error"] = "Fallo descarga de datos (Yahoo Finance)"
            self._write_output(output_file, output_lines)
            return result_data

        # 2. Análisis Técnico SMC
        df = self.smc.analyze(df)
        
        # Guardar DF para gráficos (últimas 200 velas para rendimiento)
        result_data["df"] = df.tail(200)

        
        # 3. Contexto de Mercado Detallado
        last_row = df.iloc[-1]
        current_price = last_row['Close']
        bias = self.smc.get_market_bias(df)
        htf_bias = self._get_htf_bias(pair)
        
        # --- MATRIZ DE TENDENCIAS (NUEVO) ---
        # Analizar H1 y D1 para confluencia
        trend_matrix = {"M15": bias, "H1": htf_bias, "D1": "NEUTRAL"}
        try:
            df_d1 = load_data(pair, timeframe="1d")
            if not df_d1.empty:
                df_d1 = self.smc.analyze(df_d1)
                trend_matrix["D1"] = self.smc.get_market_bias(df_d1)
        except:
            pass # Fallback silencioso si falla D1
        
        result_data["trend_matrix"] = trend_matrix

        # Obtener niveles clave
        last_pivot_high = last_row.get('last_pivot_high', 0)
        last_pivot_low = last_row.get('last_pivot_low', 0)
        
        # Estado de Sesión
        session_status = []
        if last_row.get('is_london'): session_status.append("LONDRES")
        if last_row.get('is_ny'): session_status.append("NUEVA YORK")
        if not session_status: session_status.append("ASIA / CIERRE (Baja Liquidez)")
        
        result_data["market_context"] = {
            "current_price": current_price,
            "bias": bias,
            "htf_bias": htf_bias,
            "session": ' + '.join(session_status)
        }

        log(f"\n[1] CONTEXTO DE MERCADO")
        log(f"    Precio Actual:       {current_price:.5f}")
        log(f"    Tendencia Dominante: {bias}")
        log(f"    Tendencia HTF(1h):   {htf_bias}")
        log(f"    Sesión Activa:       {' + '.join(session_status)}")
        
        log(f"\n[2] NIVELES ESTRUCTURALES (SMC)")
        log(f"    Último High Validado (Oferta):   {last_pivot_high:.5f}")
        log(f"    Último Low Validado (Demanda):   {last_pivot_low:.5f}")
        
        # Calcular distancias a niveles clave
        dist_high = abs(current_price - last_pivot_high) * 10000
        dist_low = abs(current_price - last_pivot_low) * 10000
        
        result_data["smc_levels"] = {
            "supply_zone": last_pivot_high,
            "demand_zone": last_pivot_low,
            "dist_supply_pips": dist_high,
            "dist_demand_pips": dist_low
        }

        log(f"    Distancia a Oferta:  {dist_high:.1f} pips")
        log(f"    Distancia a Demanda: {dist_low:.1f} pips")

        # 4. Búsqueda de Setup
        if self.use_ai:
            log(f"\n[3] ANÁLISIS DE OPORTUNIDAD (MODO IA: {self.ai_model})")
            pip_f = self._pip_factor(pair)
            atr_val = float(last_row.get('ATR', 0))
            setup, filter_reason = self._find_setup_ai(df, pair, timeframe, bias, htf_bias, atr_val, pip_f)
        else:
            log(f"\n[3] ANÁLISIS DE OPORTUNIDAD (MODO CLÁSICO)")
            setup, filter_reason = self._find_setup(df, pair, timeframe, bias, htf_bias)

        if setup:
            signal_data = self._execute_signal(setup, pair, timeframe, log)
            if signal_data:
                result_data["signal"] = signal_data
            else:
                filter_reason = "risk_filter"
        else:
            log("    >> NO HAY OPERACIÓN CON VENTAJA MATEMÁTICA")
            log("    Razón: No se cumplen condiciones de confluencia (Estructura + Zona + Sesión).")
            if not (last_row.get('is_london') or last_row.get('is_ny')):
                log("    Nota: Mercado fuera de horario institucional operativo.")
            if filter_reason:
                pip_f = self._pip_factor(pair)
                atr_val = float(last_row.get('ATR', 0))
                atr_pips = atr_val * pip_f
                min_atr = self.min_atr_m5 if timeframe == "5m" else self.min_atr_m15 if timeframe == "15m" else 0.0
                reason_map = {
                    "atr_low": f"    Filtro ATR: volatilidad baja ({atr_pips:.1f} < {min_atr:.1f} pips)",
                    "htf_mismatch": "    Filtro HTF: desalineación con sesgo 1h",
                    "session_off": "    Filtro Sesión: fuera de Londres/NY o killzone",
                    "rsi_extreme": "    Filtro RSI: extremo sin ventaja (sobrecompra/sobreventa)",
                    "no_setup": "    Filtro Setup: sin proximidad válida a zonas SMC",
                }
                log(reason_map.get(filter_reason, f"    Filtro: {filter_reason}"))

        if self.use_ai:
            try:
                result_data["ai_advice"] = self._ai_advise(result_data, df)
            except Exception:
                result_data["ai_advice"] = {"summary": "IA no disponible, usando heurística local.", "confidence": 60, "model": self.ai_model}
        log(f"\n============================================================")
        self._write_output(output_file, output_lines)
        
        result_data["filter_reason"] = filter_reason
        return result_data


    def _write_output(self, filepath, lines):
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
            except Exception as e:
                print(f"Error escribiendo reporte en {filepath}: {e}")

    def _pip_factor(self, pair):
        if "JPY" in pair:
            return 100.0
        return 10000.0

    def _get_htf_bias(self, pair):
        htf_df = load_data(pair, timeframe=self.htf_timeframe)
        if htf_df is None or htf_df.empty:
            return "NEUTRAL"
        htf_df = self.smc.analyze(htf_df)
        return self.smc.get_market_bias(htf_df)

    def _call_ai_api(self, system_prompt, user_prompt, response_format_json=True):
        import json
        from urllib.request import Request, urlopen
        
        # Select Provider
        if self.ai_provider == "claude":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.ai_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            body = {
                "model": self.ai_model, 
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            }
        else: # DeepSeek (default)
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.ai_api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": self.ai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"} if response_format_json else None
            }

        try:
            req = Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
            res = urlopen(req, timeout=60) # Increased timeout to 60s for stability
            data = json.loads(res.read().decode("utf-8"))
            
            if self.ai_provider == "claude":
                # Claude Response: { "content": [ {"text": "..."} ] }
                content = data.get("content", [{}])[0].get("text")
            else:
                # OpenAI/DeepSeek Response
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
            
            return content
        except Exception as e:
            print(f"Error calling AI API ({self.ai_provider}): {e}")
            raise e

    def _find_setup_ai(self, df, pair, timeframe, bias, htf_bias, atr, pip_f):
        return self._find_setup_deepseek(df, pair, timeframe, bias, htf_bias, atr, pip_f)

    def _find_setup(self, df, pair, timeframe, bias, htf_bias):
        last_row = df.iloc[-1]
        is_in_session = last_row.get('is_london') or last_row.get('is_ny')
        in_kz = last_row.get('is_killzone')
        atr = float(last_row.get('ATR', 0))
        pip_f = self._pip_factor(pair)
        atr_pips = atr * pip_f
        min_atr = self.min_atr_m5 if timeframe == "5m" else self.min_atr_m15 if timeframe == "15m" else 0.0

        # Lógica algorítmica clásica
        if min_atr > 0 and atr_pips < min_atr:
            return None, "atr_low"
        setup = None

        if bias == "BULLISH":
            last_pivot_low = df['last_pivot_low'].iloc[-1]
            if not pd.isna(last_pivot_low):
                dist_pips = (last_row['Close'] - last_pivot_low) * pip_f
                if 0 < dist_pips < 30: 
                    sl = last_pivot_low - (atr * 1.2)
                    tp = last_row['Close'] + (atr * 3.0)
                    setup = {
                        'type': 'BUY',
                        'entry': last_row['Close'],
                        'sl': sl,
                        'tp': tp,
                        'prob': 88 if in_kz else 82 if is_in_session else 72,
                        'reason': "SMC: Retesteo de Zona de Demanda (Order Block)"
                    }

        elif bias == "BEARISH":
            last_pivot_high = df['last_pivot_high'].iloc[-1]
            if not pd.isna(last_pivot_high):
                dist_pips = (last_pivot_high - last_row['Close']) * pip_f
                if 0 < dist_pips < 30:
                    sl = last_pivot_high + (atr * 1.2)
                    tp = last_row['Close'] - (atr * 3.0)
                    setup = {
                        'type': 'SELL',
                        'entry': last_row['Close'],
                        'sl': sl,
                        'tp': tp,
                        'prob': 88 if in_kz else 82 if is_in_session else 72,
                        'reason': "SMC: Retesteo de Zona de Oferta (Order Block)"
                    }

        if setup: 
            if htf_bias != bias:
                setup['prob'] = max(60, int(setup['prob'] * 0.8))
            if self.strict_mode and timeframe in ["5m", "15m"]:
                if htf_bias != bias:
                    return None, "htf_mismatch"
                if not (is_in_session or in_kz):
                    return None, "session_off"
            return setup, None

        if bias == "BULLISH" and last_row.get('fvg_bullish'):
            fvg_bottom = last_row['fvg_bottom']
            sl = fvg_bottom - (atr * 1.0)
            tp = last_row['Close'] + (atr * 2.5)
            setup = {
                'type': 'BUY',
                'entry': last_row['Close'],
                'sl': sl,
                'tp': tp,
                'prob': 84 if in_kz else 78 if is_in_session else 68,
                'reason': "FVG: Rebalanceo de Imbalance Alcista"
            }
        
        elif bias == "BEARISH" and last_row.get('fvg_bearish'):
            fvg_top = last_row['fvg_top']
            sl = fvg_top + (atr * 1.0)
            tp = last_row['Close'] - (atr * 2.5)
            setup = {
                'type': 'SELL',
                'entry': last_row['Close'],
                'sl': sl,
                'tp': tp,
                'prob': 84 if in_kz else 78 if is_in_session else 68,
                'reason': "FVG: Rebalanceo de Imbalance Bajista"
            }

        ema_50 = last_row.get('EMA_50')
        if ema_50:
            dist_ema = abs(last_row['Close'] - ema_50) * pip_f
            
            if dist_ema < 15:
                if bias == "BULLISH" and last_row['Close'] > ema_50:
                    sl = ema_50 - (atr * 1.2)
                    tp = last_row['Close'] + (atr * 2.4)
                    setup = {
                        'type': 'BUY',
                        'entry': last_row['Close'],
                        'sl': sl,
                        'tp': tp,
                        'prob': 80 if in_kz else 74 if is_in_session else 64,
                        'reason': "Trend: Rebote Dinámico en EMA 50"
                    }
                elif bias == "BEARISH" and last_row['Close'] < ema_50:
                    sl = ema_50 + (atr * 1.2)
                    tp = last_row['Close'] - (atr * 2.4)
                    setup = {
                        'type': 'SELL',
                        'entry': last_row['Close'],
                        'sl': sl,
                        'tp': tp,
                        'prob': 80 if in_kz else 74 if is_in_session else 64,
                        'reason': "Trend: Rechazo Dinámico en EMA 50"
                    }

        if setup:
            rsi = last_row.get('RSI', 50)
            if setup['type'] == 'BUY' and rsi > 70: return None, "rsi_extreme"
            if setup['type'] == 'SELL' and rsi < 30: return None, "rsi_extreme"
            if htf_bias != bias:
                setup['prob'] = max(60, int(setup['prob'] * 0.85))
            if self.strict_mode and timeframe in ["5m", "15m"]:
                if htf_bias != bias:
                    return None, "htf_mismatch"
                if not (is_in_session or in_kz):
                    return None, "session_off"

        if not setup and bias == "RANGING":
            rsi = last_row.get('RSI', 50)
            last_pivot_high = df['last_pivot_high'].iloc[-1]
            last_pivot_low = df['last_pivot_low'].iloc[-1]
            
            if not pd.isna(last_pivot_high) and rsi > 50: 
                dist_pips = (last_pivot_high - last_row['Close']) * pip_f
                if 0 < dist_pips < 30:
                    sl = last_pivot_high + (atr * 1.0)
                    tp = last_row['Close'] - (atr * 2.2)
                    setup = {
                        'type': 'SELL',
                        'entry': last_row['Close'],
                        'sl': sl,
                        'tp': tp,
                        'prob': 72, 
                        'reason': "Rango: Rechazo en Resistencia (Scalping)"
                    }
            
            if not setup and not pd.isna(last_pivot_low) and rsi < 50:
                dist_pips = (last_row['Close'] - last_pivot_low) * pip_f
                if 0 < dist_pips < 30:
                    sl = last_pivot_low - (atr * 1.0)
                    tp = last_row['Close'] + (atr * 2.2)
                    setup = {
                        'type': 'BUY',
                        'entry': last_row['Close'],
                        'sl': sl,
                        'tp': tp,
                        'prob': 72,
                        'reason': "Rango: Rebote en Soporte (Scalping)"
                    }

        if setup:
            atr = last_row.get('ATR', None)
            if atr is None or pd.isna(atr) or atr <= 0:
                recent = df.tail(20)
                atr = (recent['High'] - recent['Low']).mean()
            if atr is None or pd.isna(atr) or atr <= 0:
                recent = df.tail(20)
                atr = abs(recent['Close'].diff()).mean()
            if atr is None or pd.isna(atr) or atr <= 0:
                atr = abs(setup['entry'] - setup['sl']) * 0.4
            dist_tp = abs(setup['tp'] - setup['entry'])
            bars_est = dist_tp / max(1e-9, 0.7 * atr)
            duration = int(round(bars_est))
            if duration < 1: duration = 1
            if duration > 5: duration = 5
            setup['duration'] = duration
            return setup, None
        return None, "no_setup"

    def _find_setup_deepseek(self, df, pair, timeframe, bias, htf_bias, atr, pip_f):
        import json
        import re
        from urllib.request import Request, urlopen
        from urllib.error import URLError, HTTPError
        import numpy as np
        
        # Obtener noticias fundamentales
        news_headlines = self._get_fundamental_news(pair)
        
        # Contexto Macro (Placeholder si no hay feed de datos macro)
        macro_context = "Datos macro en tiempo real no disponibles. Inferir sentimiento de las noticias."

        last_rows = df.tail(10).to_dict(orient='records')
        last_row = df.iloc[-1]
        
        # Simplificar datos para el prompt y CONVERTIR NUMPY A PYTHON NATIVO
        def convert_numpy(obj):
            if isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            elif isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        candles_context = []
        for row in last_rows:
            candles_context.append({
                "time": str(row.get('Date', '')),
                "open": convert_numpy(row['Open']),
                "high": convert_numpy(row['High']),
                "low": convert_numpy(row['Low']),
                "close": convert_numpy(row['Close']),
                "rsi": convert_numpy(row.get('RSI', 50)),
                "ema_50": convert_numpy(row.get('EMA_50', 0))
            })

        # Ajustar prompt según Timeframe (Scalping vs Estructural)
        if timeframe in ["1m", "5m", "15m"]:
            mode_instruction = """MODO INTRADAY AGRESIVO / SCALPING:
- Tu prioridad es ENCONTRAR OPORTUNIDADES ACTIVAS.
- Para M1/M5: Busca patrones inmediatos (HFT).
- Para M15: Busca continuaciones de tendencia intradía y rebotes en zonas clave.
- NO seas excesivamente perfeccionista con la estructura macro de H4/D1 si la acción de precio actual es clara.
- Ratio Riesgo/Beneficio: Prioriza tasa de acierto (Winrate). 1:1 o 1:1.5 es aceptable si la probabilidad es alta.
- Si el precio está rebotando en una EMA o nivel clave, ES SEÑAL DE ENTRADA.
- IGNORA filtros estrictos de sesión si ves volumen/volatilidad suficiente."""
        else:
            mode_instruction = """MODO ESTRUCTURAL (SWING/DAY):
- Prioriza alineación total con HTF Bias.
- Busca confirmaciones claras en zonas de oferta/demanda.
- RR mínimo: 1:2."""

        system_prompt = f"""Sos un FX trader profesional institucional.
Analizá {pair} en el timeframe {timeframe} con foco exclusivo en ejecución.

{mode_instruction}

Tu tarea es generar una SEÑAL DE TRADING precisa.
Para que el sistema procese tu orden, DEBES responder EXCLUSIVAMENTE en formato JSON con la siguiente estructura exacta.
Mantén el estilo directo ("bullets", sin teoría) dentro del campo "reason".

Estructura JSON requerida:
{{
    "action": "BUY" | "SELL" | "WAIT",  // Si no hay setup claro, usa "WAIT"
    "bias": "BULLISH" | "BEARISH" | "RANGE",
    "structure": "Estructura H4 -> M15 (HH/HL o LH/LL)",
    "entry": precio_float,
    "sl": precio_float_invalidacion,
    "tp": precio_float_objetivo,
    "estimated_candles": numero_entero_velas,
    "reason": "Resumen tipo bullets: Bias, Estructura, Zona entrada, Timing recomendado. Nada de teoría.",
    "fundamental_analysis": {{
        "bias": "BULLISH" | "BEARISH" | "NEUTRAL",
        "summary": "Impacto noticias/macro conciso"
    }},
    "confidence": 65-100
}}

Nada de teoría, nada de advertencias, máxima precisión. Si es NO TRADE, action="WAIT"."""

        user_content = {
            "pair": pair,
            "timeframe": timeframe,
            "current_price": convert_numpy(last_row['Close']),
            "atr_pips": convert_numpy(atr * pip_f),
            "bias": bias,
            "htf_bias": htf_bias,
            "session_london": bool(last_row.get('is_london')),
            "session_ny": bool(last_row.get('is_ny')),
            "macro_context": macro_context,
            "news_headlines": news_headlines,
            "last_10_candles": candles_context,
            "smc_levels": {
                "last_pivot_high": convert_numpy(df['last_pivot_high'].iloc[-1]),
                "last_pivot_low": convert_numpy(df['last_pivot_low'].iloc[-1]),
                "fvg_bullish": convert_numpy(last_row.get('fvg_bullish', 0)),
                "fvg_bearish": convert_numpy(last_row.get('fvg_bearish', 0))
            }
        }

        try:
            content = self._call_ai_api(system_prompt, json.dumps(user_content))
            
            if not content:
                return None, "ai_empty_response"
                
            # Limpiar posible markdown ```json ... ```
            clean_content = content.replace("```json", "").replace("```", "").strip()
            
            try:
                signal = json.loads(clean_content)
            except:
                return None, "ai_json_parse_error"
            
            # Normalizar claves y valores
            action = signal.get("action", "").upper().strip()
            
            # --- LIMPIEZA DE BIAS (Fix para evitar textos largos tipo "BULLISH | BEARISH") ---
            raw_bias = str(signal.get("bias", "")).upper()
            if "BULL" in raw_bias and "BEAR" not in raw_bias: signal["bias"] = "BULLISH"
            elif "BEAR" in raw_bias and "BULL" not in raw_bias: signal["bias"] = "BEARISH"
            elif "RANG" in raw_bias: signal["bias"] = "RANGING"
            # Si la IA devolvió "BULLISH | BEARISH" (ambos), forzamos uno o NEUTRAL
            elif "BULL" in raw_bias: signal["bias"] = "BULLISH"
            elif "BEAR" in raw_bias: signal["bias"] = "BEARISH"
            else: signal["bias"] = "NEUTRAL"
            
            if "fundamental_analysis" in signal:
                raw_fund = str(signal["fundamental_analysis"].get("bias", "")).upper()
                if "BULL" in raw_fund: signal["fundamental_analysis"]["bias"] = "BULLISH"
                elif "BEAR" in raw_fund: signal["fundamental_analysis"]["bias"] = "BEARISH"
                else: signal["fundamental_analysis"]["bias"] = "NEUTRAL"
            # -------------------------------------------------------------------

            # Fallback si no hay action
            if not action:
                 return None, f"AI_WAIT: {signal.get('reason', 'Sin decisión clara')}"

            if action == "WAIT":
                return None, f"AI_WAIT: {signal.get('reason')}"
            
            if action in ["BUY", "SELL"]:
                # Validar precios básicos
                entry = signal.get("entry", convert_numpy(last_row['Close']))
                sl = signal.get("sl")
                tp = signal.get("tp")
                
                if not sl or not tp:
                    return None, "ai_invalid_params"

                # Calcular RR implícito para validar
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                if risk == 0: return None, "ai_zero_risk"
                
                # Construir setup compatible con el bot
                setup = {
                    'type': action,
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'prob': int(signal.get('confidence', 70)),
                    'reason': f"AI {self.ai_provider.title()}: {signal.get('reason')}",
                    'duration': int(signal.get('estimated_candles', 5)),
                    'fundamental': signal.get('fundamental_analysis', {'bias': 'NEUTRAL', 'summary': 'No analysis'})
                }
                return setup, None
                
            return None, f"ai_decision_unknown: {action}"

        except Exception as e:
            # Fallback seguro para que el error no sea silencioso en UI
            error_msg = str(e)
            print(f"[ERROR IA] {error_msg}")
            return None, f"ai_error: {error_msg[:50]}..."

    def _execute_signal(self, setup, pair, timeframe, log_func):
        risk_per_share = abs(setup['entry'] - setup['sl'])
        reward_per_share = abs(setup['tp'] - setup['entry'])
        rr_ratio = reward_per_share / risk_per_share if risk_per_share > 0 else 0
        
        valid, msg = self.risk.validate_trade(setup['prob'], rr_ratio)
        
        if not valid:
            log_func(f"    >> Setup descartado por Riesgo: {msg}")
            log_func("    NO HAY OPERACIÓN CON VENTAJA MATEMÁTICA")
            return None

        log_func("\n    >>> ¡OPORTUNIDAD INSTITUCIONAL DETECTADA! <<<")
        log_func(f"    Operación:          {setup['type']}")
        log_func(f"    Par:                {pair}")
        log_func(f"    Entrada exacta:     {setup['entry']:.5f}")
        log_func(f"    Stop Loss:          {setup['sl']:.5f}")
        log_func(f"    Take Profit:        {setup['tp']:.5f}")
        log_func(f"    Ratio Riesgo/Ben:   1:{rr_ratio:.2f}")
        log_func(f"    Probabilidad est.:  {setup['prob']}%")
        log_func(f"    Duración est.:      {setup.get('duration', '?')} velas")
        log_func(f"    Justificación:      {setup['reason']}")
        if 'fundamental' in setup:
             log_func(f"    Fundamental:        {setup['fundamental'].get('bias')} - {setup['fundamental'].get('summary')}")
        
        self.journal.log_trade({**setup, "pair": pair, "timeframe": timeframe})
        
        # Devolver datos estructurados de la señal
        return {
            "type": setup['type'],
            "entry": setup['entry'],
            "sl": setup['sl'],
            "tp": setup['tp'],
            "rr": rr_ratio,
            "prob": setup['prob'],
            "reason": setup['reason'],
            "duration": setup.get('duration', 0),
            "fundamental": setup.get('fundamental')
        }
    
    def _ai_advise(self, result_data, df):
        import json
        
        payload = {
            "pair": result_data.get("pair"),
            "timeframe": result_data.get("timeframe"),
            "market_context": result_data.get("market_context"),
            "smc_levels": result_data.get("smc_levels"),
            "signal": result_data.get("signal"),
            "filter_reason": result_data.get("filter_reason")
        }
        text = f"Par {payload['pair']} {payload['timeframe']}. Sesgo {payload['market_context'].get('bias')} HTF {payload['market_context'].get('htf_bias')} Sesión {payload['market_context'].get('session')}. Distancias Oferta {payload['smc_levels'].get('dist_supply_pips'):.1f} Demanda {payload['smc_levels'].get('dist_demand_pips'):.1f}."
        if payload["signal"]:
            s = payload["signal"]
            text += f" Señal {s['type']} RR 1:{s['rr']:.2f} Prob {s['prob']}%. Tesis {s['reason']}."
        else:
            fr = payload.get("filter_reason") or "sin_setup"
            text += f" Sin señal. Filtro {fr}."
        if not self.ai_api_key:
            return {"summary": "Falta API Key. Configúrala en el menú.", "confidence": 0, "model": "local"}
            
        system_prompt = "Eres un asesor institucional de trading. Analiza contexto y sintetiza consejo breve con recomendaciones accionables y nivel de confianza (0-100). Responde en JSON."
        
        try:
            content = self._call_ai_api(system_prompt, text)
            
            clean_content = content.replace("```json", "").replace("```", "").strip()
            adv = json.loads(clean_content)
            
            return {"summary": adv.get("summary", "Sin consejo"), "confidence": int(adv.get("confidence", 50)), "model": self.ai_model}
            
        except Exception as e:
            return {"summary": f"Error IA Advice: {str(e)}", "confidence": 0, "model": self.ai_model}

    def get_general_market_news(self):
        """Obtiene noticias generales del mercado usando tickers globales."""
        headlines = []
        tickers = ["^DJI", "BTC-USD", "EURUSD=X", "GC=F"] # Dow Jones, Bitcoin, Euro, Gold
        
        try:
            for t_symbol in tickers:
                t = yf.Ticker(t_symbol)
                news = t.news
                if news:
                    for n in news[:2]: # Top 2 per ticker
                        headlines.append({
                            "title": n.get('title'),
                            "link": n.get('link'),
                            "publisher": n.get('publisher'),
                            "time": n.get('providerPublishTime', 0),
                            "ticker": t_symbol
                        })
            
            # Ordenar por fecha desc
            headlines.sort(key=lambda x: x['time'], reverse=True)
            return headlines
        except Exception as e:
            print(f"Error fetching general news: {e}")
            return []

    def _get_fundamental_news(self, pair):
        try:
            # Intentar obtener noticias específicas del par
            ticker = yf.Ticker(pair)
            news = ticker.news
            headlines = []
            
            # Si no hay noticias del par, intentar con el Dólar Index o SP500 como proxy
            if not news:
                try:
                    news = yf.Ticker("USD=X").news
                except: pass

            if news:
                for n in news[:3]: # Top 3 noticias más recientes
                    title = n.get('title', '')
                    headlines.append(title)
            
            return headlines
        except Exception as e:
            print(f"Error fetching news for {pair}: {e}")
            return []


class ArgentinaBot(InstitutionalBot):
    def __init__(self, strict_mode=False, min_atr_m5=5.0, min_atr_m15=8.0, use_ai=False, ai_model="deepseek-reasoner", ai_api_key=None, ai_provider="deepseek"):
        super().__init__(strict_mode, min_atr_m5, min_atr_m15, use_ai, ai_model, ai_api_key, ai_provider)
        self.ai_provider = ai_provider
        self.ai_api_key = ai_api_key # Ensure API key is set correctly
        
    def _pip_factor(self, pair):
        # En Merval/Cedears no usamos pips multiplicados. 1 peso es 1 unidad.
        return 1.0

    def _call_ai_api(self, system_prompt, user_prompt, response_format_json=True):
        import json
        from urllib.request import Request, urlopen
        
        if self.ai_provider == "claude":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.ai_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            body = {
                "model": self.ai_model, 
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]
            }
        else: # DeepSeek
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.ai_api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": self.ai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"} if response_format_json else None
            }

        try:
            req = Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
            # AUMENTAMOS TIMEOUT A 60 SEGUNDOS (DeepSeek Reasoner es lento)
            res = urlopen(req, timeout=60) 
            data = json.loads(res.read().decode("utf-8"))
            
            if self.ai_provider == "claude":
                return data.get("content", [{}])[0].get("text")
            else:
                return data.get("choices", [{}])[0].get("message", {}).get("content")
        except Exception as e:
            print(f"Error API IA ({self.ai_provider}): {e}")
            raise e

    # Sobreescribimos la búsqueda de setup para adaptar el PROMPT a ARGENTINA
    def _find_setup_deepseek(self, df, pair, timeframe, bias, htf_bias, atr, pip_f):
        # NOTA: Mantenemos el nombre interno aunque soporte Claude para compatibilidad
        
        news_headlines = self._get_fundamental_news(pair)
        last_row = df.iloc[-1]
        
        # Conversión segura para JSON
        def convert_numpy(obj):
            if isinstance(obj, (np.integer, np.int64)): return int(obj)
            elif isinstance(obj, (np.floating, np.float64)): return float(obj)
            elif isinstance(obj, (np.bool_, bool)): return bool(obj)
            return obj

        candles_context = []
        # Reducimos a las últimas 5 velas para acelerar el análisis
        for row in df.tail(5).to_dict(orient='records'):
            candles_context.append({
                "t": str(row.get('Date', ''))[-8:], # Solo hora
                "c": convert_numpy(row['Close']),
                "rsi": int(convert_numpy(row.get('RSI', 50)))
            })

        # Prompt restaurado y optimizado (Equilibrio entre velocidad y precisión)
        system_prompt = f"""ACTUA COMO ALGORITMO DE TRADING INSTITUCIONAL HFT.
Analiza {pair} ({timeframe}).
DATOS: {json.dumps(candles_context, default=str)}

TU TAREA:
Detectar patrones de alta probabilidad para Scalping/DayTrading.
Prioriza la estructura de mercado y la acción del precio reciente.

FORMATO DE RESPUESTA (JSON PURO):
{{
    "action": "BUY" | "SELL" | "WAIT",
    "entry": precio_float,
    "sl": precio_float,
    "tp": precio_float,
    "confidence": 65-100,
    "reason": "Explicación concisa (máx 15 palabras)",
    "fundamental_analysis": {{"bias": "NEUTRAL", "summary": "N/A"}}
}}

REGLAS CRÍTICAS:
1. Si no hay setup claro, responde "WAIT".
2. Sé agresivo si ves ruptura de estructura o rechazo claro.
3. Respeta el formato JSON estrictamente."""

        user_content = {
            "p": convert_numpy(last_row['Close']),
            "bias": bias,
            "atr": convert_numpy(atr),
            "candles": candles_context
        }

        # --- FILTRO TÉCNICO PREVIO (Para optimizar velocidad) ---
        # Si el mercado está muerto (ATR nulo o RSI neutro sin estructura), evitamos llamar a la IA
        rsi = last_row.get('RSI', 50)
        # Si RSI está en zona muerta (45-55) y no es un par volátil, podríamos saltar.
        # PERO el usuario quiere que funcione "igual que forex", así que solo filtramos casos extremos.
        if atr <= 0:
             return None, "Filtro Técnico: ATR Cero (Sin Volatilidad)"
        # --------------------------------------------------------

        try:
            # Enviamos user_content en el mensaje user
            content = self._call_ai_api(system_prompt, "ANALYZE")
            # print(f"DEBUG AI RAW: {content}") # Log para depuración
            
            # Limpiar y Parsear JSON Robusto (Regex)
            try:
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    signal = json.loads(json_str)
                else:
                    clean_content = content.replace("```json", "").replace("```", "").strip()
                    signal = json.loads(clean_content)
            except:
                return None, "ai_json_parse_error"
            
            action = signal.get("action", "WAIT").upper()
            
            # Construir razón de espera si es WAIT
            wait_reason = signal.get('reason', 'Sin razón específica')
            
            # Retornamos también el log crudo para mostrarlo en UI
            ai_log = f"🤖 IA RAW RESPONSE:\n{json.dumps(signal, indent=2)}"
            
            if action in ["BUY", "SELL"]:
                return {
                    'type': action,
                    'entry': signal.get("entry", last_row['Close']),
                    'sl': signal.get("sl"),
                    'tp': signal.get("tp"),
                    'prob': int(signal.get('confidence', 60)),
                    'reason': f"IA: {wait_reason}",
                    'duration': 5,
                    'fundamental': signal.get('fundamental_analysis'),
                    'ai_log': ai_log # Pasamos el log
                }, None
            
            return None, f"IA DECIDIÓ ESPERAR: {wait_reason} || {ai_log}"
            
        except Exception as e:
            # print(f"ERROR PARSING AI: {e}")
            return None, f"ai_error: {str(e)}"

    def run_analysis(self, pair="EURUSD=X", timeframe="1h", output_file=None):
        # Override parcial para capturar logs
        res = super().run_analysis(pair, timeframe, output_file)
        # Asegurar que los logs de la IA lleguen al resultado final si existen en el error string
        if res.get("filter_reason") and "||" in res["filter_reason"]:
            parts = res["filter_reason"].split("||")
            res["filter_reason"] = parts[0].strip()
            res["ai_log"] = parts[1].strip()
        elif res.get("signal") and "ai_log" in res["signal"]:
             res["ai_log"] = res["signal"]["ai_log"]
        return res

    def _ai_advise(self, result_data, df):
        # Asesoramiento simplificado
        # OPTIMIZACIÓN: Saltamos el segundo llamado a la IA para velocidad.
        return {"summary": "Modo HFT Rápido: Asesoramiento omitido.", "confidence": 100, "model": "local-optimized"}
