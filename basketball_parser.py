# basketball_parser.py
"""
Простой парсер матчей
"""
import logging
from datetime import datetime
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import (BROWSER_CONFIG, MATCH_TIME_CONFIG, PARSER_CONFIG,
                    SITE_CONFIG, MATCH_FILTERS)


class BasketballParser:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.banned_tournaments = MATCH_FILTERS['BANNED_TOURNAMENTS']

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
        """Парсинг всех матчей на странице с фильтрацией"""
        try:
            matches = self.driver.find_elements(
                By.CSS_SELECTOR, SITE_CONFIG['MATCH_CONTAINER'])
            parsed_data = []

            for match in matches:
                match_data = self._parse_single_match(match)

                # ФИЛЬТРАЦИЯ: проверяем разрешен ли турнир
                if match_data and self._is_tournament_allowed(match_data):
                    parsed_data.append(match_data)
                elif match_data:
                    logging.debug(
                        f"Пропущен матч из запрещенного турнира: {match_data['teams']}")

            return parsed_data

        except Exception as e:
            logging.error(f"Ошибка парсинга матчей: {e}")
            return []

    def _is_tournament_allowed(self, match_data):
        """Проверяет, разрешен ли турнир для обработки"""
        tournament = match_data['tournament']

        # Если турнир в списке запрещенных - пропускаем
        if tournament in self.banned_tournaments:
            return False

        # Дополнительные проверки (если нужны)
        if MATCH_FILTERS['EXCLUDE_WOMEN'] and '(ж)' in match_data['teams'].lower():
            return False

        return True

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

            match_url = self.extract_match_url(match_element)
            match_status = self.extract_match_status(match_element)

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
                'over': over,
                'match_url': match_url,
                'match_status': match_status
            }

        except Exception as e:
            logging.debug(f"Ошибка парсинга матча: {e}")
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

    def extract_match_url(self, match_element):
        """Извлечение URL матча"""
        try:
            link_element = match_element.find_element(
                By.CSS_SELECTOR, 'a.sport-event__name--YAs00'
            )
            href = link_element.get_attribute('href')
            return href if href else None
        except Exception as e:
            logging.debug(f"Не удалось извлечь URL матча: {e}")
            return None

    def extract_match_status(self, match_element):
        """Определение статуса матча по иконкам"""
        try:
            # Проверяем наличие иконки паузы
            pause_icons = match_element.find_elements(
                By.CSS_SELECTOR, 'svg[resource-name="timerPaused"]'
            )

            # Если иконка паузы видима - матч на паузе
            for icon in pause_icons:
                if icon.is_displayed():
                    return 'paused'

            # Проверяем другие статусы (можно добавить позже)
            return 'active'

        except Exception as e:
            logging.debug(f"Не удалось определить статус матча: {e}")
            return 'active'  # по умолчанию активен


class MatchPageParser:
    """Парсер для страницы конкретного матча"""

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    def load_match_page(self, match_url):
        """Загрузка страницы матча"""
        try:
            # ⚡ УВЕЛИЧИВАЕМ РАЗМЕР ОКНА ДЛЯ СТРАНИЦЫ МАТЧА
            self.driver.set_window_size(1920, 1080)  # или даже 2560, 1440
            # Если URL уже полный - используем как есть
            if match_url.startswith('http'):
                full_url = match_url
            else:
                # Если относительный URL - добавляем домен
                full_url = f"https://fon.bet{match_url}"
            self.driver.get(full_url)

            # Ждем загрузки основных элементов
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '.scoreboard-timer__value--lpnFb')
            ))
            return True
        except Exception as e:
            logging.error(f"Ошибка загрузки страницы матча: {e}")
            return False

    def parse_match_data(self):
        """Парсинг данных со страницы матча"""
        try:
            # Время матча
            time_element = self.driver.find_element(
                By.CSS_SELECTOR, '.scoreboard-timer__value--lpnFb'
            )
            current_time = time_element.text

            # Статус матча (пауза/активен)
            match_status = self._parse_match_status()

            # Общий счет
            score_elements = self.driver.find_elements(
                By.CSS_SELECTOR, '.column--fgNW_._active--jPFnC._bold--Aw_dH'
            )
            team1_score = score_elements[1].find_element(
                By.CSS_SELECTOR, '.column__t1--WCEcc'
            ).text
            team2_score = score_elements[1].find_element(
                By.CSS_SELECTOR, '.column__t2--rn4_E'
            ).text
            total_score = int(team1_score) + int(team2_score)

            # Тотал - ИЗМЕНЕННЫЙ ВЫЗОВ
            total_value = self._parse_total_value()

            return {
                'current_time': current_time,
                'match_status': match_status,
                'score': f"{team1_score}:{team2_score}",
                'total_points': total_score,
                'total_value': total_value,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logging.error(f"Ошибка парсинга страницы матча: {e}")
            return None

    def _parse_match_status(self):
        """Определение статуса матча на странице"""
        try:
            pause_icons = self.driver.find_elements(
                By.CSS_SELECTOR, 'svg[resource-name="timerPaused"]'
            )
            for icon in pause_icons:
                if icon.is_displayed():
                    return 'paused'
            return 'active'
        except:
            return 'active'

    def _parse_total_value(self):
        """Извлечение среднего тотала из списка"""
        try:
            # Ищем все элементы с тоталами
            total_elements = self.driver.find_elements(
                By.XPATH, "//div[contains(@class, 'cell--NEHKQ') and contains(@class, '_align-left--Yc_tL') and contains(text(), 'Тотал')]"
            )
            
            if not total_elements:
                logging.debug("Не найдено элементов с тоталом")
                return None
            
            # Извлекаем числовые значения тоталов
            totals = []
            for element in total_elements:
                text = element.text
                # Парсим "Тотал 168.5" -> 168.5
                match = re.search(r'(\d+\.?\d*)', text)
                if match:
                    totals.append(float(match.group(1)))
            
            if not totals:
                logging.debug("Не удалось извлечь числовые значения тоталов")
                return None
            
            # Берем средний тотал (обычно это основной)
            # Сортируем и берем медиану или среднее значение
            totals.sort()
            
            # Если нечетное количество - берем средний элемент
            if len(totals) % 2 == 1:
                median_total = totals[len(totals) // 2]
            else:
                # Если четное - берем среднее двух центральных
                mid = len(totals) // 2
                median_total = (totals[mid - 1] + totals[mid]) / 2
            
            logging.debug(f"Найдено тоталов: {totals}, выбран средний: {median_total}")
            return median_total
            
        except Exception as e:
            logging.error(f"Ошибка парсинга тотала: {e}")
            return None
