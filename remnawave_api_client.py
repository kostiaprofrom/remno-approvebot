from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import aiohttp
import logging

# Настройка локального логгера для модуля API-клиента
logger = logging.getLogger(__name__)


class RemnawaveClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        default_squad_uuid: str | None = None,
    ):
        # Инициализация параметров подключения к панели Remnawave
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.default_squad_uuid = (default_squad_uuid or "").strip() or None

    @staticmethod
    def build_username(telegram_id: int, telegram_username: str | None) -> str:
        # Валидация и сборка системного юзернейма из данных Telegram
        if telegram_username:
            value = telegram_username.strip().lstrip("@").lower()

            cleaned = []
            for ch in value:
                if ch.isalnum() or ch in ("_", "-", "."):
                    cleaned.append(ch)
                else:
                    cleaned.append("_")

            username = "".join(cleaned).strip("._-")
            if username:
                return username

        return f"tg_{telegram_id}"

    @staticmethod
    def _dt_to_iso(dt: datetime) -> str:
        # Приведение объекта datetime к ISO-строке в формате UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        # Парсинг ISO-строки даты ответа API в объект datetime
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
        # Извлечение вложенного объекта данных из типовых оберток ответа API
        if not isinstance(payload, dict):
            return payload

        for key in ("response", "data", "result", "user"):
            if key in payload:
                return payload[key]

        return payload

    @staticmethod
    def _extract_user_uuid(user_obj: Any) -> str | None:
        # Поиск UUID пользователя в словаре ответа
        if isinstance(user_obj, dict):
            return user_obj.get("uuid") or user_obj.get("id")
        return None

    @staticmethod
    def _extract_subscription_url(user_obj: Any) -> str | None:
        # Извлечение ссылки на подписку пользователя
        if not isinstance(user_obj, dict):
            return None

        for key in (
            "subscription_url",
            "subscriptionUrl",
            "subscription",
            "url",
        ):
            value = user_obj.get(key)
            if value:
                return value

        return None

    @staticmethod
    def _extract_expire_at(user_obj: Any) -> datetime | None:
        # Извлечение даты окончания действия подписки
        if not isinstance(user_obj, dict):
            return None

        return RemnawaveClient._parse_dt(
            user_obj.get("expire_at") or user_obj.get("expireAt")
        )

    def extract_user_uuid(self, user_obj: Any) -> str | None:
        return self._extract_user_uuid(user_obj)

    def extract_subscription_url(self, user_obj: Any) -> str | None:
        return self._extract_subscription_url(user_obj)

    def extract_expire_at_iso(self, user_obj: Any) -> str | None:
        dt = self._extract_expire_at(user_obj)
        return self._dt_to_iso(dt) if dt else None

    def _headers(self) -> dict[str, str]:
        # Сборка обязательных HTTP-заголовков авторизации
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
        # Выполнение асинхронного HTTP-запроса к панели Remnawave
        url = f"{self.base_url}{path}"

        logger.debug(f"Запрос: {method} {url}")
        if params:
            logger.debug(f"Параметры: {params}")
        if json_data:
            logger.debug(f"Тело JSON: {json_data}")

        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self._headers(),
                    json=json_data,
                    params=params,
                    ssl=False,
                ) as response:
                    text = await response.text()

                    logger.debug(f"Ответ статус: {response.status}")
                    logger.debug(f"Тело ответа (срез): {text[:1000]}")

                    try:
                        parsed = await response.json(content_type=None)
                    except Exception:
                        parsed = text

                    if response.status >= 400:
                        raise Exception(
                            f"HTTP {response.status} | URL: {url} | Response: {parsed}"
                        )

                    return parsed
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при запросе к Remnawave ({method} {path}): {e}")
            raise
        except Exception:
            logger.exception(f"Непредвиденная ошибка при запросе к Remnawave ({method} {path})")
            raise

    async def get_internal_squad_by_uuid(self, squad_uuid: str) -> dict[str, Any] | None:
        # Получение информации о конкретном скваде
        try:
            response = await self._request("GET", f"/api/internal-squads/{squad_uuid}")
            data = self._extract_data(response)
            return data if isinstance(data, dict) else None
        except Exception as e:
            if "HTTP 404" in str(e):
                return None
            raise

    async def verify_default_internal_squad(self) -> None:
        # Проверка существования дефолтного сквада при запуске приложения
        if not self.default_squad_uuid:
            return

        squad = await self.get_internal_squad_by_uuid(self.default_squad_uuid)
        if squad is None:
            raise Exception(
                f"Internal squad with UUID {self.default_squad_uuid} not found"
            )

        squad_name = squad.get("name") if isinstance(squad, dict) else None
        logger.info(
            f"Успешная верификация сквада: {self.default_squad_uuid} | name={squad_name}"
        )

    async def get_user_by_uuid(self, user_uuid: str) -> dict[str, Any] | None:
        # Получение данных пользователя по его UUID в панели
        try:
            response = await self._request("GET", f"/api/users/{user_uuid}")
            data = self._extract_data(response)
            return data if isinstance(data, dict) else None
        except Exception as e:
            if "HTTP 404" in str(e):
                return None
            raise

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict[str, Any] | None:
        # Поиск пользователя по Telegram ID через API панели
        try:
            response = await self._request(
                "GET", f"/api/users/by-telegram-id/{telegram_id}"
            )
            data = self._extract_data(response)

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        return item
                return None

            if isinstance(data, dict):
                return data

            return None
        except Exception as e:
            if "HTTP 404" in str(e):
                return None
            raise

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        # Поиск пользователя по его системному юзернейму панели
        try:
            response = await self._request("GET", f"/api/users/by-username/{username}")
            data = self._extract_data(response)
            return data if isinstance(data, dict) else None
        except Exception as e:
            if "HTTP 404" in str(e):
                return None
            raise

    async def find_user(
        self,
        telegram_id: int,
        telegram_username: str | None,
        current_user_uuid: str | None = None,
    ) -> dict[str, Any] | None:
        # Комплексный последовательный поиск пользователя по всем доступным идентификаторам
        if current_user_uuid:
            try:
                user = await self.get_user_by_uuid(current_user_uuid)
                if user:
                    return user
            except Exception as e:
                logger.warning(f"Поиск по UUID {current_user_uuid} не удался: {e}")

        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if user:
                return user
        except Exception as e:
            logger.warning(f"Поиск по Telegram ID {telegram_id} не удался: {e}")

        remnawave_username = self.build_username(telegram_id, telegram_username)

        try:
            user = await self.get_user_by_username(remnawave_username)
            if user:
                return user
        except Exception as e:
            logger.warning(f"Поиск по сгенерированному юзернейму {remnawave_username} не удался: {e}")

        return None

    async def create_user(
        self,
        telegram_id: int,
        telegram_username: str | None,
        days: int,
    ) -> dict[str, Any]:
        # Регистрация нового пользователя в панели с добавлением в дефолтный сквад
        logger.info(f"Запрос на создание нового пользователя в панели Remnawave для TG: {telegram_id}")
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
            "description": (
                f"Created by Telegram bot for @{telegram_username}"
                if telegram_username
                else f"Created by Telegram bot for {telegram_id}"
            ),
            "tag": "TELEGRAM_BOT",
            "activeInternalSquads": [],
        }

        if self.default_squad_uuid:
            payload["activeInternalSquads"] = [self.default_squad_uuid]

        response = await self._request(
            method="POST",
            path="/api/users",
            json_data=payload,
        )

        created_user = self._extract_data(response)

        if not isinstance(created_user, dict):
            raise Exception(f"Неожиданный ответ create_user: {created_user}")

        user_uuid = self._extract_user_uuid(created_user)
        logger.info(f"Пользователь успешно создан в панели. UUID: {user_uuid}")

        return {
            "success": True,
            "action": "created_and_extended",
            "user_uuid": user_uuid,
            "subscription_url": self._extract_subscription_url(created_user),
            "expires_at": self._dt_to_iso(expire_at),
            "raw": created_user,
        }

    async def update_user_expire_at(
        self,
        user: dict[str, Any],
        days: int,
    ) -> dict[str, Any]:
        # Сдвиг даты окончания подписки на N дней вперед относительно текущей или будущей даты
        user_uuid = self._extract_user_uuid(user)
        if not user_uuid:
            raise Exception("У существующего пользователя нет UUID")

        current_expire_at = self._extract_expire_at(user)
        now = datetime.now(timezone.utc)

        if current_expire_at is None or current_expire_at < now:
            base_dt = now
        else:
            base_dt = current_expire_at

        new_expire_at = base_dt + timedelta(days=days)
        logger.info(f"Продление подписки в Remnawave для UUID {user_uuid} на {days} дней. Новый expireAt: {new_expire_at}")

        payload = {
            "uuid": user_uuid,
            "expireAt": self._dt_to_iso(new_expire_at),
        }

        response = await self._request(
            method="PATCH",
            path="/api/users",
            json_data=payload,
        )

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
            "subscription_url": self._extract_subscription_url(updated_user)
            or self._extract_subscription_url(user),
            "expires_at": self._dt_to_iso(new_expire_at),
            "raw": updated_user,
        }

    async def update_user_expiry(
        self,
        user_uuid: str,
        new_expire_at: datetime,
        user: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Алиас-метод для установки фиксированной даты (вызывается в карточке админа)
        logger.info(f"Установка фиксированной даты подписки для UUID {user_uuid} на: {new_expire_at}")
        
        payload = {
            "uuid": user_uuid,
            "expireAt": self._dt_to_iso(new_expire_at),
        }

        response = await self._request(
            method="PATCH",
            path="/api/users",
            json_data=payload,
        )
        
        updated_user = self._extract_data(response)
        return {
            "success": True,
            "user_uuid": user_uuid,
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
        # Проверяет существование пользователя; создает нового или продлевает существующего
        user = await self.find_user(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            current_user_uuid=current_user_uuid,
        )

        if user is None:
            return await self.create_user(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                days=days,
            )

        return await self.update_user_expire_at(
            user=user,
            days=days,
        )