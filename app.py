# app.py
"""
Главный модуль приложения
"""
import time
import logging
from basketball_parser import BasketballParser
from database import Database
from match_monitor import MatchMonitor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


class BasketballApp:
    def __init__(self):
        self.parser = BasketballParser()
        self.db = Database()
        self.monitor = MatchMonitor(self.db)
        self.is_running = False

    def start(self):
        """Запуск приложения"""
        logging.info("Запуск парсера баскетбольных матчей...")

        try:
            self.parser.setup_driver()

            if not self.parser.load_page():
                logging.error("Не удалось загрузить страницу")
                return

            self.is_running = True
            self._main_loop()

        except KeyboardInterrupt:
            logging.info("Остановка по команде пользователя")
        except Exception as e:
            logging.error(f"Критическая ошибка: {e}")
        finally:
            self.stop()

    def stop(self):
        """Остановка приложения"""
        self.is_running = False
        self.parser.close_driver()
        if hasattr(self.db, 'conn'):
            self.db.conn.close()
        logging.info("Парсер остановлен")

    def _main_loop(self):
        """Основной цикл работы"""
        update_count = 0

        while self.is_running:
            try:
                # Парсим матчи
                matches = self.parser.parse_matches()
                logging.info(
                    f"Обновление #{update_count}: найдено {len(matches)} матчей")

                # Собираем список текущих матчей для синхронизации
                current_teams = [match['teams'] for match in matches]

                # Синхронизируем статусы
                self.db.sync_match_statuses(current_teams)

                # Сохраняем в БД
                saved_count = 0
                for match in matches:
                    success, match_type, timestamp_type = self.db.save_match_data(
                        match)
                    if success:
                        saved_count += 1

                logging.info(f"Сохранено матчей: {saved_count}")
                update_count += 1
                time.sleep(5)

            except Exception as e:
                logging.error(f"Ошибка в основном цикле: {e}")
                time.sleep(5)

    def add_to_monitor(self, team_name):
        """Добавить матч в мониторинг"""
        return self.monitor.add_match(team_name)

    def remove_from_monitor(self, team_name):
        """Убрать матч из мониторинга"""
        return self.monitor.remove_match(team_name)


def main():
    app = BasketballApp()
    app.start()


if __name__ == "__main__":
    main()
