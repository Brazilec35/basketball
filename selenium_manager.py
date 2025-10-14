"""
Менеджер для управления переиспользуемым Selenium драйвером
"""
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


class SeleniumManager:
    """Singleton для управления переиспользуемым Selenium драйвером"""
    
    _instance = None
    _driver = None
    _is_initialized = False
    _last_activity = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_driver(self):
        """Получение или создание драйвера"""
        if not self._is_initialized or not self._health_check():
            self._initialize_driver()
        
        self._last_activity = time.time()
        return self._driver
    
    def _initialize_driver(self):
        """Инициализация драйвера с настройками"""
        try:
            logging.info("🚀 Инициализация Selenium драйвера...")
            
            # Закрываем старый драйвер если есть
            if self._driver:
                try:
                    self._driver.quit()
                except:
                    pass
            
            options = Options()
            
            # ОСНОВНЫЕ НАСТРОЙКИ
            options.add_argument('--headless')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            
            # ВАЖНО: предотвращаем автоматическое закрытие
            options.add_experimental_option("detach", True)  # Не закрывать браузер
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            
            # Размер окна
            options.add_argument('--window-size=1920,1080')
            
            # User Agent
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            self._driver = webdriver.Chrome(options=options)
            
            # ОТКРЫВАЕМ ПУСТУЮ СТРАНИЦУ чтобы браузер не закрывался
            self._driver.get("about:blank")
            
            self._is_initialized = True
            self._last_activity = time.time()
            logging.info("✅ Selenium драйвер успешно инициализирован")
            
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации Selenium драйвера: {e}")
            raise
    
    def _health_check(self):
        """Проверка работоспособности драйвера"""
        try:
            if not self._driver:
                return False
            
            # Простая проверка - драйвер отвечает
            return self._driver.current_url is not None
            
        except Exception:
            return False
    
    def _keep_alive(self):
        """Поддержание активности драйвера"""
        try:
            # Если драйвер бездействовал больше 30 секунд - обновляем страницу
            if (self._last_activity and 
                time.time() - self._last_activity > 30 and 
                self._driver):
                
                current_url = self._driver.current_url
                if current_url and current_url != "about:blank":
                    # Возвращаемся на текущую страницу чтобы поддерживать сессию
                    self._driver.get(current_url)
                else:
                    # Или обновляем about:blank
                    self._driver.get("about:blank")
                
                self._last_activity = time.time()
                logging.debug("🔁 Keep-alive: обновлена страница")
                
        except Exception as e:
            logging.warning(f"⚠️ Keep-alive ошибка: {e}")
    
    def parse_match_page(self, match_url):
        """Парсинг страницы матча с использованием существующего драйвера"""
        try:
            logging.info(f"🌐 Начинаем парсинг: {match_url}")
            
            driver = self.get_driver()
            
            # Сохраняем текущую вкладку
            original_window = driver.current_window_handle
            
            # Создаем новую вкладку для парсинга
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            
            try:
                # Загружаем страницу матча
                driver.get(match_url)
                
                # Ждем загрузки основных элементов
                wait = WebDriverWait(driver, 10)
                wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '.scoreboard-timer__value--lpnFb')
                ))
                
                # Даем время на полную загрузку
                time.sleep(1)
                
                # Используем MatchPageParser для парсинга
                from basketball_parser import MatchPageParser
                parser = MatchPageParser(driver)
                match_data = parser.parse_match_data()
                
                return match_data
                
            finally:
                # Закрываем вкладку и возвращаемся к исходной
                driver.close()
                driver.switch_to.window(original_window)
                
                # Вызываем keep-alive после операции
                self._keep_alive()
                
        except Exception as e:
            logging.error(f"❌ Ошибка парсинга: {e}")
            
            # При критических ошибках перезапускаем драйвер
            if "invalid session id" in str(e).lower():
                logging.warning("🔄 Обнаружена критическая ошибка сессии, перезапускаем драйвер...")
                self._initialize_driver()
            
            return None


# Глобальный экземпляр менеджера
selenium_manager = SeleniumManager()
