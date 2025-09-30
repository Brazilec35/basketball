# basketball_parser.py
"""
Простой парсер матчей
"""
import logging
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import (BROWSER_CONFIG, MATCH_TIME_CONFIG, PARSER_CONFIG,
                    SITE_CONFIG)


class BasketballParser:
    def __init__(self):
        self.driver = None
        self.wait = None

    def setup_driver(self):
        """Настройка браузера"""
        options = webdriver.ChromeOptions()

        if BROWSER_CONFIG['HEADLESS']:
            options.add_argument('--headless')

        options.add_argument(f'--user-agent={BROWSER_CONFIG["USER_AGENT"]}')
        options.add_argument(f'--window-size={BROWSER_CONFIG["WINDOW_SIZE"]}')
        options.add_argument('--disable-blink-features=AutomationControlled')

        # Масштаб 50%
        options.add_argument('--force-device-scale-factor=0.5')
        options.add_argument('--high-dpi-support=0.5')

        if BROWSER_CONFIG.get('DISABLE_LOGS', True):
            options.add_argument('--log-level=3')
            options.add_experimental_option(
                'excludeSwitches', ['enable-logging'])

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(
            self.driver, PARSER_CONFIG['PAGE_LOAD_TIMEOUT'])

    def close_driver(self):
        """Закрытие браузера"""
        if self.driver:
            self.driver.quit()

    def load_page(self):
        """Загрузка страницы"""
        try:
            self.driver.get(SITE_CONFIG['URL'])
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, SITE_CONFIG['MATCH_CONTAINER']))
            )
            return True
        except Exception as e:
            logging.error(f"Ошибка загрузки страницы: {e}")
            return False

    def parse_matches(self):
        """Парсинг всех матчей на странице"""
        try:
            matches = self.driver.find_elements(
                By.CSS_SELECTOR, SITE_CONFIG['MATCH_CONTAINER'])
            parsed_data = []

            for match in matches:
                match_data = self._parse_single_match(match)
                if match_data:
                    parsed_data.append(match_data)

            return parsed_data

        except Exception as e:
            logging.error(f"Ошибка парсинга матчей: {e}")
            return []

    def _parse_single_match(self, match_element):
        """Парсинг одного матча"""
        try:
            # Основные данные
            teams = match_element.find_element(
                By.CSS_SELECTOR, SITE_CONFIG['TEAMS_SELECTOR']).text
            match_time = match_element.find_element(
                By.CSS_SELECTOR, SITE_CONFIG['TIME_SELECTOR']).text

            # Пропускаем матчи с скобками (кроме женских)
            if '(' in teams and ')' in teams:
                if '(ж)' not in teams.lower():
                    return None

            # Счет и голы
            try:
                score = match_element.find_element(
                    By.CSS_SELECTOR, SITE_CONFIG['SCORE_SELECTOR']).text
                # ПРАВИЛЬНО ПАРСИМ total_points
                if ':' in score:
                    score_parts = score.split(':')
                    total_goals = int(score_parts[0]) + int(score_parts[1])
                else:
                    total_goals = 0
            except:
                score = '-'
                total_goals = 0

            # Логируем для отладки
            if total_goals > 0:
                logging.info(
                    f"Матч {teams}: счет {score}, total_points = {total_goals}")

            # Коэффициенты
            odds_elements = match_element.find_elements(
                By.CSS_SELECTOR, SITE_CONFIG['ODDS_SELECTOR'])
            p1 = odds_elements[0].text if len(odds_elements) > 0 else '-'
            p2 = odds_elements[2].text if len(odds_elements) > 2 else '-'

            # Тоталы
            try:
                total = match_element.find_element(
                    By.CSS_SELECTOR, SITE_CONFIG['TOTAL_SELECTOR']).text
                under_over = match_element.find_elements(
                    By.CSS_SELECTOR, SITE_CONFIG['UNDER_OVER_SELECTOR'])
                under = under_over[0].text.split(
                )[-1] if len(under_over) > 0 else '-'
                over = under_over[1].text.split(
                )[-1] if len(under_over) > 1 else '-'
            except:
                total = under = over = '-'

            # Турнир - используем правильное название метода
            tournament = self._find_tournament(match_element)

            # Определяем общее время матча
            total_match_time = self._get_total_match_time(
                tournament, match_element)

            return {
                'teams': teams,
                'tournament': tournament,
                'time': match_time,
                'total_match_time': total_match_time,
                'score': score,
                'total_points': total_goals,  # ПЕРЕДАЕМ total_points
                'p1': p1,
                'p2': p2,
                'total': total,
                'under': under,
                'over': over
            }

        except Exception as e:
            logging.error(f"Ошибка парсинга матча: {e}")
            return None

    def _get_total_match_time(self, tournament, match_element):
        """Определение общего времени матча по турниру"""
        try:
            # Проверяем формат 2x10 в интерфейсе
            try:
                period_elements = match_element.find_elements(
                    By.CSS_SELECTOR, ".event-block-label--Ol68n")
                for elem in period_elements:
                    if '2x10' in elem.text:
                        return 20  # 2x10 формат
            except:
                pass

            # Определяем по названию турнира
            tournament_upper = tournament.upper()

            # Проверяем формат 4x12 (48 минут)
            for key in MATCH_TIME_CONFIG:
                if key in ['NBA', 'CDBL', 'WCBA', 'PBA', 'Prime Division']:
                    if any(word in tournament_upper for word in [key.upper(), key]):
                        return 48

            # Проверяем формат 4x10 (40 минут)
            for key in MATCH_TIME_CONFIG:
                if key not in ['NBA', 'CDBL', 'WCBA', 'PBA', 'Prime Division', 'DEFAULT_TIME']:
                    if any(word in tournament_upper for word in [key.upper(), key]):
                        return 40

            # Стандарт по умолчанию
            return MATCH_TIME_CONFIG['DEFAULT_TIME']

        except Exception as e:
            logging.debug(f"Ошибка определения времени матча: {e}")
            return MATCH_TIME_CONFIG['DEFAULT_TIME']

    def _find_tournament(self, match_element):
        """Поиск названия турнира для конкретного матча"""
        try:
            # Находим все контейнеры турниров и матчей
            all_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                ".sport-competition--Xt2wb, .sport-base-event--W4qkO"
            )

            # Находим индекс текущего матча
            current_match_index = None
            for i, element in enumerate(all_elements):
                if element == match_element:
                    current_match_index = i
                    break

            if current_match_index is None:
                return "Неизвестно"

            # Ищем ближайший турнир выше по иерархии
            current_tournament = "Неизвестно"
            for i in range(current_match_index, -1, -1):
                element = all_elements[i]
                element_class = element.get_attribute("class")

                if "sport-competition--" in element_class:
                    # Нашли турнир, извлекаем название
                    try:
                        tournament_name = element.find_element(
                            By.CSS_SELECTOR, ".table-component-text--Tjj3g"
                        ).text.strip()
                        current_tournament = tournament_name
                        break
                    except Exception as e:
                        logging.debug(
                            f"Не удалось извлечь название турнира: {e}")
                        continue

            return current_tournament

        except Exception as e:
            logging.debug(f"Ошибка поиска турнира: {e}")
            return "Неизвестно"
