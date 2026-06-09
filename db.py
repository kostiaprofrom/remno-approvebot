import aiosqlite
import os
import logging
from typing import Any
from datetime import datetime, timedelta, timezone

# Настройка локального логгера для модуля базы данных
logger = logging.getLogger(__name__)


async def init_db(db_path: str) -> None:
    # Инициализация структуры таблиц базы данных и проверка миграций
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    logger.info(f"Инициализация базы данных: {db_path}")

    try:
        async with aiosqlite.connect(db_path) as db:
            # Таблица пользователей бота
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    access_granted INTEGER DEFAULT 0,
                    access_code_used TEXT,
                    remnawave_user_uuid TEXT,
                    subscription_url TEXT,
                    subscription_expires_at TEXT,
                    last_menu_message_id INTEGER,
                    referred_by INTEGER DEFAULT NULL
                )
            """)

            # Таблица заявок на оплату тарифов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    tariff_code TEXT NOT NULL,
                    tariff_days INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    screenshot_file_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    processed_at TEXT,
                    processed_by INTEGER
                )
            """)

            # Таблица отправленных напоминаний
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    reminder_type TEXT NOT NULL,
                    reminder_key TEXT NOT NULL,
                    sent_at TEXT NOT NULL
                )
            """)

            # Индексы для ускорения выборок шедулером и реферальной системой
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_reminders_lookup
                ON reminders (telegram_id, reminder_type, reminder_key)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_referred_by
                ON users (referred_by)
            """)

            # Проверка необходимости добавления новых колонок в старых БД
            columns = await _get_table_columns(db, "users")
            
            if "last_menu_message_id" not in columns:
                logger.info("Миграция: Добавление колонки last_menu_message_id в таблицу users")
                await db.execute("ALTER TABLE users ADD COLUMN last_menu_message_id INTEGER")
                
            if "referred_by" not in columns:
                logger.info("Миграция: Добавление колонки referred_by в таблицу users")
                await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL")

            await db.commit()
            logger.info("База данных успешно инициализирована и проверена.")
    except Exception:
        logger.exception("Критическая ошибка при инициализации базы данных")
        raise


async def _get_table_columns(db: aiosqlite.Connection, table_name: str) -> set[str]:
    # Вспомогательная функция получения списка колонок таблицы
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    rows = await cursor.fetchall()
    return {row[1] for row in rows}


async def create_or_update_user(
    db_path: str,
    telegram_id: int,
    username: str | None,
    full_name: str | None,
    referred_by: int | None = None,
    last_menu_message_id: int | None = None,
    subscription_expires_at: str | None = None,
    subscription_url: str | None = None,
) -> dict[str, Any]:
    # Создание нового или обновление параметров существующего пользователя
    if referred_by and int(telegram_id) == int(referred_by):
        referred_by = None

    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,))
            exists = await cursor.fetchone()

            if exists:
                # Динамическая сборка полей для обновления
                updates = []
                params = []
                
                if username is not None: updates.append("username = ?"); params.append(username)
                if full_name is not None: updates.append("full_name = ?"); params.append(full_name)
                if last_menu_message_id is not None: updates.append("last_menu_message_id = ?"); params.append(last_menu_message_id)
                if subscription_expires_at is not None: updates.append("subscription_expires_at = ?"); params.append(subscription_expires_at)
                if subscription_url is not None: updates.append("subscription_url = ?"); params.append(subscription_url)
                
                if updates:
                    params.append(telegram_id)
                    query = f"UPDATE users SET {', '.join(updates)} WHERE telegram_id = ?"
                    await db.execute(query, tuple(params))
            else:
                # Создание новой записи, если пользователя нет в базе
                await db.execute("""
                    INSERT INTO users (telegram_id, username, full_name, referred_by)
                    VALUES (?, ?, ?, ?)
                """, (telegram_id, username, full_name, referred_by))
                
            await db.commit()
            
        return await get_user(db_path, telegram_id)
    except Exception:
        logger.exception(f"Ошибка при создании/обновлении пользователя {telegram_id}")
        raise


async def get_user(db_path: str, telegram_id: int) -> dict[str, Any] | None:
    # Получение профиля пользователя в виде словаря
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    except Exception:
        logger.exception(f"Ошибка при получении пользователя {telegram_id}")
        return None


async def grant_access(
    db_path: str,
    telegram_id: int,
    code_used: str,
    remnawave_user_uuid: str | None = None,
    subscription_url: str | None = None,
    subscription_expires_at: str | None = None,
) -> None:
    # Фиксация предоставления/активации доступа пользователю в БД
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                UPDATE users
                SET access_granted = 1,
                    access_code_used = ?,
                    remnawave_user_uuid = COALESCE(?, remnawave_user_uuid),
                    subscription_url = COALESCE(?, subscription_url),
                    subscription_expires_at = COALESCE(?, subscription_expires_at)
                WHERE telegram_id = ?
            """, (code_used, remnawave_user_uuid, subscription_url, subscription_expires_at, telegram_id))
            await db.commit()
    except Exception:
        logger.exception(f"Ошибка при grant_access для {telegram_id}")
        raise


async def toggle_user_access(db_path: str, telegram_id: int, access_granted: int) -> None:
    # Принудительное изменение статуса доступа администратором (0 или 1)
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                UPDATE users
                SET access_granted = ?
                WHERE telegram_id = ?
            """, (access_granted, telegram_id))
            await db.commit()
    except Exception:
        logger.exception(f"Ошибка при изменении доступа пользователя {telegram_id}")
        raise


async def count_users_by_access(db_path: str, access_value: int) -> int:
    # Подсчет количества пользователей по фильтру доступа (-1 означает выборку всех)
    try:
        async with aiosqlite.connect(db_path) as db:
            if access_value == -1:
                cursor = await db.execute("SELECT COUNT(*) FROM users")
            else:
                cursor = await db.execute("SELECT COUNT(*) FROM users WHERE access_granted = ?", (access_value,))
            row = await cursor.fetchone()
            return int(row[0]) if row else 0
    except Exception:
        logger.exception("Ошибка при подсчете пользователей")
        return 0


async def get_paginated_users_by_access(
    db_path: str,
    access_value: int,
    page: int,
    per_page: int,
) -> list[dict[str, Any]]:
    # Вывод постраничного списка пользователей для админ-панели
    offset = (page - 1) * per_page
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            if access_value == -1:
                cursor = await db.execute("SELECT * FROM users ORDER BY telegram_id DESC LIMIT ? OFFSET ?", (per_page, offset))
            else:
                cursor = await db.execute("""
                    SELECT * FROM users WHERE access_granted = ? 
                    ORDER BY telegram_id DESC LIMIT ? OFFSET ?
                """, (access_value, per_page, offset))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Ошибка при пагинации списка пользователей")
        return []


async def create_payment_request(
    db_path: str,
    telegram_id: int,
    tariff_code: str,
    tariff_days: int,
    amount: int,
    screenshot_file_id: str,
    created_at: str,
) -> int:
    # Сохранение новой заявки на покупку/продление во время ожидания чека
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("""
                INSERT INTO requests (
                    telegram_id, tariff_code, tariff_days, amount, screenshot_file_id, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """, (telegram_id, tariff_code, tariff_days, amount, screenshot_file_id, created_at))
            await db.commit()
            return cursor.lastrowid
    except Exception:
        logger.exception(f"Ошибка сохранения заявки на оплату от {telegram_id}")
        raise


async def get_request_by_id(db_path: str, request_id: int) -> dict[str, Any] | None:
    # Поиск заявки по ее идентификатору
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    except Exception:
        logger.exception(f"Ошибка при получении заявки {request_id}")
        return None


async def update_request_status(
    db_path: str,
    request_id: int,
    status: str,
    processed_at: str,
    processed_by: int,
) -> None:
    # Смена статуса заявки (approved/rejected) после решения администратора
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                UPDATE requests
                SET status = ?, processed_at = ?, processed_by = ?
                WHERE id = ?
            """, (status, processed_at, processed_by, request_id))
            await db.commit()
    except Exception:
        logger.exception(f"Ошибка при обновлении статуса заявки {request_id}")
        raise


async def get_pending_requests(db_path: str) -> list[dict[str, Any]]:
    # Выборка всех необработанных заявок для админки
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM requests WHERE status = 'pending' ORDER BY id ASC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Ошибка получения списка необработанных заявок")
        return []


async def get_all_active_users_for_reminder(db_path: str) -> list[dict[str, Any]]:
    # Получение списка пользователей с активным доступом для планировщика уведомлений
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE access_granted = 1")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Ошибка получения списка пользователей для шедулера напоминаний")
        return []


async def mark_expiry_reminder_sent_by_type(
    db_path: str,
    telegram_id: int,
    reminder_type: str,
    reminder_key: str,
) -> None:
    # Запись факта отправки конкретного уведомления, чтобы избежать дублей
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                INSERT INTO reminders (telegram_id, reminder_type, reminder_key, sent_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (telegram_id, reminder_type, reminder_key))
            await db.commit()
    except Exception:
        logger.exception(f"Ошибка отметки отправленного напоминания для {telegram_id}")


async def process_referral_on_access_grant(db_path: str, new_user_id: int, bonus_days: int) -> int | None:
    # Начисление бонусных дней пригласившему пользователю, если у реферала первый успешный доступ
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT referred_by FROM users WHERE telegram_id = ?", (new_user_id,))
            row = await cursor.fetchone()
            
            if not row or row[0] is None:
                return None  
                
            referrer_id = row[0]
            
            cursor = await db.execute("SELECT subscription_expires_at FROM users WHERE telegram_id = ?", (referrer_id,))
            ref_row = await cursor.fetchone()
            
            now = datetime.now(timezone.utc)
            
            if ref_row and ref_row[0]:
                try:
                    s = str(ref_row[0]).replace("Z", "+00:00")
                    current_expiry = datetime.fromisoformat(s)
                    
                    if current_expiry > now:
                        new_expiry = current_expiry + timedelta(days=bonus_days)
                    else:
                        new_expiry = now + timedelta(days=bonus_days)
                except Exception:
                    new_expiry = now + timedelta(days=bonus_days)
            else:
                new_expiry = now + timedelta(days=bonus_days)
                
            new_expiry_str = new_expiry.isoformat().replace("+00:00", "Z")
            
            await db.execute("""
                UPDATE users 
                SET subscription_expires_at = ? 
                WHERE telegram_id = ?
            """, (new_expiry_str, referrer_id))
            
            await db.commit()
            logger.info(f"Реферальный бонус: Пригласителю {referrer_id} начислено {bonus_days} дней. Новая дата: {new_expiry_str}")
            return referrer_id
    except Exception:
        logger.exception(f"Ошибка при начислении реферального бонуса пригласителю за пользователя {new_user_id}")
        return None