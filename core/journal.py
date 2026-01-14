import json
import os
from datetime import datetime, timedelta
import yfinance as yf

class TradeJournal:
    def __init__(self, filepath="trade_journal.json"):
        self.filepath = filepath
        self.trades = self._load_journal()

    def _load_journal(self):
        if not os.path.exists(self.filepath):
            return []
        try:
            with open(self.filepath, 'r') as f:
                return json.load(f)
        except:
            return []

    def log_trade(self, trade_data):
        with self.lock:
            trade_data['timestamp'] = datetime.now().isoformat()
            self.trades.append(trade_data)
            self._save_journal()

    def _save_journal(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.trades, f, indent=4)

    def _evaluate_trade(self, t):
        pair = t.get('pair')
        tf = t.get('timeframe', '15m')
        ts = t.get('timestamp')
        if not pair or not ts:
            return 'skip'
        try:
            start_dt = datetime.fromisoformat(ts)
        except:
            return 'skip'
        horizon_bars = 20 if tf in ['5m','15m'] else 10
        delta = 5 if tf=='5m' else 15 if tf=='15m' else 60
        end_dt = start_dt + timedelta(minutes=delta*horizon_bars)
        data = yf.download(pair, start=start_dt, end=end_dt, interval=tf, progress=False, auto_adjust=True)
        if data.empty:
            return 'no_data'
        entry = t['entry']; sl = t['sl']; tp = t['tp']; side = t['type']
        for _, row in data.iterrows():
            high = float(row['High']); low = float(row['Low'])
            if side == 'BUY':
                if low <= sl:
                    return 'loss'
                if high >= tp:
                    return 'win'
            else:
                if high >= sl:
                    return 'loss'
                if low <= tp:
                    return 'win'
        return 'open'

    def get_stats(self):
        total = len(self.trades)
        if total == 0:
            return {"total":0, "wins":0, "losses":0, "win_rate":0.0}
        wins=0; losses=0; evaluated=0
        for t in self.trades:
            res = self._evaluate_trade(t)
            if res in ('win','loss'):
                evaluated+=1
                if res=='win': wins+=1
                else: losses+=1
        win_rate = (wins / evaluated * 100.0) if evaluated>0 else 0.0
        return {"total": total, "evaluated": evaluated, "wins": wins, "losses": losses, "win_rate": round(win_rate,2)}

    def get_stats_by_timeframe(self, tfs=("5m","15m")):
        out = {}
        for tf in tfs:
            wins=0; losses=0; evaluated=0; total=0
            for t in self.trades:
                if t.get('timeframe') == tf:
                    total+=1
                    res = self._evaluate_trade(t)
                    if res in ('win','loss'):
                        evaluated+=1
                        if res=='win': wins+=1
                        else: losses+=1
            wr = (wins / evaluated * 100.0) if evaluated>0 else 0.0
            out[tf] = {"total": total, "evaluated": evaluated, "wins": wins, "losses": losses, "win_rate": round(wr,2)}
        return out

    def export_csv(self, path):
        try:
            import pandas as pd
            df = pd.DataFrame(self.trades)
            df.to_csv(path, index=False)
            return path
        except Exception:
            return ""
