# config.py
"""
Конфигурация парсера баскетбольных матчей
"""

# Настройки парсера
PARSER_CONFIG = {
    'REFRESH_INTERVAL': 5,           # секунды между обновлениями
    'PAGE_LOAD_TIMEOUT': 15,          # секунды на загрузку страницы
    'MAX_RETRIES': 2,                 # попытки переподключения при ошибках
    'RETRY_DELAY': 5,                 # секунды между попытками
}

# Настройки браузера
BROWSER_CONFIG = {
    'HEADLESS': True,                 # без GUI для скорости
    'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'WINDOW_SIZE': '1920,1080',
    'DISABLE_LOGS': True,             # отключить логи браузера
    'SCALE_FACTOR': 0.5
}

# Настройки сайта
SITE_CONFIG = {
    'URL': 'https://fon.bet/live/basketball',
    'MATCH_CONTAINER': '.sport-base-event--W4qkO',
    'TEAMS_SELECTOR': '.sport-event__name--YAs00',
    'TIME_SELECTOR': '.event-block-current-time__time--VEuoj',
    'SCORE_SELECTOR': '.event-block-score__score--r0ZU9',
    'ODDS_SELECTOR': '.table-component-factor-value_single--TOTnW',
    'TOTAL_SELECTOR': '.table-component-factor-value_param--M33Ul .param--qbIN_',
    'UNDER_OVER_SELECTOR': '.table-component-factor-value_complex--HFX8T',
    'TOURNAMENT_CONTAINER': '.sport-competition--Xt2wb',
    'TOURNAMENT_SELECTOR': '.table-component-text--Tjj3g',
}

# Настройки БД
DATABASE_CONFIG = {
    'DB_PATH': 'basketball.db',
    'BACKUP_INTERVAL': 3600,          # секунды между бэкапами
}

# Настройки фильтрации матчей
MATCH_FILTERS = {
    'EXCLUDE_2X10': True,             # исключать матчи 2x10
    'EXCLUDE_WOMEN': False,           # исключать женские матчи (кроме (ж))
    # минимальное время матча для анализа (минуты)
    'MIN_TIME_ELAPSED': 2,
}

MATCH_TIME_CONFIG = {
    # Турниры с форматом 4x12 (48 минут)
    'NBA': 48,
    'CDBL': 48,  # Китайская лига
    'WCBA': 48,  # Женская китайская лига
    'PBA': 48,   # Филиппины
    'Prime Division': 48,

    # Турниры с форматом 4x10 (40 минут)
    'WNBA': 40,
    'Euroleague': 40,
    'Eurocup': 40,
    'VTB': 40,   # Единая лига ВТБ
    'IPBL': 40,  # Российская IPBL
    'Superleague': 40,  # Греческая лига
    'ACB': 40,   # Испанская лига
    'LNB': 40,   # Французская лига
    'Legabasket': 40,  # Итальянская лига

    # Стандарт по умолчанию (если не нашли в списке)
    'DEFAULT_TIME': 40
}

STRATEGY_CONFIG = {
    'DEVIATION_THRESHOLD': 5,      # Порог отклонения тотала для первого сигнала (%)
    'PACE_REVERSAL_CONFIRMATIONS': 2,  # Количество подтверждений разворота темпа
    'MIN_MATCH_PROGRESS': 15,      # Минимальный прогресс матча для анализа (%)
    'MAX_MATCH_PROGRESS': 85,      # Максимальный прогресс матча для анализа (%)
}