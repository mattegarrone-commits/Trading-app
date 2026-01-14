import requests
import json
import os
from datetime import datetime

class TelegramNotifier:
    def __init__(self, token=None, chat_id=None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None

    def is_configured(self):
        return bool(self.token and self.chat_id)

    def _escape_html(self, text):
        if not isinstance(text, str):
            return str(text)
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def send_message(self, message):
        if not self.is_configured():
            return False, "Telegram no configurado"
        
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True, "Mensaje enviado"
            else:
                return False, f"Error API Telegram: {response.text}"
        except Exception as e:
            return False, f"Error de conexión: {str(e)}"

    def send_signal(self, signal_data, pair, timeframe, image_buf=None):
        """
        Formatea y envía una señal de trading. Opcionalmente envía un gráfico.
        """
        if not self.is_configured():
            return False, "Telegram no configurado"

        icon = "🟢 COMPRA" if signal_data['type'] == 'BUY' else "🔴 VENTA"
        
        fundamental = signal_data.get('fundamental', {})
        fund_text = ""
        if fundamental and fundamental.get('bias') != 'NEUTRAL':
            summary = self._escape_html(fundamental.get('summary', ''))
            bias = self._escape_html(fundamental.get('bias', ''))
            fund_text = f"📰 <b>Fundamental:</b> {bias} ({summary})\n"

        reason = self._escape_html(signal_data.get('reason', 'N/A'))
        
        msg = (
            f"<b>{icon} NUEVA SEÑAL</b>\n\n"
            f"🪙 <b>Par:</b> {pair}\n"
            f"⏰ <b>TF:</b> {timeframe}\n"
            f"📉 <b>Entrada:</b> {signal_data['entry']:.5f}\n"
            f"🛑 <b>Stop Loss:</b> {signal_data['sl']:.5f}\n"
            f"🎯 <b>Take Profit:</b> {signal_data['tp']:.5f}\n\n"
            f"{fund_text}"
            f"🧠 <b>Tesis:</b> {reason}\n"
            f"⏳ <b>Duración Est.:</b> {signal_data.get('duration', '?')} velas\n"
            f"📊 <b>Confianza:</b> {signal_data.get('prob', 'N/A')}%\n"
            f"📅 <b>Hora:</b> {datetime.now().strftime('%H:%M:%S')}"
        )
        
        try:
            if image_buf:
                image_buf.seek(0) # Asegurar inicio
                url = f"{self.base_url}/sendPhoto"
                data = {
                    "chat_id": self.chat_id,
                    "caption": msg,
                    "parse_mode": "HTML"
                }
                files = {"photo": ("chart.png", image_buf, "image/png")}
                response = requests.post(url, data=data, files=files, timeout=20)
            else:
                return self.send_message(msg)

            if response.status_code == 200:
                return True, "Mensaje enviado"
            else:
                return False, f"Error API Telegram: {response.text}"
        except Exception as e:
            return False, f"Error enviando a Telegram: {e}"
