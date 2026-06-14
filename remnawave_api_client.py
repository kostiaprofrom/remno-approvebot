from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from html import escape
import aiohttp

logger = logging.getLogger(__name__)

class RemnawaveException(Exception):
    """Базовое исключение для нашего клиента."""
    pass

class RemnawaveAPIError(RemnawaveException):
    """Ошибка, возвращенная самой панелью (код ответа >= 400)."""
    pass


class RemnawaveClient:
    """Enterprise-клиент для интеграции с API панели управления Remnawave."""

    def __init__(
        self,
        base_url: str,
        token: str,
        default_squad_uuid: str | None = None,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.default_squad_uuid = (default_squad_uuid or "").strip() or None
        self.verify_ssl = verify_ssl
        
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()  # Защита от Race Condition при создании сессии

    async def get_session(self) -> aiohttp.ClientSession:
        """Возвращает существующую сессию или атомарно создает новую."""
        if self._session is None or self._session.closed:
            async with self._lock:
                # Повторная проверка внутри лока (Double-checked locking pattern)
                if self._session is None or self._session.closed:
                    timeout = aiohttp.ClientTimeout(total=30)
                    self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Закрывает HTTP-сессию при завершении работы бота."""
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def build_username(telegram_id: int, telegram_username: str | None) -> str:
        """Формирует валидное имя пользователя для панели Remnawave."""
        if telegram_username:
            value = telegram_username.strip().lstrip("@").lower()
            cleaned = [ch if ch.isalnum() or ch in ("_", "-", ".") else "_" for ch in value]
            username = "".join(cleaned).strip("._-")
            if username:
                return username
        return f"tg_{telegram_id}"

    @staticmethod
    def _dt_to_iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    @staticmethod
    def _extract_data(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        for key in ("response", "data", "result", "user"):
            if key in payload:
                return payload[key]
        return payload

    @staticmethod
    def _extract_user_uuid(user_obj: Any) -> str | None:
        if isinstance(user_obj, dict):
            return user_obj.get("uuid") or user_obj.get("id")
        return None

    @staticmethod
    def _extract_subscription_url(user_obj: Any) -> str | None:
        if not isinstance(user_obj, dict):
            return None
        for key in ("subscription_url", "subscriptionUrl", "subscription", "url"):
            value = user_obj.get(key)
            if value:
                return value
        return None

    @staticmethod
    def _extract_expire_at(user_obj: Any) -> datetime | None:
        if not isinstance(user_obj, dict):
            return None
        return RemnawaveClient._parse_dt(user_obj.get("expire_at") or user_obj.get("expireAt"))

    def extract_user_uuid(self, user_obj: Any) -> str | None:
        return self._extract_user_uuid(user_obj)

    def extract_subscription_url(self, user_obj: Any) -> str | None:
        return self._extract_subscription_url(user_obj)

    def extract_expire_at_iso(self, user_obj: Any) -> str | None:
        dt = self._extract_expire_at(user_obj)
        return self._dt_to_iso(dt) if dt else None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        logger.debug(f"HTTP Запрос: {method} {url}")

        session = await self.get_session()
        
        try:
            async with session.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json_data,
                params=params,
                ssl=self.verify_ssl,
            ) as response:
                
                if response.status == 404:
                    logger.debug(f"HTTP Ресурс не найден (404): {url}")
                    return {"_http_status": 404}

                text = await response.text()
                logger.debug(f"HTTP Статус ответа: {response.status} | Тело (300 симв.): {text[:300]}")

                try:
                    parsed = await response.json(content_type=None)
                except Exception:
                    parsed = {"_raw_text": text}

                if response.status >= 400:
                    error_msg = f"HTTP Error {response.status} | URL: {url} | Response: {parsed}"
                    logger.error(error_msg)
                    raise RemnawaveAPIError(error_msg)  # Используем кастомный класс

                return parsed
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при запросе к Remnawave API ({url}): {e}")
            raise RemnawaveException(f"Remnawave API недоступно: {e}")

    async def get_internal_squad_by_uuid(self, squad_uuid: str) -> dict[str, Any] | None:
        response = await self._request("GET", f"/api/internal-squads/{squad_uuid}")
        if isinstance(response, dict) and response.get("_http_status") == 404:
            logger.warning(f"Внутренний сквад с UUID {squad_uuid} не найден на сервере (404).")
            return None
        data = self._extract_data(response)
        return data if isinstance(data, dict) else None

    async def verify_default_internal_squad(self) -> None:
        if not self.default_squad_uuid:
            logger.info("Дефолтный UUID сквада не задан в конфигурации. Проверка пропущена.")
            return
        squad = await self.get_internal_squad_by_uuid(self.default_squad_uuid)
        if squad is None:
            error_msg = f"Критическая ошибка: Дефолтный сквад с UUID {self.default_squad_uuid} не найден в панели!"
            logger.critical(error_msg)
            raise RemnawaveException(error_msg)
        squad_name = squad.get("name") if isinstance(squad, dict) else None
        logger.info(f"Дефолтный сквад проверен: {self.default_squad_uuid} | Имя: {squad_name}")

    async def get_user_by_uuid(self, user_uuid: str) -> dict[str, Any] | None:
        response = await self._request("GET", f"/api/users/{user_uuid}")
        if isinstance(response, dict) and response.get("_http_status") == 404:
            return None
        data = self._extract_data(response)
        return data if isinstance(data, dict) else None

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict[str, Any] | None:
        response = await self._request("GET", f"/api/users/by-telegram-id/{telegram_id}")
        if isinstance(response, dict) and response.get("_http_status") == 404:
            return None

        data = self._extract_data(response)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    return item
            return None
        return data if isinstance(data, dict) else None

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        response = await self._request("GET", f"/api/users/by-username/{username}")
        if isinstance(response, dict) and response.get("_http_status") == 404:
            return None
        data = self._extract_data(response)
        return data if isinstance(data, dict) else None

    async def find_user(
        self,
        telegram_id: int,
        telegram_username: str | None,
        current_user_uuid: str | None = None,
    ) -> dict[str, Any] | None:
        if current_user_uuid:
            try:
                user = await self.get_user_by_uuid(current_user_uuid)
                if user:
                    return user
            except Exception as e:
                logger.warning(f"Ошибка поиска по UUID {current_user_uuid}: {e}")

        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if user:
                return user
        except Exception as e:
            logger.warning(f"Ошибка поиска по TG ID {telegram_id}: {e}")

        remnawave_username = self.build_username(telegram_id, telegram_username)
        try:
            user = await self.get_user_by_username(remnawave_username)
            if user:
                return user
        except Exception as e:
            logger.warning(f"Ошибка поиска по никнейму {remnawave_username}: {e}")

        return None

    async def create_user(self, telegram_id: int, telegram_username: str | None, days: int) -> dict[str, Any]:
        logger.info(f"Создание пользователя для TG ID: {telegram_id}")
        await self.verify_default_internal_squad()

        expire_at = datetime.now(timezone.utc) + timedelta(days=days)
        remnawave_username = self.build_username(telegram_id, telegram_username)

        payload = {
            "username": remnawave_username,
            "status": "ACTIVE",
            "expireAt": self._dt_to_iso(expire_at),
            "trafficLimitBytes": 0,
            "trafficLimitStrategy": "NO_RESET",
            "telegramId": telegram_id,
            "description": f"Created by Telegram bot",
            "tag": "TELEGRAM_BOT",
            "activeInternalSquads": [self.default_squad_uuid] if self.default_squad_uuid else [],
        }

        response = await self._request(method="POST", path="/api/users", json_data=payload)
        created_user = self._extract_data(response)

        if not isinstance(created_user, dict):
            raise RemnawaveException(f"Некорректный формат ответа создания пользователя: {created_user}")

        user_uuid = self._extract_user_uuid(created_user)
        return {
            "success": True,
            "action": "created_and_extended",
            "user_uuid": user_uuid,
            "subscription_url": self._extract_subscription_url(created_user),
            "expires_at": self._dt_to_iso(expire_at),
            "raw": created_user,
        }

    async def update_user_expire_at(self, user: dict[str, Any], days: int) -> dict[str, Any]:
        user_uuid = self._extract_user_uuid(user)
        if not user_uuid:
            raise RemnawaveException("У объекта пользователя отсутствует UUID.")

        current_expire_at = self._extract_expire_at(user)
        now = datetime.now(timezone.utc)

        base_dt = now if (current_expire_at is None or current_expire_at < now) else current_expire_at
        new_expire_at = base_dt + timedelta(days=days)

        payload = {
            "uuid": user_uuid,
            "expireAt": self._dt_to_iso(new_expire_at),
        }

        response = await self._request(method="PATCH", path="/api/users", json_data=payload)
        updated_user = self._extract_data(response)

        if not isinstance(updated_user, dict):
            updated_user = dict(user)
            updated_user["expire_at"] = self._dt_to_iso(new_expire_at)

        if "expire_at" not in updated_user and "expireAt" not in updated_user:
            updated_user["expire_at"] = self._dt_to_iso(new_expire_at)

        return {
            "success": True,
            "action": "extended",
            "user_uuid": self._extract_user_uuid(updated_user) or user_uuid,
            "subscription_url": self._extract_subscription_url(updated_user) or self._extract_subscription_url(user),
            "expires_at": self._dt_to_iso(new_expire_at),
            "raw": updated_user,
        }

    async def ensure_user_and_extend(
        self,
        telegram_id: int,
        telegram_username: str | None,
        days: int,
        current_user_uuid: str | None = None,
    ) -> dict[str, Any]:
        user = await self.find_user(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            current_user_uuid=current_user_uuid,
        )
        if user is None:
            return await self.create_user(telegram_id=telegram_id, telegram_username=telegram_username, days=days)
        return await self.update_user_expire_at(user=user, days=days)