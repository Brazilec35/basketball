# web_app.py
"""
Веб-интерфейс на FastAPI
"""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from config import BET_CONFIG
from database import Database, safe_float, safe_int

app = FastAPI(title="Basketball Parser")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="templates"), name="static")
db = Database()


class DataAnalyzer:
    def __init__(self, db):
        self.db = db
        self.previous_data = {}

    def calculate_changes(self, match_data):
        """Расчет изменений тотала и темпа"""
        try:
            match_id = match_data['id']
            current_time = datetime.now().timestamp()

            if match_id not in self.previous_data:
                self.previous_data[match_id] = {
                    'last_total_value': match_data.get('total_value'),
                    'last_pace': match_data.get('current_pace'),
                    'initial_total': match_data.get('total_value'),
                    'last_update': current_time
                }
                return {}

            prev_data = self.previous_data[match_id]
            changes = {}

            if (match_data.get('total_value') and
                prev_data['last_total_value'] and
                    prev_data['last_total_value'] != 0):

                total_change = ((match_data['total_value'] - prev_data['last_total_value']) /
                                prev_data['last_total_value']) * 100
                changes['total_change_percent'] = round(total_change, 1)

            if (match_data.get('current_pace') and
                prev_data['last_pace'] and
                    prev_data['last_pace'] != 0):

                pace_change = ((match_data['current_pace'] - prev_data['last_pace']) /
                               prev_data['last_pace']) * 100
                changes['pace_change_percent'] = round(pace_change, 1)

            if (match_data.get('total_value') and
                prev_data['initial_total'] and
                    prev_data['initial_total'] != 0):

                initial_diff = ((match_data['total_value'] - prev_data['initial_total']) /
                                prev_data['initial_total']) * 100
                changes['initial_total_diff'] = round(initial_diff, 1)

            prev_data.update({
                'last_total_value': match_data.get('total_value'),
                'last_pace': match_data.get('current_pace'),
                'last_update': current_time
            })

            return changes

        except Exception as e:
            logging.error(f"Ошибка расчета изменений: {e}")
            return {}


data_analyzer = DataAnalyzer(db)


@app.get("/api/matches")
async def get_matches():
    """API для получения активных матчей"""
    try:
        loop = asyncio.get_event_loop()
        matches = await loop.run_in_executor(None, db.get_active_matches)

        formatted_matches = []
        for match in matches:
            match_data = {
                'id': match[0],
                'teams': match[1],
                'tournament': match[2],
                'current_time': match[3],
                'total_match_time': safe_int(match[4]),
                'score': match[5] if match[5] else '-',
                'total_points': safe_int(match[6]),
                'total_value': safe_float(match[7])
            }
            # triggered_at exists (9-й элемент в результате SELECT)
            if match[9]:
                match_data['bet'] = {
                    'triggered_at': match[9],
                    'total_value': safe_float(match[10]),
                    'diff_percent': safe_float(match[11])
                }
            # Получаем начальный тотал
            initial_total = await loop.run_in_executor(
                None, db.get_initial_total, match_data['id']
            )
            match_data['initial_total'] = safe_float(initial_total)

            # Вычисляем темп и аналитику
            pace_data = calculate_pace(match_data)
            match_data.update(pace_data)

            # Вычисляем изменения
            changes_data = data_analyzer.calculate_changes(match_data)
            match_data.update(changes_data)

            formatted_matches.append(match_data)

        return {"matches": formatted_matches}

    except Exception as e:
        logging.error(f"Ошибка получения матчей: {e}")
        return {"matches": []}


@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """Главная страница с таблицей матчей"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/matches/{match_id}/chart")
async def get_match_chart(match_id: int):
    """API для получения данных графика с информацией о периодах"""
    try:
        loop = asyncio.get_event_loop()

        # Получаем историю матча из БД
        history = await loop.run_in_executor(
            None,
            lambda: db.conn.execute('''
                SELECT 
                    ms.timestamp,
                    ms.score,
                    ms.total_points,
                    ms.total_value,
                    ms.period_number,
                    ms.match_status,
                    ms.recorded_at
                FROM match_stats ms
                WHERE ms.match_id = ?
                ORDER BY ms.recorded_at ASC
            ''', (match_id,)).fetchall()
        )

        if not history:
            return {"error": "Данные матча не найдены"}

        # Получаем общее время матча
        match_info = await loop.run_in_executor(
            None,
            lambda: db.conn.execute(
                'SELECT total_match_time, status FROM matches WHERE id = ?',
                (match_id,)
            ).fetchone()
        )
        total_match_time = match_info[0] if match_info else 40
        # Определяем линии периодов
        if total_match_time == 48:
            period_lines = [12, 24, 36, 48]
        else:  # 40 минут по умолчанию
            period_lines = [10, 20, 30, 40]        
        match_status = match_info[1] if match_info else 'finished'

        # Форматируем данные для графика
        timestamps = []
        scores = []
        total_points = []
        total_values = []
        pace_data = []
        periods_info = []  # Информация о периодах

        for i, record in enumerate(history):
            timestamp, score, points, total_value, period_number, match_status, recorded_at = record
            
            timestamps.append(timestamp)
            scores.append(score)
            total_points.append(points)
            total_values.append(total_value)

            # Расчет темпа
            pace = calculate_pace_for_record(timestamp, points, total_match_time, total_value)
            pace_data.append(pace)

            # Сохраняем информацию о начале периодов
            if match_status in ['quarter_break', 'halftime']:
                periods_info.append({
                    'period_number': period_number,
                    'break_start_index': i,  # Индекс в массиве данных
                    'timestamp': timestamp,
                    'match_status': match_status
                })

        # Формируем ответ
        chart_response = {
            "timestamps": timestamps,
            "scores": scores,
            "total_points": total_points,
            "total_values": total_values,
            "pace_data": pace_data,
            "period_lines": period_lines,
            "total_match_time": total_match_time,
            "periods_info": periods_info,  # Добавляем информацию о периодах
            "match_status": match_info[1] if match_info else 'finished'
        }

        # Добавляем финальный результат если матч завершен
        if match_info and match_info[1] == 'finished' and total_points:
            final_points = total_points[-1] if total_points else 0
            final_total = total_values[-1] if total_values else 0
            if final_total > 0:
                chart_response["final_result"] = 'OVER' if final_points > final_total else 'UNDER'

        return chart_response

    except Exception as e:
        logging.error(f"Ошибка получения данных графика: {e}")
        return {"error": "Ошибка загрузки данных"}


@app.get("/api/matches/archive")
async def get_archive_matches(
    date_from: str = None,
    date_to: str = None,
    tournament: str = None,
    team: str = None,
    limit: int = 100
):
    """Получение завершенных матчей с полной информацией"""
    try:
        loop = asyncio.get_event_loop()

        # ОБНОВЛЕННЫЙ ЗАПРОС - добавляем статусы и данные о ставках
        query = '''
            SELECT 
                m.id, 
                m.teams, 
                m.tournament, 
                m.status,
                m.current_time,
                m.total_match_time,
                m.created_at,
                m.updated_at as finished_date,
                ms_final.score as final_score,
                ms_final.total_points as final_points,
                ms_final.total_value as final_total,
                ms_first.total_value as initial_total,
                mb.triggered_at,
                mb.total_value as bet_total,
                mb.diff_percent as bet_diff_percent,
                ba.bet_result,
                ba.final_points as bet_final_points
            FROM matches m
            JOIN match_stats ms_final ON m.id = ms_final.match_id
            JOIN match_stats ms_first ON m.id = ms_first.match_id
            LEFT JOIN match_bets mb ON m.id = mb.match_id
            LEFT JOIN bet_analysis ba ON m.id = ba.match_id
            WHERE m.status = 'finished'
            AND (
                -- МАТЧ СЧИТАЕТСЯ ЗАВЕРШЕННЫМ ЕСЛИ:
                -- 1. Время матча близко к полному (39+/47+ минут)
                (m.total_match_time = 40 AND CAST(SUBSTR(m.current_time, 1, 2) AS INTEGER) >= 39) OR
                (m.total_match_time = 48 AND CAST(SUBSTR(m.current_time, 1, 2) AS INTEGER) >= 47) OR
                (m.total_match_time != 40 AND m.total_match_time != 48 AND 
                 CAST(SUBSTR(m.current_time, 1, 2) AS INTEGER) >= m.total_match_time - 1) OR
                -- 2. ИЛИ есть результат анализа ставки (значит матч точно доигран)
                ba.bet_result IS NOT NULL
            )
            AND ms_final.recorded_at = (
                SELECT MAX(recorded_at) FROM match_stats WHERE match_id = m.id
            )
            AND ms_first.recorded_at = (
                SELECT MIN(recorded_at) FROM match_stats WHERE match_id = m.id
            )
        '''

        params = []

        # Добавляем фильтры
        if date_from:
            query += " AND DATE(m.updated_at) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND DATE(m.updated_at) <= ?"
            params.append(date_to)
        if tournament:
            query += " AND m.tournament LIKE ?"
            params.append(f'%{tournament}%')
        if team:
            query += " AND m.teams LIKE ?"
            params.append(f'%{team}%')

        query += " ORDER BY m.updated_at DESC LIMIT ?"
        params.append(limit)

        # Выполняем запрос
        matches = await loop.run_in_executor(
            None,
            lambda: db.conn.execute(query, params).fetchall()
        )

        # Форматируем результат
        formatted_matches = []
        for match in matches:
            match_data = {
                'id': match[0],
                'teams': match[1],
                'tournament': match[2],
                'status': match[3],  # ← СТАТУС
                'current_time': match[4],
                'total_match_time': match[5],
                'created_at': match[6],
                'finished_date': match[7],
                'final_score': match[8],
                'final_points': match[9],
                'final_total': match[10],
                'initial_total': match[11],
                # Данные о ставках
                'triggered_at': match[12],
                'bet_total': match[13],
                'bet_diff_percent': match[14],
                'bet_result': match[15],
                'bet_final_points': match[16]
            }

            # Рассчитываем дополнительные показатели
            if match_data['final_points'] and match_data['final_total']:
                final_pace = match_data['final_points']
                deviation = ((final_pace - match_data['final_total']) / match_data['final_total']) * 100
                match_data['final_pace'] = round(final_pace, 1)
                match_data['final_deviation'] = round(deviation, 1)
                match_data['total_result'] = 'OVER' if final_pace > match_data['final_total'] else 'UNDER'

            formatted_matches.append(match_data)

        # Базовая статистика
        stats = {
            'total_matches': len(formatted_matches),
            'over_matches': len([m for m in formatted_matches if m.get('total_result') == 'OVER']),
            'under_matches': len([m for m in formatted_matches if m.get('total_result') == 'UNDER']),
        }

        if stats['total_matches'] > 0:
            stats['over_percentage'] = round((stats['over_matches'] / stats['total_matches']) * 100, 1)
            stats['under_percentage'] = round((stats['under_matches'] / stats['total_matches']) * 100, 1)

            # Среднее отклонение
            deviations = [m.get('final_deviation', 0) for m in formatted_matches if m.get('final_deviation')]
            if deviations:
                stats['avg_deviation'] = round(sum(deviations) / len(deviations), 1)

        return {
            "matches": formatted_matches,
            "stats": stats
        }

    except Exception as e:
        logging.error(f"Ошибка получения архива: {e}")
        return {"matches": [], "stats": {}}


@app.get("/archive", response_class=HTMLResponse)
async def archive_page(request: Request):
    """Страница архива матчей"""
    return templates.TemplateResponse("archive.html", {"request": request})


def calculate_pace_for_record(timestamp, total_points, total_match_time, total_value=None):
    """Расчет темпа для конкретной записи в истории с валидацией"""
    try:
        if timestamp == '-' or ':' not in timestamp or total_points == 0:
            return None

        # Парсим время матча
        time_parts = timestamp.split(':')
        minutes_elapsed = safe_int(time_parts[0])
        seconds_elapsed = safe_int(time_parts[1]) if len(time_parts) > 1 else 0
        total_minutes_elapsed = minutes_elapsed + (seconds_elapsed / 60)

        if total_minutes_elapsed <= 0:
            return None

        # Расчет темпа
        current_pace = (total_points * total_match_time) / \
            total_minutes_elapsed

        # ВАЛИДАЦИЯ: темп не может превышать тотал более чем на 50%
        if total_value and total_value > 0:
            max_allowed_pace = total_value * 1.5  # +50% от тотала
            if current_pace > max_allowed_pace:
                logging.debug(
                    f"Темп скорректирован: {current_pace:.1f} -> {max_allowed_pace:.1f} (превышение +50%)")
                return round(max_allowed_pace, 1)

        # Дополнительная валидация: разумные пределы для баскетбола
        if current_pace > 300:  # Максимальный разумный темп
            logging.debug(
                f"Темп скорректирован: {current_pace:.1f} -> 300.0 (превышение максимального предела)")
            return 300.0

        if current_pace < 50:   # Минимальный разумный темп
            logging.debug(
                f"Темп скорректирован: {current_pace:.1f} -> 50.0 (ниже минимального предела)")
            return 50.0

        return round(current_pace, 1)

    except Exception as e:
        logging.debug(f"Ошибка расчета темпа для записи: {e}")
        return None


def calculate_pace(match_data):
    """Расчет темпа и производных показателей с валидацией"""
    try:
        if (match_data['score'] == '-' or
            match_data['current_time'] == '-' or
            ':' not in match_data['current_time'] or
                match_data['total_points'] == 0):
            return {}

        time_parts = match_data['current_time'].split(':')
        minutes_elapsed = safe_int(time_parts[0])
        seconds_elapsed = safe_int(time_parts[1]) if len(time_parts) > 1 else 0
        total_minutes_elapsed = minutes_elapsed + (seconds_elapsed / 60)

        if total_minutes_elapsed <= 0:
            return {}

        total_match_time = safe_int(match_data.get('total_match_time', 40))

        # Расчет темпа
        current_pace = (match_data['total_points']
                        * total_match_time) / total_minutes_elapsed

        # ВАЛИДАЦИЯ: темп не может превышать тотал более чем на 50%
        if match_data.get('total_value') and match_data['total_value'] > 0:
            # +50% от тотала
            max_allowed_pace = match_data['total_value'] * 1.5
            if current_pace > max_allowed_pace:
                logging.info(
                    f"Валидация темпа: {match_data['teams']} - темп скорректирован {current_pace:.1f} -> {max_allowed_pace:.1f}")
                current_pace = max_allowed_pace

        # Дополнительные разумные пределы
        if current_pace > 300:
            current_pace = 300.0
        elif current_pace < 50:
            current_pace = 50.0

        total_deviation = None
        if match_data['total_value']:
            total_deviation = (
                (current_pace - match_data['total_value']) / match_data['total_value']) * 100

        return {
            'current_pace': round(current_pace, 1),
            'total_deviation': round(total_deviation, 1) if total_deviation else None,
            'minutes_elapsed': round(total_minutes_elapsed, 1),
            'pace_validated': True  # Флаг что темп прошел валидацию
        }

    except Exception as e:
        logging.error(
            f"Ошибка расчета темпа для {match_data.get('teams', 'unknown')}: {e}")
        return {}


class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                self.active_connections.remove(connection)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Получаем данные матчей
            matches_data = await get_matches()

            # Отправляем обновление таблицы
            await websocket.send_json({
                "type": "table_update",
                "data": matches_data
            })

            # Если есть активные графики, отправляем им обновления
            for connection in manager.active_connections:
                try:
                    # Можно добавить логику для отправки конкретных данных графика
                    # если клиент сообщит какой график у него открыт
                    pass
                except:
                    manager.active_connections.remove(connection)

            await asyncio.sleep(3)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/analytics/stats")
async def get_analytics_stats():
    """Общая статистика ставок"""
    try:
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(None, lambda: db.conn.execute('''
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN bet_result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN bet_result = 'LOSE' THEN 1 ELSE 0 END) as losses,
                AVG(total_diff_percent) as avg_total_diff
            FROM bet_analysis
        ''').fetchone())

        total_bets, wins, losses, avg_total_diff = stats

        return {
            "total_bets": total_bets,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / total_bets * 100, 1) if total_bets > 0 else 0,
            "avg_total_diff": round(avg_total_diff, 1) if avg_total_diff else 0
        } 

    except Exception as e:
        logging.error(f"Ошибка получения статистики: {e}")
        return {"error": "Ошибка загрузки статистики"}


@app.get("/api/analytics/history")
async def get_analytics_history(limit: int = 50):
    """История всех ставок с результатами"""
    try:
        loop = asyncio.get_event_loop()
        history = await loop.run_in_executor(None, lambda: db.conn.execute('''
            SELECT 
                m.id,                                                           
                m.teams,
                m.tournament,
                ba.final_score,
                ba.final_points,
                mb.total_value as bet_total,
                mb.triggered_at,
                mb.initial_total,
                ba.bet_result,
                ba.total_diff,
                ba.total_diff_percent,
                ba.analyzed_at
            FROM bet_analysis ba
            JOIN matches m ON ba.match_id = m.id
            JOIN match_bets mb ON ba.bet_id = mb.id
            ORDER BY ba.analyzed_at DESC
            LIMIT ?
        ''', (limit,)).fetchall())
        
        formatted_history = []
        for row in history:
            # ВЫЧИСЛЯЕМ РАЗНИЦУ МЕЖДУ НАЧАЛЬНЫМ ТОТАЛОМ И ФИНАЛЬНЫМИ ОЧКАМИ
            initial_total = row[7]
            final_points = row[4]
            initial_final_diff = 0
            initial_final_diff_percent = 0
            
            if initial_total and final_points and initial_total > 0:
                initial_final_diff = final_points - initial_total
                initial_final_diff_percent = (initial_final_diff / initial_total) * 100

            formatted_history.append({
                'match_id': row[0],
                'teams': row[1],
                'tournament': row[2],
                'final_score': row[3],
                'final_points': row[4],
                'bet_total': row[5],
                'triggered_at': row[6],
                'initial_total': initial_total,
                'initial_final_diff': initial_final_diff,           # ← АБСОЛЮТНАЯ разница
                'initial_final_diff_percent': initial_final_diff_percent,  # ← разница в %
                'bet_result': row[8],
                'total_diff': round(row[9], 1) if row[9] else 0,
                'total_diff_percent': round(row[10], 1) if row[10] else 0,
                'analyzed_at': row[11]
            })
            
        return {
            "history": formatted_history,
            "config": {
                "trigger_percent": BET_CONFIG['TRIGGER_PERCENT']
            }
        }
        
    except Exception as e:
        logging.error(f"Ошибка получения истории: {e}")
        return {"history": [], "config": {"trigger_percent": 15}}


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    return templates.TemplateResponse("analytics.html", {"request": request})

@app.post("/api/analytics/rescan")
async def rescan_completed_matches():
    """Принудительная проверка всех завершенных матчей со ставками"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, db.rescan_completed_matches)
        return result
    except Exception as e:
        logging.error(f"Ошибка перепроверки матчей: {e}")
        return {"error": "Ошибка перепроверки"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
