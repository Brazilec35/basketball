# database.py
import sqlite3
import logging
from datetime import datetime


def safe_int(value, default=0):
    """Безопасное преобразование в int"""
    try:
        if value is None or value == '-':
            return default
        return int(float(value)) if value else default
    except (ValueError, TypeError):
        return default


def safe_float(value, default=None):
    """Безопасное преобразование в float"""
    try:
        if value is None or value == '-':
            return default
        return float(str(value).replace(',', '.')) if value else default
    except (ValueError, TypeError):
        return default


class Database:
    def __init__(self, db_path='basketball.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        """Инициализация таблиц"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teams TEXT NOT NULL UNIQUE,
                tournament TEXT,
                current_time TEXT,
                total_match_time INTEGER DEFAULT 40,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS match_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                timestamp TEXT NOT NULL,
                score TEXT,
                total_points INTEGER,
                total_value REAL,
                under_odds REAL,
                over_odds REAL,
                p1_odds REAL,
                p2_odds REAL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches (id),
                UNIQUE(match_id, timestamp)
            )
        ''')

        self.conn.commit()

    def get_or_create_match(self, match_data):
        """Получить существующий матч или создать новый"""
        teams = match_data['teams']

        cursor = self.conn.execute(
            'SELECT id FROM matches WHERE teams = ?',
            (teams,)
        )
        result = cursor.fetchone()

        if result:
            match_id = result[0]
            self.conn.execute(
                'UPDATE matches SET current_time = ?, total_match_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (match_data['time'], match_data['total_match_time'], match_id)
            )
            self.conn.commit()
            return match_id, 'existing'
        else:
            cursor = self.conn.execute('''
                INSERT INTO matches (teams, tournament, current_time, total_match_time)
                VALUES (?, ?, ?, ?)
            ''', (teams, match_data['tournament'], match_data['time'], match_data['total_match_time']))

            match_id = cursor.lastrowid
            self.conn.commit()
            return match_id, 'new'

    def save_match_data(self, match_data):
        """Сохранение данных матча с сохранением последних значений"""
        try:
            match_id, match_type = self.get_or_create_match(match_data)

            # Логируем полученные данные
            logging.info(
                f"Сохранение матча {match_data['teams']}: score={match_data['score']}, total_points={match_data.get('total_points')}")

            # Обновляем статус матча на 'active' при каждом обновлении
            self.conn.execute(
                'UPDATE matches SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                ('active', match_id)
            )

            last_values = self._get_last_match_values(match_id)
            prepared_data = self._prepare_match_data(match_data, last_values)

            existing_timestamp = self._get_last_timestamp(match_id)
            current_timestamp = match_data['time']

            if existing_timestamp != current_timestamp:
                self.conn.execute('''
                    INSERT INTO match_stats 
                    (match_id, timestamp, score, total_points, total_value, under_odds, over_odds, p1_odds, p2_odds)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id,
                    current_timestamp,
                    prepared_data['score'],
                    prepared_data['total_points'],  # Должно быть числом
                    prepared_data['total_value'],
                    prepared_data['under_odds'],
                    prepared_data['over_odds'],
                    prepared_data['p1_odds'],
                    prepared_data['p2_odds']
                ))
                self.conn.commit()

                # Логируем сохраненные данные
                logging.info(
                    f"Сохранено: total_points={prepared_data['total_points']}")

                return True, match_type, 'new_timestamp'
            else:
                return True, match_type, 'same_timestamp'

        except Exception as e:
            logging.error(f"Ошибка сохранения в БД: {e}")
            return False, 'error', 'error'

    def _get_last_match_values(self, match_id):
        """Получить последние известные значения из БД"""
        try:
            cursor = self.conn.execute('''
                SELECT total_value, under_odds, over_odds, p1_odds, p2_odds
                FROM match_stats 
                WHERE match_id = ? 
                ORDER BY recorded_at DESC 
                LIMIT 1
            ''', (match_id,))

            result = cursor.fetchone()
            if result:
                return {
                    'total_value': result[0],
                    'under_odds': result[1],
                    'over_odds': result[2],
                    'p1_odds': result[3],
                    'p2_odds': result[4]
                }
        except Exception as e:
            logging.error(f"Ошибка получения последних значений: {e}")

        return {}

    def _prepare_match_data(self, match_data, last_values):
        """Подготовка данных с сохранением последних значений"""
        prepared = match_data.copy()

        # Сохраняем последние значения если текущие пустые
        if prepared['total'] == '-' and last_values.get('total_value'):
            prepared['total_value'] = last_values['total_value']

        if prepared['under'] == '-' and last_values.get('under_odds'):
            prepared['under_odds'] = last_values['under_odds']

        if prepared['over'] == '-' and last_values.get('over_odds'):
            prepared['over_odds'] = last_values['over_odds']

        if prepared['p1'] == '-' and last_values.get('p1_odds'):
            prepared['p1_odds'] = last_values['p1_odds']

        if prepared['p2'] == '-' and last_values.get('p2_odds'):
            prepared['p2_odds'] = last_values['p2_odds']

        # Конвертируем строки в числа
        prepared['total_value'] = self._parse_float(
            prepared.get('total_value', prepared['total']))
        prepared['under_odds'] = self._parse_float(
            prepared.get('under_odds', prepared['under']))
        prepared['over_odds'] = self._parse_float(
            prepared.get('over_odds', prepared['over']))
        prepared['p1_odds'] = self._parse_float(
            prepared.get('p1_odds', prepared['p1']))
        prepared['p2_odds'] = self._parse_float(
            prepared.get('p2_odds', prepared['p2']))

        # Убедимся что total_points есть и это число
        prepared['total_points'] = safe_int(prepared.get('total_points', 0))

        return prepared

    def _get_last_timestamp(self, match_id):
        """Получить последнюю временную метку для матча"""
        cursor = self.conn.execute(
            'SELECT timestamp FROM match_stats WHERE match_id = ? ORDER BY recorded_at DESC LIMIT 1',
            (match_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def _parse_float(self, value):
        """Парсинг числовых значений"""
        if value == '-' or not value:
            return None
        try:
            return float(str(value).replace(',', '.'))
        except:
            return None

    def get_active_matches(self):
        """Получить только активные матчи"""
        cursor = self.conn.execute('''
            SELECT 
                m.id, 
                m.teams, 
                m.tournament, 
                m.current_time,
                m.total_match_time,
                ms.score,
                ms.total_points,
                ms.total_value,
                ms.recorded_at
            FROM matches m
            JOIN match_stats ms ON m.id = ms.match_id
            WHERE m.status = 'active'  -- ← ДОБАВЛЯЕМ ФИЛЬТР ПО СТАТУСУ
            AND ms.recorded_at = (
                SELECT MAX(recorded_at) 
                FROM match_stats 
                WHERE match_id = m.id
            )
            AND m.updated_at > datetime('now', '-30 minutes')
            ORDER BY ms.recorded_at DESC
        ''')

        return cursor.fetchall()

    def sync_match_statuses(self, current_matches_teams):
        """Синхронизация статусов матчей с текущими данными парсера"""
        try:
            cursor = self.conn.execute('''
                SELECT id, teams, status 
                FROM matches 
                WHERE updated_at > datetime('now', '-4 hours')
                AND status != 'finished'
            ''')

            all_recent_matches = cursor.fetchall()
            updated_count = 0

            for match_id, teams, current_status in all_recent_matches:
                if teams not in current_matches_teams:
                    self.conn.execute(
                        'UPDATE matches SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                        ('finished', match_id)
                    )
                    updated_count += 1
                    logging.info(f"Матч завершен: {teams}")

            self.conn.commit()
            logging.info(f"Синхронизировано статусов: {updated_count} матчей")

        except Exception as e:
            logging.error(f"Ошибка синхронизации статусов: {e}")

    def get_initial_total(self, match_id):
        """Получить начальный тотал матча (первый сохраненный)"""
        try:
            cursor = self.conn.execute('''
                SELECT total_value
                FROM match_stats
                WHERE match_id = ?
                ORDER BY recorded_at ASC
                LIMIT 1
            ''', (match_id,))

            result = cursor.fetchone()
            return result[0] if result else None

        except Exception as e:
            logging.error(f"Ошибка получения начального тотала: {e}")
            return None
