# web_app.py
"""
Веб-интерфейс на FastAPI
"""
import threading
import atexit
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import json
import logging
import asyncio
import time
from datetime import datetime
from database import Database, safe_int, safe_float

app = FastAPI(title="Basketball Parser")
templates = Jinja2Templates(directory="templates")
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

        return {
            "timestamps": timestamps,
            "scores": scores,
            "total_points": total_points,
            "total_values": total_values,
            "pace_data": pace_data,
            "total_match_time": total_match_time,
            "final_result": final_result,
            "match_status": match_status
        }

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
    """Получение завершенных матчей"""
    try:
        loop = asyncio.get_event_loop()

        # Базовый SQL запрос
        query = '''
            SELECT 
                m.id, m.teams, m.tournament, m.created_at,
                ms_final.score as final_score,
                ms_final.total_points as final_points,
                ms_final.total_value as final_total,
                ms_first.total_value as initial_total,
                m.updated_at as finished_date
            FROM matches m
            JOIN match_stats ms_final ON m.id = ms_final.match_id
            JOIN match_stats ms_first ON m.id = ms_first.match_id
            WHERE m.status = 'finished'
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
                'created_at': match[3],
                'final_score': match[4],
                'final_points': match[5],
                'final_total': match[6],
                'initial_total': match[7],
                'finished_date': match[8]
            }

            # Рассчитываем дополнительные показатели
            if match_data['final_points'] and match_data['final_total']:
                # Для архивных матчей темп = финальные очки
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

# В web_app.py добавляем
active_match_monitors = {}


async def get_match_page_data(match_id):
    """Получение данных со страницы матча через Selenium Manager"""
    try:
        print(
            f"🎯 [DEBUG] get_match_page_data ВЫЗВАНА для match_id: {match_id}")

        # Получаем URL матча из БД
        loop = asyncio.get_event_loop()
        match_info = await loop.run_in_executor(
            None,
            lambda: db.conn.execute(
                'SELECT match_url, teams FROM matches WHERE id = ?',
                (match_id,)
            ).fetchone()
        )

        if not match_info or not match_info[0]:
            print(f"⚠️ [DEBUG] Матч {match_id} не найден или нет URL")
            return None

        match_url, teams = match_info
        print(f"🔗 [DEBUG] Найден URL: {match_url} для команд: {teams}")

        # Импортируем менеджер
        try:
            from selenium_manager import selenium_manager
            print("✅ [DEBUG] Selenium Manager импортирован")
        except ImportError as e:
            print(f"❌ [DEBUG] Ошибка импорта: {e}")
            return None

        # Запускаем парсинг в отдельном потоке
        print(f"🔄 [DEBUG] Запускаем парсинг для {match_url}")

        match_data = await loop.run_in_executor(
            None,
            selenium_manager.parse_match_page,
            match_url
        )

        if match_data:
            print(f"✅ [DEBUG] Успешно получены данные: {match_data}")
            match_data['source'] = 'real_match_page'
        else:
            print("⚠️ [DEBUG] parse_match_page вернул None")

        return match_data

    except Exception as e:
        print(f"❌ [DEBUG] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None


async def broadcast_chart_update(match_id, updated_data):
    """Отправка обновления графика конкретному клиенту"""
    try:
        if match_id in active_match_monitors:
            # Обновляем статус в мониторе
            active_match_monitors[match_id]['last_update'] = datetime.now()

            for connection in active_match_monitors[match_id]['connections']:
                try:
                    await connection.send_json({
                        "type": "chart_update",
                        "match_id": match_id,
                        "data": updated_data
                    })
                    logging.debug(
                        f"📨 Отправлено обновление графика для матча {match_id}")
                except Exception as e:
                    logging.error(f"❌ Ошибка отправки обновления: {e}")
                    # Удаляем нерабочее соединение
                    active_match_monitors[match_id]['connections'].remove(
                        connection)
    except Exception as e:
        logging.error(f"❌ Ошибка broadcast_chart_update: {e}")


async def update_active_charts():
    """Обновление данных для активных графиков"""
    try:
        if not active_match_monitors:
            return

        current_time = datetime.now()

        for match_id, chart_data in list(active_match_monitors.items()):
            # Проверяем когда было последнее обновление (не чаще чем раз в 2 секунды)
            last_update = chart_data.get('last_update')
            if last_update and (current_time - last_update).total_seconds() < 2:
                continue

            if chart_data['status'] == 'active':
                # Получаем свежие данные со страницы матча
                updated_data = await get_match_page_data(match_id)
                if updated_data:
                    await broadcast_chart_update(match_id, updated_data)

    except Exception as e:
        logging.error(f"❌ Ошибка update_active_charts: {e}")


def add_active_chart(match_id, websocket):
    """Добавление активного графика"""
    if match_id not in active_match_monitors:
        active_match_monitors[match_id] = {
            'status': 'active',
            'connections': [websocket]
        }
    else:
        active_match_monitors[match_id]['connections'].append(websocket)


def remove_active_chart(match_id, websocket):
    """Удаление активного графика"""
    if match_id in active_match_monitors:
        active_match_monitors[match_id]['connections'].remove(websocket)
        if not active_match_monitors[match_id]['connections']:
            del active_match_monitors[match_id]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Словарь для хранения открытых графиков этого соединения
    client_charts = set()

    try:
        while True:
            # Ожидаем сообщения от клиента
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                message = json.loads(data)

                if message.get('type') == 'chart_opened':
                    match_id = message['match_id']
                    add_active_chart(match_id, websocket)
                    client_charts.add(match_id)
                    logging.info(f"📊 График открыт: матч {match_id}")

                elif message.get('type') == 'chart_closed':
                    match_id = message['match_id']
                    remove_active_chart(match_id, websocket)
                    client_charts.discard(match_id)
                    logging.info(f"📊 График закрыт: матч {match_id}")

            except asyncio.TimeoutError:
                # Таймаут - нет сообщений от клиента, продолжаем
                pass
            except json.JSONDecodeError:
                logging.error("❌ Невалидный JSON от клиента")
            except Exception as e:
                logging.error(f"❌ Ошибка обработки сообщения: {e}")

            # Основные данные матчей (каждые 3 секунды)
            matches_data = await get_matches()

            # Приоритетное обновление для активных графиков (каждые 2 секунды)
            await update_active_charts()

            # Отправляем обновление таблицы
            await websocket.send_json({
                "type": "table_update",
                "data": matches_data
            })

            await asyncio.sleep(3)

    except WebSocketDisconnect:
        # При отключении удаляем все графики этого клиента
        for match_id in client_charts:
            remove_active_chart(match_id, websocket)
        manager.disconnect(websocket)
        logging.info(
            f"🔌 Клиент отключен, удалено графиков: {len(client_charts)}")


@atexit.register
def cleanup():
    """Очистка ресурсов при завершении работы"""
    from selenium_manager import selenium_manager
    selenium_manager.close_driver()
    logging.info("🧹 Ресурсы очищены")


def keep_alive_worker():
    """Фоновая задача для поддержания активности драйвера"""
    while True:
        try:
            from selenium_manager import manager as selenium_manager
            if selenium_manager._is_initialized:
                selenium_manager._keep_alive()
        except Exception as e:
            logging.debug(f"Keep-alive worker error: {e}")
        time.sleep(30)  # Каждые 30 секунд


# Запускаем в отдельном потоке при старте
keep_alive_thread = threading.Thread(target=keep_alive_worker, daemon=True)
keep_alive_thread.start()
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
