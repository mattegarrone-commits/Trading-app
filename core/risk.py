class RiskManager:
    def __init__(self, account_balance=100000, risk_per_trade_percent=1.0):
        self.account_balance = account_balance
        self.risk_per_trade_percent = risk_per_trade_percent
        self.max_daily_drawdown_percent = 5.0

    def calculate_position_size(self, entry_price, stop_loss_price):
        """
        Calcula el tamaño de la posición (lotes) basado en el riesgo.
        Riesgo = |Entry - SL|
        Capital en Riesgo = Balance * (Risk% / 100)
        Unidades = Capital en Riesgo / Riesgo por unidad
        """
        if entry_price == stop_loss_price:
            return 0

        risk_amount = self.account_balance * (self.risk_per_trade_percent / 100)
        price_risk_per_unit = abs(entry_price - stop_loss_price)
        
        # En Forex estandar, 1 lote = 100,000 unidades.
        # Asumiendo par base USD o conversión directa para simplificar el ejemplo.
        # Ajuste simple:
        units = risk_amount / price_risk_per_unit
        
        # Convertir a lotes estándar (aprox)
        lots = units / 100000
        
        return round(lots, 2)

    def validate_trade(self, probability, risk_reward_ratio):
        """
        Filtro final de riesgo.
        Solo acepta trades con RR >= 1:2 (2.0) y probabilidad estimada alta.
        """
        # Prioridad a la efectividad: Si es > 65%, aceptamos RR más bajos (hasta 1:1)
        if probability >= 65:
            if risk_reward_ratio < 1.0:
                 return False, "Ratio Riesgo/Beneficio insuficiente (< 1:1)"
            return True, "Trade Aprobado (Efectividad > 65%)"

        # Para probabilidades menores (si llegaran a pasar), exigimos RR alto
        if risk_reward_ratio < 2.0:
            return False, "Ratio Riesgo/Beneficio insuficiente (< 1:2)"
        
        return False, "Probabilidad estimada insuficiente (< 65%)"
