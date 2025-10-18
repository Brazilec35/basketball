# database.py
import sqlite3
import logging
from datetime import datetime
from config import BET_CONFIG


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
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=20.0)
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
                period INTEGER,
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

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS bet_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                bet_id INTEGER NOT NULL,
                final_score TEXT,
                final_points INTEGER,
                bet_result TEXT,
                total_diff REAL,
                total_diff_percent REAL,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches (id),
                FOREIGN KEY (bet_id) REFERENCES match_bets (id),
                UNIQUE(match_id, bet_id)
            )
        ''')

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS match_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_value REAL NOT NULL,
                diff_percent REAL NOT NULL,
                initial_total REAL NOT NULL,
                FOREIGN KEY (match_id) REFERENCES matches (id),
                UNIQUE(match_id)
            )
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_match_stats_period 
            ON match_stats(period)
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
                    (match_id, timestamp, period, score, total_points, total_value, under_odds, over_odds, p1_odds, p2_odds)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id,
                    current_timestamp,
                    match_data.get('period'),
                    prepared_data['score'],
                    prepared_data['total_points'],  # Должно быть числом
                    prepared_data['total_value'],
                    prepared_data['under_odds'],
                    prepared_data['over_odds'],
                    prepared_data['p1_odds'],
                    prepared_data['p2_odds']
                ))
                self.conn.commit()
                self._check_bet_condition(match_id, match_data, prepared_data)
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
                ms.recorded_at,
                mb.triggered_at,
                mb.total_value as bet_total,
                mb.diff_percent as bet_diff
            FROM matches m
            JOIN match_stats ms ON m.id = ms.match_id
            LEFT JOIN match_bets mb ON m.id = mb.match_id
            WHERE m.status = 'active'
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
        try:
            cursor = self.conn.execute('''
                SELECT id, teams, status, current_time, total_match_time 
                FROM matches 
                WHERE updated_at > datetime('now', '-4 hours')
                AND status != 'finished'
            ''')

            all_recent_matches = cursor.fetchall()
            updated_count = 0
            analyzed_count = 0

            for match_id, teams, current_status, current_time, total_match_time in all_recent_matches:
                if teams not in current_matches_teams:
                    # Помечаем матч как завершенный
                    self.conn.execute(
                        'UPDATE matches SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                        ('finished', match_id)
                    )
                    updated_count += 1
                    logging.info(f"Матч завершен: {teams} (время: {current_time}, полное: {total_match_time})")
                    
                    # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ
                    is_completed = self._is_match_fully_completed(current_time, total_match_time)
                    logging.info(f"Проверка завершения: время={current_time}, полное={total_match_time}, результат={is_completed}")
                    
                    if is_completed:
                        match_data = self._get_last_match_data(match_id)
                        logging.info(f"Данные для анализа: {match_data}")
                        self.analyze_completed_match(match_id, match_data)
                        analyzed_count += 1

            self.conn.commit()
            logging.info(
                f"Синхронизировано статусов: {updated_count} матчей, проанализировано: {analyzed_count}")

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

    def _check_bet_condition(self, match_id, match_data, prepared_data):
        try:
            # Проверяем что нет существующей ставки
            cursor = self.conn.execute(
                'SELECT 1 FROM match_bets WHERE match_id = ?',
                (match_id,)
            )
            if cursor.fetchone():
                return  # ставка уже существует

            # Проверяем условие >12%
            current_total = prepared_data.get('total_value')
            initial_total = self.get_initial_total(match_id)

            if current_total and initial_total and initial_total > 0:
                diff_percent = (
                    (current_total - initial_total) / initial_total) * 100

                # условие срабатывания
                if diff_percent > BET_CONFIG['TRIGGER_PERCENT']:
                    self.conn.execute('''
                        INSERT INTO match_bets 
                        (match_id, triggered_at, total_value, diff_percent, initial_total)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (match_id, match_data['time'], current_total, diff_percent, initial_total))
                    self.conn.commit()
                    logging.info(
                        f"🎯 Ставка зафиксирована для матча {match_id}: {diff_percent:.1f}%")

        except Exception as e:
            logging.error(f"Ошибка проверки условия ставки: {e}")

    def analyze_completed_match(self, match_id, match_data):
        try:
            # 1. Проверяем есть ли ставка для этого матча
            bet_cursor = self.conn.execute(
                'SELECT id, total_value FROM match_bets WHERE match_id = ?',
                (match_id,)
            )
            bet = bet_cursor.fetchone()
            if not bet:
                return  # нет ставки - нечего анализировать
            
            bet_id, bet_total = bet
            
            # 2. Проверяем не анализировали ли уже этот матч
            analysis_cursor = self.conn.execute(
                'SELECT 1 FROM bet_analysis WHERE match_id = ?',
                (match_id,)
            )
            if analysis_cursor.fetchone():
                return  # уже анализировали
            
            # 3. Получаем финальные данные матча
            final_points = match_data.get('total_points', 0)
            final_score = match_data.get('score', '-')
            
            # 4. ИСПРАВЛЕННАЯ ЛОГИКА - ставка на ТМ
            if final_points < bet_total:
                bet_result = 'WIN'    # ТМ сыграл - ВЫИГРЫШ
            elif final_points > bet_total:
                bet_result = 'LOSE'   # ТМ не сыграл - ПРОИГРЫШ
            else:
                bet_result = 'PUSH'   # Возврат
            
            # 5. Рассчитываем отклонение
            initial_total = self.get_initial_total(match_id)
            total_diff = bet_total - initial_total if initial_total else 0
            total_diff_percent = ((bet_total - initial_total) / initial_total * 100) if initial_total else 0
            
            # 6. Сохраняем анализ
            self.conn.execute('''
                INSERT INTO bet_analysis 
                (match_id, bet_id, final_score, final_points, bet_result, total_diff, total_diff_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (match_id, bet_id, final_score, final_points, bet_result, total_diff, total_diff_percent))
            
            self.conn.commit()
            
        except Exception as e:
            logging.error(f"Ошибка анализа матча {match_id}: {e}")

    def _get_last_match_data(self, match_id):
        """Получение последних данных матча"""
        cursor = self.conn.execute('''
            SELECT score, total_points, total_value 
            FROM match_stats 
            WHERE match_id = ? 
            ORDER BY recorded_at DESC 
            LIMIT 1
        ''', (match_id,))
        result = cursor.fetchone()
        if result:
            return {
                'score': result[0],
                'total_points': result[1],
                'total_value': result[2]
            }
        return None

    def _is_match_fully_completed(self, current_time, total_match_time):
        """Проверка что матч полноценно завершен"""
        try:
            if not current_time or current_time == '-':
                return False

            # Парсим время матча (формат "45:30" или "40:00")
            parts = current_time.split(':')
            minutes = int(parts[0]) if parts[0].isdigit() else 0

            # Проверяем пороги завершения
            if total_match_time == 40:
                return minutes >= 39
            elif total_match_time == 48:
                return minutes >= 47
            else:
                return minutes >= total_match_time - 1  # для других форматов

        except Exception as e:
            logging.error(f"Ошибка проверки завершения матча: {e}")
            return False

    def rescan_completed_matches(self):
        """Перепроверка всех завершенных матчей со ставками"""
        try:
            # Ищем матчи: finished + есть ставка + нет анализа
            cursor = self.conn.execute('''
                SELECT m.id, m.teams, m.current_time, m.total_match_time
                FROM matches m
                JOIN match_bets mb ON m.id = mb.match_id
                LEFT JOIN bet_analysis ba ON m.id = ba.match_id
                WHERE m.status = 'finished'
                AND ba.id IS NULL  -- нет анализа
            ''')
            
            matches_to_analyze = cursor.fetchall()
            analyzed_count = 0
            
            logging.info(f"🔍 Найдено матчей для перепроверки: {len(matches_to_analyze)}")
            
            for match_id, teams, current_time, total_match_time in matches_to_analyze:
                # Используем улучшенную проверку завершения
                if self._is_match_fully_completed(current_time, total_match_time):
                    match_data = self._get_last_match_data(match_id)
                    if match_data:
                        self.analyze_completed_match(match_id, match_data)
                        analyzed_count += 1
                        logging.info(f"✅ Проанализирован: {teams}")
            
            return {
                "scanned_matches": len(matches_to_analyze),
                "analyzed_matches": analyzed_count,
                "message": f"Проанализировано {analyzed_count} из {len(matches_to_analyze)} матчей"
            }
            
        except Exception as e:
            logging.error(f"Ошибка перепроверки: {e}")
            return {"error": str(e)}