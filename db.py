import aiosqlite
import os
from typing import Any
from datetime import datetime, timedelta, timezone


async def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                reminder_type TEXT NOT NULL,
                reminder_key TEXT NOT NULL,
                sent_at TEXT NOT NULL
            )
        """)

        # Существующий индекс для напоминаний
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_lookup
            ON reminders (telegram_id, reminder_type, reminder_key)
        """)

        # Новый индекс для ускорения счётчика рефералов
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_referred_by
            ON users (referred_by)
        """)

        # Проверка и динамическое добавление колонок, если база данных уже существовала
        columns = await _get_table_columns(db, "users")
        
        if "last_menu_message_id" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN last_menu_message_id INTEGER")
            
        if "referred_by" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL")

        await db.commit()


async def _get_table_columns(db: aiosqlite.Connection, table_name: str) -> set[str]:
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    rows = await cursor.fetchall()
    return {row[1] for row in rows}


async def create_or_update_user(
    db_path: str,
    telegram_id: int,
    username: str | None,
    full_name: str | None,
    referred_by: int | None = None,
) -> None:
    # Защита: нельзя быть рефералом самого себя
    if referred_by and int(telegram_id) == int(referred_by):
        referred_by = None

    async with aiosqlite.connect(db_path) as db:
        # 1. Проверяем, существует ли уже пользователь
        cursor = await db.execute("SELECT referred_by FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()

        if row:
            # Пользователь существует: обновляем только юзернейм и имя. Реферера НЕ трогаем!
            await db.execute("""
                UPDATE users 
                SET username = ?, full_name = ? 
                WHERE telegram_id = ?
            """, (username, full_name, telegram_id))
        else:
            # Пользователь новый: создаем запись сразу с реферером
            await db.execute("""
                INSERT INTO users (telegram_id, username, full_name, referred_by)
                VALUES (?, ?, ?, ?)
            """, (telegram_id, username, full_name, referred_by))
            
        await db.commit()


async def get_user(db_path: str, telegram_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def grant_access(db_path: str, telegram_id: int, access_code: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            UPDATE users
            SET access_granted = 1,
                access_code_used = ?
            WHERE telegram_id = ?
        """, (access_code, telegram_id))
        await db.commit()


async def set_user_access(db_path: str, telegram_id: int, access_granted: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            UPDATE users
            SET access_granted = ?
            WHERE telegram_id = ?
        """, (access_granted, telegram_id))
        await db.commit()


async def count_users_by_access(db_path: str, access_value: int) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE access_granted = ?",
            (access_value,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def get_users_by_access_paginated(
    db_path: str,
    access_value: int,
    page: int,
    per_page: int,
) -> list[dict[str, Any]]:
    offset = (page - 1) * per_page

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT *
            FROM users
            WHERE access_granted = ?
            ORDER BY telegram_id DESC
            LIMIT ? OFFSET ?
        """, (access_value, per_page, offset))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def create_payment_request(
    db_path: str,
    telegram_id: int,
    tariff_code: str,
    tariff_days: int,
    amount: int,
    screenshot_file_id: str,
    created_at: str,
) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("""
            INSERT INTO requests (
                telegram_id,
                tariff_code,
                tariff_days,
                amount,
                screenshot_file_id,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (
            telegram_id,
            tariff_code,
            tariff_days,
            amount,
            screenshot_file_id,
            created_at,
        ))
        await db.commit()
        return cursor.lastrowid


async def get_request_by_id(db_path: str, request_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM requests WHERE id = ?",
            (request_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_request_status(
    db_path: str,
    request_id: int,
    status: str,
    processed_at: str,
    processed_by: int,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            UPDATE requests
            SET status = ?,
                processed_at = ?,
                processed_by = ?
            WHERE id = ?
        """, (status, processed_at, processed_by, request_id))
        await db.commit()


async def set_user_subscription_data(
    db_path: str,
    telegram_id: int,
    remnawave_user_uuid: str | None,
    subscription_url: str | None,
    subscription_expires_at: str | None,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            UPDATE users
            SET remnawave_user_uuid = ?,
                subscription_url = ?,
                subscription_expires_at = ?
            WHERE telegram_id = ?
        """, (
            remnawave_user_uuid,
            subscription_url,
            subscription_expires_at,
            telegram_id,
        ))
        await db.commit()


async def clear_user_subscription_data(db_path: str, telegram_id: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            UPDATE users
            SET remnawave_user_uuid = NULL,
                subscription_url = NULL,
                subscription_expires_at = NULL
            WHERE telegram_id = ?
        """, (telegram_id,))
        await db.commit()


async def get_last_menu_message_id(db_path: str, telegram_id: int) -> int | None:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT last_menu_message_id FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None


async def set_last_menu_message_id(db_path: str, telegram_id: int, message_id: int | None) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            UPDATE users
            SET last_menu_message_id = ?
            WHERE telegram_id = ?
        """, (message_id, telegram_id))
        await db.commit()


async def get_users_for_reminder_check(db_path: str) -> list[dict[str, Any]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM users
            WHERE access_granted = 1
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def was_expiry_reminder_sent_by_type(
    db_path: str,
    telegram_id: int,
    reminder_type: str,
    reminder_key: str,
) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("""
            SELECT 1
            FROM reminders
            WHERE telegram_id = ?
              AND reminder_type = ?
              AND reminder_key = ?
            LIMIT 1
        """, (telegram_id, reminder_type, reminder_key))
        row = await cursor.fetchone()
        return row is not None


async def mark_expiry_reminder_sent_by_type(
    db_path: str,
    telegram_id: int,
    reminder_type: str,
    reminder_key: str,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO reminders (telegram_id, reminder_type, reminder_key, sent_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (telegram_id, reminder_type, reminder_key))
        await db.commit()


async def set_referrer(db_path: str, telegram_id: int, referrer_id: int) -> bool:
    if telegram_id == referrer_id:
        return False  
        
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT referred_by, access_granted FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        
        if not row:
            await db.execute(
                "INSERT INTO users (telegram_id, referred_by) VALUES (?, ?)",
                (telegram_id, referrer_id)
            )
            await db.commit()
            return True
        
        if row[0] is None and row[1] == 0:
            await db.execute(
                "UPDATE users SET referred_by = ? WHERE telegram_id = ?", 
                (referrer_id, telegram_id)
            )
            await db.commit()
            return True
            
    return False


async def get_referrer_id(db_path: str, telegram_id: int) -> int | None:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT referred_by FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def count_referred_users(db_path: str, telegram_id: int) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def reward_referrer_if_exists(db_path: str, new_user_id: int, bonus_days: int) -> int | None:
    """
    Проверяет, есть ли у пользователя пригласитель. 
    Если есть, начисляет ему бонусные дни в базе данных.
    Возвращает telegram_id пригласителя для отправки уведомления.
    """
    async with aiosqlite.connect(db_path) as db:
        # 1. Ищем, кто пригласил этого пользователя
        cursor = await db.execute("SELECT referred_by FROM users WHERE telegram_id = ?", (new_user_id,))
        row = await cursor.fetchone()
        
        if not row or row[0] is None:
            return None  # Пригласителя нет
            
        referrer_id = row[0]
        
        # 2. Получаем текущую подписку пригласителя
        cursor = await db.execute("SELECT subscription_expires_at FROM users WHERE telegram_id = ?", (referrer_id,))
        ref_row = await cursor.fetchone()
        
        now = datetime.now(timezone.utc)
        
        if ref_row and ref_row[0]:
            try:
                # Парсим дату (заменяем Z на +00:00 для корректной работы isoformat)
                s = str(ref_row[0]).replace("Z", "+00:00")
                current_expiry = datetime.fromisoformat(s)
                
                # Если подписка еще активна — прибавляем к ней, если истекла — от текущего момента
                if current_expiry > now:
                    new_expiry = current_expiry + timedelta(days=bonus_days)
                else:
                    new_expiry = now + timedelta(days=bonus_days)
            except Exception:
                new_expiry = now + timedelta(days=bonus_days)
        else:
            new_expiry = now + timedelta(days=bonus_days)
            
        # Форматируем обратно для хранения в БД
        new_expiry_str = new_expiry.isoformat().replace("+00:00", "Z")
        
        # 3. Обновляем дату подписки пригласителя в базе данных
        await db.execute("""
            UPDATE users 
            SET subscription_expires_at = ? 
            WHERE telegram_id = ?
        """, (new_expiry_str, referrer_id))
        
        await db.commit()
        return referrer_id