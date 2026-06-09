from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
import aiohttp

# Настройка логгера для текущего модуля
logger = logging.getLogger(__name__)


class RemnawaveClient:
    """Клиент для интеграции с API панели управления Remnawave."""

    def __init__(
        self,
        base_url: str,
        token: str,
        default_squad_uuid: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        # Очищаем UUID сквада от пробелов, если он передан пустой строкой — приводим к None
        self.default_squad_uuid = (default_squad_uuid or "").strip() or None

    @staticmethod
    def build_username(telegram_id: int, telegram_username: str | None) -> str:
        """
        Формирует валидное имя пользователя для панели Remnawave.
        Если username в Telegram задан, очищает его от запрещенных символов.
        В противном случае генерирует дефолтное имя на основе telegram_id.
        """
        if telegram_username:
            value = telegram_username.strip().lstrip("@").lower()

            cleaned = []
            for ch in value:
                # Панель обычно разрешает буквы, цифры, подчёркивания, дефисы и точки
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
        """Приводит объект datetime к строгому ISO-формату UTC."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        """Парсит ISO-строку даты времени от API в объект datetime с timezone.utc."""
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
        """Извлекает полезную нагрузку (data/response) из различных вариаций ответов API."""
        if not isinstance(payload, dict):
            return payload

        for key in ("response", "data", "result", "user"):
            if key in payload:
                return payload[key]

        return payload

    @staticmethod
    def _extract_user_uuid(user_obj: Any) -> str | None:
        """Извлекает уникальный идентификатор (UUID/ID) пользователя из объекта ответа."""
        if isinstance(user_obj, dict):
            return user_obj.get("uuid") or user_obj.get("id")
        return None

    @staticmethod
    def _extract_subscription_url(user_obj: Any) -> str | None:
        """Ищет ссылку на подписку (конфиг) в объекте пользователя."""
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
        """Находит и парсит дату окончания подписки в объекте пользователя."""
        if not isinstance(user_obj, dict):
            return None

        return RemnawaveClient._parse_dt(
            user_obj.get("expire_at") or user_obj.get("expireAt")
        )

    def extract_user_uuid(self, user_obj: Any) -> str | None:
        """Публичный метод для получения UUID пользователя."""
        return self._extract_user_uuid(user_obj)

    def extract_subscription_url(self, user_obj: Any) -> str | None:
        """Публичный метод для получения ссылки на подписку."""
        return self._extract_subscription_url(user_obj)

    def extract_expire_at_iso(self, user_obj: Any) -> str | None:
        """Публичный метод для получения даты окончания подписки в ISO-формате."""
        dt = self._extract_expire_at(user_obj)
        return self._dt_to_iso(dt) if dt else None

    def _headers(self) -> dict[str, str]:
        """Формирует заголовки авторизации для HTTP-запросов."""
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
        """Внутренний метод для отправки асинхронных HTTP-запросов к API Remnawave."""
        url = f"{self.base_url}{path}"

        # Логируем параметры запроса на уровне DEBUG, чтобы не перегружать продакшен
        logger.debug(f"HTTP Запрос: {method} {url}")
        if params:
            logger.debug(f"HTTP Параметры: {params}")
        if json_data:
            logger.debug(f"HTTP Тело (JSON): {json_data}")

        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json_data,
                params=params,
                ssl=False,  # Отключение строгой проверки SSL, если используются самоподписанные сертификаты
            ) as response:
                # Если ресурс не найден, возвращаем специальный маркер ответа вместо паники и генерации ошибки
                if response.status == 404:
                    logger.debug(f"HTTP Ресурс не найден (404): {url}")
                    return {"_http_status": 404}

                text = await response.text()

                logger.debug(f"HTTP Статус ответа: {response.status}")
                logger.debug(f"HTTP Тело ответа (первые 3000 симв.): {text[:3000]}")

                try:
                    parsed = await response.json(content_type=None)
                except Exception:
                    parsed = text

                # Ошибки уровня 400+ (кроме обработанного выше 404) по-прежнему считаются критическими
                if response.status >= 400:
                    error_msg = f"HTTP Error {response.status} | URL: {url} | Response: {parsed}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

                return parsed

    async def get_internal_squad_by_uuid(self, squad_uuid: str) -> dict[str, Any] | None:
        """Получает информацию о внутреннем скваде (отряде) по его UUID."""
        response = await self._request("GET", f"/api/internal-squads/{squad_uuid}")
        
        # Корректно обрабатываем случай, если сквад не найден панели
        if isinstance(response, dict) and response.get("_http_status") == 404:
            logger.warning(f"Внутренний сквад с UUID {squad_uuid} не найден на сервере (404).")
            return None
            
        data = self._extract_data(response)
        return data if isinstance(data, dict) else None

    async def verify_default_internal_squad(self) -> None:
        """Проверяет существование дефолтного сквада на стороне панели."""
        if not self.default_squad_uuid:
            logger.info("Дефолтный UUID сквада не задан в конфигурации. Проверка пропущена.")
            return

        squad = await self.get_internal_squad_by_uuid(self.default_squad_uuid)
        if squad is None:
            error_msg = f"Критическая ошибка: Дефолтный сквад с UUID {self.default_squad_uuid} не найден в панели!"
            logger.critical(error_msg)
            raise Exception(error_msg)

        squad_name = squad.get("name") if isinstance(squad, dict) else None
        logger.info(
            f"Дефолтный сквад успешно проверен в панели: {self.default_squad_uuid} | Имя: {squad_name}"
        )

    async def get_user_by_uuid(self, user_uuid: str) -> dict[str, Any] | None:
        """Получает данные пользователя из панели по его UUID."""
        response = await self._request("GET", f"/api/users/{user_uuid}")
        if isinstance(response, dict) and response.get("_http_status") == 404:
            return None
            
        data = self._extract_data(response)
        return data if isinstance(data, dict) else None

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict[str, Any] | None:
        """Ищет пользователя в панели по его Telegram ID."""
        response = await self._request(
            "GET", f"/api/users/by-telegram-id/{telegram_id}"
        )
        if isinstance(response, dict) and response.get("_http_status") == 404:
            return None

        data = self._extract_data(response)

        # Если API вернуло список совпадений, берем первый подходящий словарь
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    return item
            return None

        if isinstance(data, dict):
            return data

        return None

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Ищет пользователя в панели по его уникальному имени (username)."""
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
        """
        Каскадный поиск пользователя в панели.
        Последовательно проверяет: UUID из БД, Telegram ID, затем сгенерированный username.
        """
        # 1. Попытка найти по известному UUID из локальной базы данных
        if current_user_uuid:
            try:
                user = await self.get_user_by_uuid(current_user_uuid)
                if user:
                    return user
            except Exception as e:
                logger.warning(f"Не удалось выполнить поиск пользователя по UUID {current_user_uuid}: {e}")

        # 2. Попытка найти по Telegram ID через специальный эндпоинт панели
        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if user:
                return user
        except Exception as e:
            logger.warning(f"Не удалось выполнить поиск пользователя по Telegram ID {telegram_id}: {e}")

        # 3. Попытка найти по сконструированному имени пользователя (username)
        remnawave_username = self.build_username(telegram_id, telegram_username)
        try:
            user = await self.get_user_by_username(remnawave_username)
            if user:
                return user
        except Exception as e:
            logger.warning(f"Не удалось выполнить поиск пользователя по никнейму {remnawave_username}: {e}")

        # Пользователь действительно не зарегистрирован в панели
        return None

    async def create_user(
        self,
        telegram_id: int,
        telegram_username: str | None,
        days: int,
    ) -> dict[str, Any]:
        """Создает нового пользователя в панели Remnawave с привязкой к дефолтному скваду."""
        logger.info(f"Запуск процесса создания нового пользователя для TG ID: {telegram_id}")
        
        # Перед созданием проверяем валидность настроенного сквада
        await self.verify_default_internal_squad()

        # Рассчитываем дату окончания подписки от текущего момента UTC
        expire_at = datetime.now(timezone.utc) + timedelta(days=days)
        remnawave_username = self.build_username(telegram_id, telegram_username)

        # Подготовка параметров тела запроса для создания пользователя
        payload = {
            "username": remnawave_username,
            "status": "ACTIVE",
            "expireAt": self._dt_to_iso(expire_at),
            "trafficLimitBytes": 0,  # 0 означает отсутствие лимита по трафику
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

        # Если задан дефолтный сквад, автоматически добавляем пользователя в него
        if self.default_squad_uuid:
            payload["activeInternalSquads"] = [self.default_squad_uuid]

        response = await self._request(
            method="POST",
            path="/api/users",
            json_data=payload,
        )

        created_user = self._extract_data(response)

        if not isinstance(created_user, dict):
            error_msg = f"Панель вернула некорректный формат при создании пользователя: {created_user}"
            logger.error(error_msg)
            raise Exception(error_msg)

        user_uuid = self._extract_user_uuid(created_user)
        logger.info(f"Пользователь {remnawave_username} успешно создан в панели. UUID: {user_uuid}")

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
        """Продлевает срок действия подписки существующего пользователя в панели."""
        user_uuid = self._extract_user_uuid(user)
        if not user_uuid:
            error_msg = "Невозможно обновить подписку: у переданного объекта пользователя отсутствует UUID."
            logger.error(error_msg)
            raise Exception(error_msg)

        current_expire_at = self._extract_expire_at(user)
        now = datetime.now(timezone.utc)

        # Если текущая подписка уже истекла или отсутствует, продлеваем от текущего момента.
        # Если подписка еще активна — новые дни аккуратно суммируются к ней.
        if current_expire_at is None or current_expire_at < now:
            base_dt = now
        else:
            base_dt = current_expire_at

        new_expire_at = base_dt + timedelta(days=days)
        logger.info(
            f"Продление подписки пользователя UUID {user_uuid} на {days} дней. "
            f"Новая дата окончания: {new_expire_at}"
        )

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

        # Страховка на случай, если API вернуло неполный ответ: собираем данные вручную
        if not isinstance(updated_user, dict):
            updated_user = dict(user)
            updated_user["expire_at"] = self._dt_to_iso(new_expire_at)

        if "expire_at" not in updated_user and "expireAt" not in updated_user:
            updated_user["expire_at"] = self._dt_to_iso(new_expire_at)

        logger.info(f"Подписка пользователя UUID {user_uuid} успешно обновлена в панели.")

        return {
            "success": True,
            "action": "extended",
            "user_uuid": self._extract_user_uuid(updated_user) or user_uuid,
            "subscription_url": self._extract_subscription_url(updated_user)
            or self._extract_subscription_url(user),
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
        """
        Высокоуровневый метод: ищет пользователя в панели, создает его в случае отсутствия
        или продлевает ему подписку, если он уже зарегистрирован.
        """
        logger.info(f"Запрос на обеспечение доступа для TG ID {telegram_id} на срок {days} дн.")
        
        # Пытаемся найти пользователя в системе по всем доступным признакам
        user = await self.find_user(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            current_user_uuid=current_user_uuid,
        )

        # Если пользователя нет — регистрируем с нуля
        if user is None:
            return await self.create_user(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                days=days,
            )

        # Если нашли — просто накатываем новые оплаченные дни
        return await self.update_user_expire_at(
            user=user,
            days=days,
        )