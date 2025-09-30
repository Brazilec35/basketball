# match_monitor.py
"""
Мониторинг выбранных матчей
"""
import time
import logging
from datetime import datetime
from database import Database


class MatchMonitor:
    def __init__(self, database):
        self.db = database
        self.monitored_matches = set()  # отслеживаемые матчи (team_ids)
        self.match_cache = {}  # кэш данных матчей

    def add_match(self, team_name):
        """Добавить матч для мониторинга"""
        match_id = self._get_match_id(team_name)
        if match_id:
            self.monitored_matches.add(match_id)
            logging.info(f"Добавлен для мониторинга: {team_name}")
            return True
        return False

    def remove_match(self, team_name):
        """Убрать матч из мониторинга"""
        match_id = self._get_match_id(team_name)
        if match_id in self.monitored_matches:
            self.monitored_matches.remove(match_id)
            logging.info(f"Удален из мониторинга: {team_name}")
            return True
        return False

    def _get_match_id(self, team_name):
        """Получить ID матча по названию команд"""
        with self.db.conn:
            cursor = self.db.conn.execute(
                'SELECT id FROM matches WHERE teams = ? ORDER BY created_at DESC LIMIT 1',
                (team_name,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def get_monitored_stats(self):
        """Получить статистику по отслеживаемым матчам"""
        if not self.monitored_matches:
            return []

        stats = []
        match_ids = tuple(self.monitored_matches)

        with self.db.conn:
            cursor = self.db.conn.execute('''
                SELECT m.teams, m.tournament, ms.timestamp, ms.score, ms.total_points, 
                       ms.total_value, ms.under_odds, ms.over_odds
                FROM matches m
                JOIN match_stats ms ON m.id = ms.match_id
                WHERE m.id IN ({})
                AND ms.recorded_at = (
                    SELECT MAX(recorded_at) 
                    FROM match_stats 
                    WHERE match_id = m.id
                )
            '''.format(','.join('?' * len(match_ids))), match_ids)

            for row in cursor.fetchall():
                stats.append({
                    'teams': row[0],
                    'tournament': row[1],
                    'time': row[2],
                    'score': row[3],
                    'total_points': row[4],
                    'total_value': row[5],
                    'under_odds': row[6],
                    'over_odds': row[7]
                })

        return stats

    def is_match_finished(self, team_name):
        """Проверить завершен ли матч"""
        match_id = self._get_match_id(team_name)
        if not match_id:
            return False

        with self.db.conn:
            cursor = self.db.conn.execute('''
                SELECT timestamp FROM match_stats 
                WHERE match_id = ? 
                ORDER BY recorded_at DESC LIMIT 1
            ''', (match_id,))

            result = cursor.fetchone()
            if not result:
                return False

            # Простая проверка: если время содержит '+' (овертайм) или матч давно не обновлялся
            last_time = result[0]
            return '+' in last_time
