# strategy_analyzer.py
"""
Анализатор стратегии разворота
"""
import logging
from datetime import datetime
from config import STRATEGY_CONFIG

class StrategyAnalyzer:
    def __init__(self, db):
        self.db = db
        self.match_signals = {}  # Храним сигналы по матчам
    
    def analyze_match_strategy(self, match_data):
        """Анализ матча по стратегии разворота"""
        try:
            match_id = match_data['id']
            
            # Проверяем базовые условия
            if not self._check_basic_conditions(match_data):
                return None
            
            # Получаем историю сигналов для матча
            if match_id not in self.match_signals:
                self.match_signals[match_id] = {
                    'deviation_signals': [],
                    'reversal_signals': [],
                    'last_analysis': None
                }
            
            signal_data = self.match_signals[match_id]
            
            # 1. Проверяем отклонение тотала
            deviation_signal = self._check_deviation_signal(match_data, signal_data)
            if deviation_signal:
                return deviation_signal
            
            # 2. Проверяем разворот темпа
            reversal_signal = self._check_pace_reversal(match_data, signal_data)
            if reversal_signal:
                return reversal_signal
            
            # 3. Проверяем сигнал на ставку
            bet_signal = self._check_bet_signal(match_data, signal_data)
            if bet_signal:
                return bet_signal
            
            return None
            
        except Exception as e:
            logging.error(f"Ошибка анализа стратегии: {e}")
            return None
    
    def _check_basic_conditions(self, match_data):
        """Проверка базовых условий для анализа"""
        if (not match_data.get('total_value') or 
            not match_data.get('current_pace') or
            match_data['score'] == '-'):
            return False
        
        # Проверяем прогресс матча
        progress = match_data.get('match_progress', 0)
        if (progress < STRATEGY_CONFIG['MIN_MATCH_PROGRESS'] or 
            progress > STRATEGY_CONFIG['MAX_MATCH_PROGRESS']):
            return False
        
        return True
    
    def _check_deviation_signal(self, match_data, signal_data):
        """Проверка сигнала отклонения тотала"""
        deviation = match_data.get('total_deviation', 0)
        
        if abs(deviation) >= STRATEGY_CONFIG['DEVIATION_THRESHOLD']:
            # Проверяем, не было ли уже такого сигнала
            recent_signals = [s for s in signal_data['deviation_signals'] 
                            if s['timestamp'] > datetime.now().timestamp() - 300]  # Последние 5 минут
            
            if not recent_signals:
                signal_type = 'high' if deviation > 0 else 'low'
                signal = {
                    'type': 'deviation',
                    'signal_type': signal_type,
                    'deviation': deviation,
                    'message': f"📊 Тотал изменился на {abs(deviation):.1f}%",
                    'timestamp': datetime.now().timestamp()
                }
                
                signal_data['deviation_signals'].append(signal)
                return signal
        
        return None
    
    def _check_pace_reversal(self, match_data, signal_data):
        """Проверка разворота темпа"""
        if not signal_data['deviation_signals']:
            return None
        
        # Берем последний сигнал отклонения
        last_deviation = signal_data['deviation_signals'][-1]
        current_deviation = match_data.get('total_deviation', 0)
        
        # Проверяем разворот (отклонение уменьшается)
        if (last_deviation['signal_type'] == 'high' and current_deviation < last_deviation['deviation'] * 0.7 or
            last_deviation['signal_type'] == 'low' and current_deviation > last_deviation['deviation'] * 0.7):
            
            reversal_signal = {
                'type': 'reversal',
                'direction': 'down' if last_deviation['signal_type'] == 'high' else 'up',
                'message': f"🔄 Разворот темпа! Отклонение уменьшается",
                'timestamp': datetime.now().timestamp()
            }
            
            signal_data['reversal_signals'].append(reversal_signal)
            return reversal_signal
        
        return None
    
    def _check_bet_signal(self, match_data, signal_data):
        """Проверка сигнала на ставку"""
        if (len(signal_data['deviation_signals']) >= 1 and 
            len(signal_data['reversal_signals']) >= STRATEGY_CONFIG['PACE_REVERSAL_CONFIRMATIONS']):
            
            # Проверяем, что тотал пошел в ту же сторону что и темп
            last_deviation = signal_data['deviation_signals'][-1]
            last_reversal = signal_data['reversal_signals'][-1]
            current_deviation = match_data.get('total_deviation', 0)
            
            # Если тотал продолжает движение в направлении разворота
            if (last_reversal['direction'] == 'down' and current_deviation < 0 or
                last_reversal['direction'] == 'up' and current_deviation > 0):
                
                bet_type = 'ТМ' if last_reversal['direction'] == 'down' else 'ТБ'
                bet_signal = {
                    'type': 'bet',
                    'bet_type': bet_type,
                    'total_value': match_data['total_value'],
                    'message': f"🎯 СТАВКА: {bet_type}({match_data['total_value']})",
                    'timestamp': datetime.now().timestamp()
                }
                
                # Очищаем сигналы после ставки
                signal_data['deviation_signals'].clear()
                signal_data['reversal_signals'].clear()
                
                return bet_signal
        
        return None