# web_app.py
"""
Веб-интерфейс на FastAPI
"""
import asyncio
import logging
import json
from datetime import datetime

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import Database, safe_float, safe_int

app = FastAPI(title="Basketball Parser")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="templates"), name="static")
db = Database()


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

            # Получаем начальный тотал
            initial_total = await loop.run_in_executor(
                None, db.get_initial_total, match_data['id']
            )
            match_data['initial_total'] = safe_float(initial_total)

            # Вычисляем темп и аналитику
            pace_data = calculate_pace(match_data)
            match_data.update(pace_data)

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
    """API для получения данных графика матча (работает и для архивных)"""
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

        for record in history:
            timestamp = record[0] if record[0] else '0:00'
            score = record[1] if record[1] else '-'
            points = record[2] if record[2] is not None else 0
            total_value = record[3] if record[3] is not None else 0

            timestamps.append(timestamp)
            scores.append(score)
            total_points.append(points)
            total_values.append(total_value)

            # ВЫЧИСЛЯЕМ ТЕМП ДЛЯ АРХИВНЫХ МАТЧЕЙ
            pace = calculate_pace_for_record(
                timestamp, points, total_match_time, total_value)
            pace_data.append(pace)

        # Для архивных матчей добавляем финальную информацию
        final_result = None
        if match_status == 'finished' and total_points:
            final_points = total_points[-1] if total_points else 0
            final_total = total_values[-1] if total_values else 0
            if final_total > 0:
                final_result = 'OVER' if final_points > final_total else 'UNDER'

        chart_response = {
            "timestamps": timestamps,
            "scores": scores,
            "total_points": total_points,
            "total_values": total_values,
            "pace_data": pace_data,
            "period_lines": period_lines,
            "total_match_time": total_match_time,
            "final_result": final_result,
            "match_status": match_status
        }

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
                ms_first.total_value as initial_total
            FROM matches m
            JOIN match_stats ms_final ON m.id = ms_final.match_id
            JOIN match_stats ms_first ON m.id = ms_first.match_id
            WHERE m.status = 'finished'
            AND (
                -- МАТЧ СЧИТАЕТСЯ ЗАВЕРШЕННЫМ ЕСЛИ:
                -- 1. Время матча близко к полному (39+/47+ минут)
                (m.total_match_time = 40 AND CAST(SUBSTR(m.current_time, 1, 2) AS INTEGER) >= 39) OR
                (m.total_match_time = 48 AND CAST(SUBSTR(m.current_time, 1, 2) AS INTEGER) >= 47) OR
                (m.total_match_time != 40 AND m.total_match_time != 48 AND 
                CAST(SUBSTR(m.current_time, 1, 2) AS INTEGER) >= m.total_match_time - 1)
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
                'status': match[3],
                'current_time': match[4],
                'total_match_time': match[5],
                'created_at': match[6],
                'finished_date': match[7],
                'final_score': match[8],
                'final_points': match[9],
                'final_total': match[10],
                'initial_total': match[11]
            }

            # Рассчитываем дополнительные показатели
            if match_data['final_points'] and match_data['final_total']:
                final_pace = match_data['final_points']
                deviation = (
                    (final_pace - match_data['final_total']) / match_data['final_total']) * 100
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
            stats['over_percentage'] = round(
                (stats['over_matches'] / stats['total_matches']) * 100, 1)
            stats['under_percentage'] = round(
                (stats['under_matches'] / stats['total_matches']) * 100, 1)

            # Среднее отклонение
            deviations = [m.get('final_deviation', 0)
                          for m in formatted_matches if m.get('final_deviation')]
            if deviations:
                stats['avg_deviation'] = round(
                    sum(deviations) / len(deviations), 1)

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
                return round(max_allowed_pace, 1)

        # Дополнительная валидация: разумные пределы для баскетбола
        if current_pace > 300:  # Максимальный разумный темп
            return 300.0

        if current_pace < 50:   # Минимальный разумный темп
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
            # Ждем сообщения от клиента (или просто поддерживаем соединение)
            data = await websocket.receive_text()
            # Можно обрабатывать команды от клиента если нужно
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Отдельная задача для рассылки обновлений
async def broadcast_updates():
    while True:
        try:
            matches_data = await get_matches()
            await manager.broadcast(json.dumps({
                "type": "table_update",
                "data": matches_data
            }))
            await asyncio.sleep(3)
        except Exception as e:
            logging.error(f"WebSocket broadcast error: {e}")
            await asyncio.sleep(5)

# Запускаем при старте приложения
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_updates())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
