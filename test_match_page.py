import logging
from basketball_parser import BasketballParser, MatchPageParser
import time
from selenium.webdriver.common.by import By
import re

# Настройка логирования
logging.basicConfig(level=logging.INFO)

def test_match_page_parsing():
    """Тестирование парсинга страницы матча"""
    parser = BasketballParser()
    match_parser = None
    
    try:
        print("🚀 Запуск теста парсинга страницы матча...")
        
        # Настраиваем драйвер
        parser.setup_driver()
        
        # Загружаем главную страницу чтобы получить URL матча
        if not parser.load_page():
            print("❌ Не удалось загрузить главную страницу")
            return
            
        # Парсим матчи чтобы получить URL
        matches = parser.parse_matches()
        if not matches:
            print("❌ Не найдено матчей")
            return
            
        # Берем первый матч для теста
        test_match = matches[0]
        match_url = test_match['match_url']
        
        print(f"🔍 Тестируем матч: {test_match['teams']}")
        print(f"📎 URL: {match_url}")
        
        # Создаем парсер страницы матча
        match_parser = MatchPageParser(parser.driver)
        
        # Загружаем страницу матча
        print("🌐 Загружаем страницу матча...")
        if not match_parser.load_match_page(match_url):
            print("❌ Не удалось загрузить страницу матча")
            return
            
        print("✅ Страница матча загружена")
        
        # Парсим данные
        print("📊 Парсим данные со страницы матча...")
        match_data = match_parser.parse_match_data()
        # После парсинга добавь этот код:

        print("\n🔍 ДЕТАЛЬНЫЙ ПОИСК ТОТАЛА:")

        try:
            # 1. Сначала сделаем скриншот чтобы видеть что загрузилось
            match_parser.driver.save_screenshot("match_page_debug.png")
            print("📸 Скриншот сохранен: match_page_debug.png")
            
            # 2. Ищем все элементы с текстом "тотал" или "total"
            all_elements = match_parser.driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ТОТАЛ', 'тотал'), 'тотал') or contains(translate(text(), 'TOTAL', 'total'), 'total')]")
            print(f"🔤 Найдено элементов с 'тотал/total': {len(all_elements)}")
            
            for i, elem in enumerate(all_elements):
                print(f"  {i}: '{elem.text}' (класс: {elem.get_attribute('class')})")
            
            # 3. Ищем все элементы с числами (возможные тоталы)
            number_elements = match_parser.driver.find_elements(By.XPATH, "//*[contains(text(), '.')]")
            print(f"🔢 Найдено элементов с точками: {len(number_elements)}")
            
            for i, elem in enumerate(number_elements[:10]):  # первые 10
                text = elem.text.strip()
                if text and any(c.isdigit() for c in text):
                    print(f"  {i}: '{text}' (класс: {elem.get_attribute('class')})")
            
            # 4. Ищем в определенных блоках
            blocks = [
                '.sport-base-event--W4qkO',
                '.table-component-factor-value_single--TOTnW', 
                '.table-component-factor-value_param--M33Ul',
                '.table-component-factor-value_complex--HFX8T'
            ]
            
            for block in blocks:
                elements = match_parser.driver.find_elements(By.CSS_SELECTOR, block)
                print(f"📦 Блок '{block}': {len(elements)} элементов")
                for i, elem in enumerate(elements):
                    if elem.text.strip():
                        print(f"  {i}: '{elem.text}'")

        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")        
        if match_data:
            print("\n🎯 РЕЗУЛЬТАТЫ ПАРСИНГА:")
            print(f"⏱️  Время матча: {match_data['current_time']}")
            print(f"🎯 Статус: {match_data['match_status']}")
            print(f"📊 Счет: {match_data['score']}")
            print(f"🏀 Всего очков: {match_data['total_points']}")
            print(f"📈 Тотал: {match_data['total_value']}")
            print(f"🕒 Время парсинга: {match_data['timestamp']}")
            
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if parser.driver:
            parser.close_driver()

if __name__ == "__main__":
    test_match_page_parsing()