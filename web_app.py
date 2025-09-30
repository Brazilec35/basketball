# web_app.py
"""
Веб-интерфейс на FastAPI
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import json
import logging
import asyncio
from datetime import datetime
# Импортируем функции из database
from database import Database, safe_int, safe_float

app = FastAPI(title="Basketball Parser")
templates = Jinja2Templates(directory="templates")
db = Database()

# Убираем дублирующиеся функции safe_int и safe_float отсюда


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
        # Используем asyncio для выполнения синхронных операций с БД
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
    """API для получения данных графика матча"""
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
                'SELECT total_match_time FROM matches WHERE id = ?',
                (match_id,)
            ).fetchone()
        )
        total_match_time = match_info[0] if match_info else 40

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

            # Вычисляем темп для этой записи
            pace = calculate_pace_for_record(
                timestamp, points, total_match_time)
            pace_data.append(pace)

        return {
            "timestamps": timestamps,
            "scores": scores,  # ⬅️ ВАЖНО: возвращаем scores
            "total_points": total_points,
            "total_values": total_values,
            "pace_data": pace_data,
            "total_match_time": total_match_time
        }

    except Exception as e:
        logging.error(f"Ошибка получения данных графика: {e}")
        return {"error": "Ошибка загрузки данных"}


def calculate_pace_for_record(timestamp, total_points, total_match_time):
    """Расчет темпа для конкретной записи в истории"""
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
        return round(current_pace, 1)

    except Exception as e:
        logging.debug(f"Ошибка расчета темпа для записи: {e}")
        return None


def calculate_pace(match_data):
    """Расчет темпа и производных показателей"""
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
        current_pace = (match_data['total_points']
                        * total_match_time) / total_minutes_elapsed

        total_deviation = None
        if match_data['total_value']:
            total_deviation = (
                (current_pace - match_data['total_value']) / match_data['total_value']) * 100

        return {
            'current_pace': round(current_pace, 1),
            'total_deviation': round(total_deviation, 1) if total_deviation else None,
            'minutes_elapsed': round(total_minutes_elapsed, 1)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
