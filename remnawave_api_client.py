from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import aiohttp


class RemnawaveClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        default_squad_uuid: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.default_squad_uuid = (default_squad_uuid or "").strip() or None

    @staticmethod
    def build_username(telegram_id: int, telegram_username: str | None) -> str:
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

        print(f"[REMNAWAVE] {method} {url}")
        if params:
            print(f"[REMNAWAVE] params={params}")
        if json_data:
            print(f"[REMNAWAVE] json={json_data}")

        timeout = aiohttp.ClientTimeout(total=30)

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

                print(f"[REMNAWAVE] status={response.status}")
                print(f"[REMNAWAVE] body={text[:3000]}")

                try:
                    parsed = await response.json(content_type=None)
                except Exception:
                    parsed = text

                if response.status >= 400:
                    raise Exception(
                        f"HTTP {response.status} | URL: {url} | Response: {parsed}"
                    )

                return parsed

    async def get_internal_squad_by_uuid(self, squad_uuid: str) -> dict[str, Any] | None:
        try:
            response = await self._request("GET", f"/api/internal-squads/{squad_uuid}")
            data = self._extract_data(response)
            return data if isinstance(data, dict) else None
        except Exception as e:
            if "HTTP 404" in str(e):
                return None
            raise

    async def verify_default_internal_squad(self) -> None:
        if not self.default_squad_uuid:
            return

        squad = await self.get_internal_squad_by_uuid(self.default_squad_uuid)
        if squad is None:
            raise Exception(
                f"Internal squad with UUID {self.default_squad_uuid} not found"
            )

        squad_name = squad.get("name") if isinstance(squad, dict) else None
        print(
            f"[REMNAWAVE] verified internal squad: "
            f"{self.default_squad_uuid} | name={squad_name}"
        )

    async def get_user_by_uuid(self, user_uuid: str) -> dict[str, Any] | None:
        try:
            response = await self._request("GET", f"/api/users/{user_uuid}")
            data = self._extract_data(response)
            return data if isinstance(data, dict) else None
        except Exception as e:
            if "HTTP 404" in str(e):
                return None
            raise

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict[str, Any] | None:
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
        if current_user_uuid:
            try:
                user = await self.get_user_by_uuid(current_user_uuid)
                if user:
                    return user
            except Exception as e:
                print(f"[REMNAWAVE] get_user_by_uuid failed: {e}")

        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if user:
                return user
        except Exception as e:
            print(f"[REMNAWAVE] get_user_by_telegram_id failed: {e}")

        remnawave_username = self.build_username(telegram_id, telegram_username)

        try:
            user = await self.get_user_by_username(remnawave_username)
            if user:
                return user
        except Exception as e:
            print(f"[REMNAWAVE] get_user_by_username failed: {e}")

        return None

    async def create_user(
        self,
        telegram_id: int,
        telegram_username: str | None,
        days: int,
    ) -> dict[str, Any]:
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

        return {
            "success": True,
            "action": "created_and_extended",
            "user_uuid": self._extract_user_uuid(created_user),
            "subscription_url": self._extract_subscription_url(created_user),
            "expires_at": self._dt_to_iso(expire_at),
            "raw": created_user,
        }

    async def update_user_expire_at(
        self,
        user: dict[str, Any],
        days: int,
    ) -> dict[str, Any]:
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
            return await self.create_user(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                days=days,
            )

        return await self.update_user_expire_at(
            user=user,
            days=days,
        )