import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Tariff:
    code: str
    title: str
    months: int
    days: int
    price: int

# Основные параметры авторизации бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0").strip())
ACCESS_CODE = os.getenv("ACCESS_CODE", "").strip()

# Ссылки на внешние ресурсы
CHAT_LINK = os.getenv("CHAT_LINK", "").strip()
PAYMENT_LINK = os.getenv("PAYMENT_LINK", "").strip()

# Параметры интеграции с панелью Remnawave
REMNAWAVE_BASE_URL = os.getenv("REMNAWAVE_BASE_URL", "").strip()
REMNAWAVE_TOKEN = os.getenv("REMNAWAVE_TOKEN", "").strip()
REMNAWAVE_DEFAULT_SQUAD_UUID = os.getenv("REMNAWAVE_DEFAULT_SQUAD_UUID", "").strip()

# Путь к локальной базе данных SQLite
DB_PATH = "data/bot.db"

# Пути к медиа-файлам интерфейса
HERO_IMAGE_PATH = os.getenv("HERO_IMAGE_PATH", "assets/main_menu.jpg").strip()
WELCOME_IMAGE_PATH = os.getenv("WELCOME_IMAGE_PATH", "assets/welcome.jpg").strip()

# Интервал проверки подписок для планировщика (в секундах)
REMINDER_CHECK_INTERVAL_SECONDS = int(os.getenv("REMINDER_CHECK_INTERVAL_SECONDS", "3600").strip())
# Сохраняем алиас с опечаткой для обратной совместимости с текущим app.py
REMIDER_CHECK_INTERVAL_SECONDS = REMINDER_CHECK_INTERVAL_SECONDS

# Количество пользователей на одной странице в админ-панели
ADMIN_USERS_PER_PAGE = int(os.getenv("ADMIN_USERS_PER_PAGE", "8").strip())

# Бонусные дни за успешную рекомендацию
REFERRAL_BONUS_DAYS = int(os.getenv("REFERRAL_BONUS_DAYS", "5").strip())

# Сетка доступных тарифных планов
TARIFFS = {
    "1m": Tariff(
        code="1m",
        title="1 месяц",
        months=1,
        days=30,
        price=int(os.getenv("PRICE_1", "500")),
    ),
    "3m": Tariff(
        code="3m",
        title="3 месяца",
        months=3,
        days=90,
        price=int(os.getenv("PRICE_3", "1400")),
    ),
    "6m": Tariff(
        code="6m",
        title="6 месяцев",
        months=6,
        days=180,
        price=int(os.getenv("PRICE_6", "2600")),
    ),
    "12m": Tariff(
        code="12m",
        title="12 месяцев",
        months=12,
        days=365,
        price=int(os.getenv("PRICE_12", "4800")),
    ),
}
# Настройки пробного периода (Trial)
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "3").strip())
TRIAL_BUTTON_ENABLED = os.getenv("TRIAL_BUTTON_ENABLED", "False").strip().lower() == "true"
# Настройки кнопки поддержки
SUPPORT_LINK = os.getenv("SUPPORT_LINK", "").strip()
SUPPORT_BUTTON_ENABLED = os.getenv("SUPPORT_BUTTON_ENABLED", "False").strip().lower() == "true"
# Настройка доступности реферальной программы
REFERRAL_REQUIRE_PAYMENT = os.getenv("REFERRAL_REQUIRE_PAYMENT", "True").strip().lower() == "true"