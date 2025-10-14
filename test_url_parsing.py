import logging
from basketball_parser import BasketballParser

# Настройка логирования для отладки
logging.basicConfig(level=logging.DEBUG)

def test_url_parsing():
    """Тестирование парсинга URL матчей"""
    parser = BasketballParser()
    
    try:
        print("🚀 Запуск теста парсинга URL...")
        
        # Настраиваем драйвер
        parser.setup_driver()
        
        # Загружаем страницу
        if not parser.load_page():
            print("❌ Не удалось загрузить страницу")
            return
            
        # Парсим матчи
        matches = parser.parse_matches()
        
        print(f"📊 Найдено матчей: {len(matches)}")
        
        # Выводим информацию о каждом матче
        for i, match in enumerate(matches, 1):
            print(f"\n--- Матч #{i} ---")
            print(f"Команды: {match['teams']}")
            print(f"Турнир: {match['tournament']}")
            print(f"URL: {match.get('match_url', 'НЕТ URL')}")
            print(f"Статус: {match.get('match_status', 'unknown')}")
            print(f"Счет: {match['score']}")
            print(f"Тотал: {match['total']}")
            
        print(f"\n✅ Тест завершен. Обработано матчей: {len(matches)}")
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
    finally:
        parser.close_driver()

if __name__ == "__main__":
    test_url_parsing()