import pandas as pd
import json
import os
from datetime import datetime
import yfinance as yf

class TradeTracker:
    def __init__(self, filepath="trade_history.json"):
        self.filepath = filepath
        self.trades = self._load_trades()

    def _load_trades(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_trades(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.trades, f, indent=4)

    def add_trade(self, signal, pair):
        # Evitar duplicados recientes (mismo par y tipo en la última hora)
        now_ts = datetime.utcnow().timestamp()
        for t in self.trades:
            if t['pair'] == pair and t['type'] == signal['type'] and t['status'] == 'PENDING':
                # Si la señal es muy reciente (< 1 hora), no la duplicamos
                if (now_ts - t['timestamp']) < 3600: 
                    return

        new_trade = {
            "id": int(now_ts),
            "timestamp": now_ts,
            "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "pair": pair,
            "type": signal['type'],
            "entry": signal['entry'],
            "sl": signal['sl'],
            "tp": signal['tp'],
            "status": "PENDING", # PENDING, WIN, LOSS
            "pnl": 0.0,
            "exit_price": 0.0,
            "closed_at": None
        }
        self.trades.append(new_trade)
        self.save_trades()

    def update_trades(self):
        # Verificar trades pendientes
        updated_count = 0
        for trade in self.trades:
            if trade['status'] == 'PENDING':
                # Bajar datos recientes para verificar
                # Usamos intervalo 5m para tener granularidad
                try:
                    df = yf.download(trade['pair'], period="5d", interval="5m", progress=False)
                except Exception:
                    continue
                    
                if df is None or df.empty: continue
                
                # Filtrar datos posteriores a la entrada
                # yfinance devuelve index con zona horaria, trade timestamp es UTC sin zona
                # Normalizamos simple: comparamos timestamps
                df['ts'] = df.index.astype(int) / 10**9
                future_data = df[df['ts'] > trade['timestamp']]
                
                if future_data.empty: continue
                
                # Simular recorrido vela a vela
                for idx, row in future_data.iterrows():
                    high = row['High'].item()
                    low = row['Low'].item()
                    
                    if trade['type'] == 'BUY':
                        # TP Hit?
                        if high >= trade['tp']:
                            trade['status'] = 'WIN'
                            trade['exit_price'] = trade['tp']
                            trade['pnl'] = trade['tp'] - trade['entry']
                            trade['closed_at'] = str(idx)
                            updated_count += 1
                            break
                        # SL Hit?
                        if low <= trade['sl']:
                            trade['status'] = 'LOSS'
                            trade['exit_price'] = trade['sl']
                            trade['pnl'] = trade['sl'] - trade['entry']
                            trade['closed_at'] = str(idx)
                            updated_count += 1
                            break
                            
                    elif trade['type'] == 'SELL':
                        # TP Hit? (Precio baja)
                        if low <= trade['tp']:
                            trade['status'] = 'WIN'
                            trade['exit_price'] = trade['tp']
                            trade['pnl'] = trade['entry'] - trade['tp']
                            trade['closed_at'] = str(idx)
                            updated_count += 1
                            break
                        # SL Hit? (Precio sube)
                        if high >= trade['sl']:
                            trade['status'] = 'LOSS'
                            trade['exit_price'] = trade['sl']
                            trade['pnl'] = trade['entry'] - trade['sl']
                            trade['closed_at'] = str(idx)
                            updated_count += 1
                            break
        
        if updated_count > 0:
            self.save_trades()
        return updated_count

    def get_stats(self):
        total = 0
        wins = 0
        losses = 0
        for t in self.trades:
            if t['status'] in ['WIN', 'LOSS']:
                total += 1
                if t['status'] == 'WIN': wins += 1
                else: losses += 1
        
        win_rate = (wins / total * 100) if total > 0 else 0.0
        return {
            "total_closed": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "pending": len([t for t in self.trades if t['status'] == 'PENDING'])
        }
