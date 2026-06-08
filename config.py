from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Tariff:
    code: str
    title: str
    months: int
    days: int
    price: int


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0").strip())
ACCESS_CODE = os.getenv("ACCESS_CODE", "").strip()

CHAT_LINK = os.getenv("CHAT_LINK", "").strip()
PAYMENT_LINK = os.getenv("PAYMENT_LINK", "").strip()

REMNAWAVE_BASE_URL = os.getenv("REMNAWAVE_BASE_URL", "").strip()
REMNAWAVE_TOKEN = os.getenv("REMNAWAVE_TOKEN", "").strip()

DB_PATH = "data/bot.db"

HERO_IMAGE_PATH = os.getenv("HERO_IMAGE_PATH", "assets/main_menu.jpg").strip()
WELCOME_IMAGE_PATH = os.getenv("WELCOME_IMAGE_PATH", "assets/welcome.jpg").strip()

REMIDER_CHECK_INTERVAL_SECONDS = int(
    os.getenv("REMINDER_CHECK_INTERVAL_SECONDS", "3600").strip()
)

ADMIN_USERS_PER_PAGE = int(
    os.getenv("ADMIN_USERS_PER_PAGE", "8").strip()
)

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
        price=int(os.getenv("PRICE_6", "2700")),
    ),
    "12m": Tariff(
        code="12m",
        title="12 месяцев",
        months=12,
        days=360,
        price=int(os.getenv("PRICE_12", "5000")),
    ),
}

# Количество бонусных дней за привлеченного друга
REFERRAL_BONUS_DAYS = int(os.getenv("REFERRAL_BONUS_DAYS", "7").strip())
