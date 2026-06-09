import os
from datetime import datetime, timezone
from html import escape
from dotenv import load_dotenv

# Загружаем переменные из конфигурационного файла .env
load_dotenv()


def get_env_text(key: str, default: str) -> str:
    # Возвращает текст из .env с поддержкой корректного переноса строк
    text = os.getenv(key, default)
    return text.replace("\\n", "\n")


def safe_user_name(username: str | None, full_name: str | None, user_id: int) -> str:
    # Безопасное форматирование и экранирование имени пользователя для HTML
    if username:
        return f"@{escape(username)}"
    if full_name:
        return escape(full_name)
    return f"ID {user_id}"


def calculate_days_left(expires_at: str | None) -> int:
    # Рассчитывает количество оставшихся дней подписки на основе ISO-строки даты
    if not expires_at:
        return 0
    try:
        s = str(expires_at).replace("Z", "+00:00")
        if "." in s:
            base, tz = s.split(".", 1)
            if "+" in tz:
                ms, zone = tz.split("+", 1)
                s = f"{base}.{ms[:6]}+{zone}"
            elif "-" in tz:
                ms, zone = tz.split("-", 1)
                s = f"{base}.{ms[:6]}-{zone}"
            else:
                s = f"{base}.{tz[:6]}"

        expire_dt = datetime.fromisoformat(s)
        if expire_dt.tzinfo is None:
            expire_dt = expire_dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        expire_date = expire_dt.date()
        now_date = now.date()

        delta_days = (expire_date - now_date).days
        return max(0, delta_days)
    except Exception:
        return 0


# --- ТЕКСТЫ АВТОРИЗАЦИИ ПО КОДУ ---

def build_access_prompt_text() -> str:
    default = "🔐 <b>Доступ к боту закрыт</b>\n\nОтправьте <b>код доступа</b>, чтобы открыть меню."
    return get_env_text("TEXT_ACCESS_PROMPT", default)


def build_access_success_text() -> str:
    default = "✅ <b>Код принят</b>\n\nДоступ открыт. Загружаю Ваше меню…"
    return get_env_text("TEXT_ACCESS_SUCCESS", default)


def build_access_error_text() -> str:
    default = "❌ <b>Неверный код доступа</b>\n\nПроверьте код и попробуйте снова."
    return get_env_text("TEXT_ACCESS_ERROR", default)


# --- ГЛАВНОЕ МЕНЮ И РЕФЕРАЛЬНАЯ СИСТЕМА ---

def build_main_menu_text(
    days_left: int,
    subscription_url: str | None,
    chat_link: str,
    is_admin: bool = False,
) -> str:
    # Формирует текст личного кабинета пользователя со статусом подписки
    sub_url_line = f'<a href="{escape(subscription_url, quote=True)}">Открыть подписку</a>' if subscription_url else "Пока не создана"
    chat_url_line = f'<a href="{escape(chat_link, quote=True)}">Перейти в чат</a>' if chat_link else "Не указана"

    if days_left > 3:
        status_emoji, status_text = "🟢", "Подписка активна"
    elif days_left > 0:
        status_emoji, status_text = "🟡", "Подписка скоро закончится"
    else:
        status_emoji, status_text = "🔴", "Подписка неактивна"

    admin_line = "\n🛠 <b>Режим:</b> доступна админка" if is_admin else ""

    default = (
        "✨ <b>Главное меню</b>\n\n"
        "{status_emoji} <b>Статус:</b> {status_text}\n"
        "📅 <b>Осталось дней:</b> {days_left}\n"
        "🔗 <b>Ссылка на подписку:</b> {sub_url_line}\n"
        "💬 <b>Общий чат:</b> {chat_url_line}"
        "{admin_line}\n\n"
        "Используйте кнопки ниже для управления подпиской."
    )
    
    template = get_env_text("TEXT_MAIN_MENU", default)
    return template.format(
        status_emoji=status_emoji,
        status_text=status_text,
        days_left=days_left,
        sub_url_line=sub_url_line,
        chat_url_line=chat_url_line,
        admin_line=admin_line
    )


def build_referral_menu_text(
    telegram_id: int,
    bot_username: str,
    bonus_days: int,
    referred_count: int,
) -> str:
    # Генерирует экран реферальной программы и ссылку приглашения
    ref_link = f"https://t.me/{escape(bot_username)}?start=ref_{telegram_id}"
    
    default = (
        "🤝 <b>Реферальная программа</b>\n\n"
        "💰 <b>Вам:</b> +{bonus_days} дн. (после первой оплаты друга)\n"
        "📊 <b>Всего приглашено:</b> {referred_count} чел.\n\n"
        "🔗 <b>Ваша ссылка для приглашения:</b>\n"
        "<code>{ref_link}</code>"
    )
    
    template = get_env_text("TEXT_REFERRAL_MENU", default)
    return template.format(bonus_days=bonus_days, referred_count=referred_count, ref_link=ref_link)


# --- ТАРИФЫ И ОПЛАТА ---

def build_tariffs_text() -> str:
    default = "🧾 <b>Выбор тарифа</b>\n\nВыберите подходящий тариф для продления подписки."
    return get_env_text("TEXT_TARIFFS", default)


def build_tariff_payment_text(tariff_title: str, amount: int, payment_link: str) -> str:
    # Карточка оплаты выбранного тарифа с платежными реквизитами
    default = (
        "💳 <b>Оплата подписки</b>\n\n"
        "📦 <b>Тариф:</b> {tariff_title}\n"
        "💰 <b>Сумма:</b> {amount} ₽\n"
        "🏦 <b>Реквизиты для оплаты:</b>\n"
        "📱 Номер телефона: <code>+7 903 948 24 92</code>\n"
        "🏷 СБП (Система быстрых платежей)\n"
        "✅ Доступные банки: <b>Сбер</b>, <b>Т-Банк</b>\n\n"
        "После оплаты направьте <b>скриншот</b> для подтверждения👇"
    )
    
    template = get_env_text("TEXT_TARIFF_PAYMENT", default)
    return template.format(tariff_title=escape(tariff_title), amount=amount, payment_link=escape(payment_link, quote=True))


def build_invalid_screenshot_text() -> str:
    default = "⚠️ <b>Нужен скриншот оплаты</b>\n\nПожалуйста, отправьте его именно как <b>фото</b>."
    return get_env_text("TEXT_INVALID_SCREENSHOT", default)


def build_request_sent_text() -> str:
    default = "⏳ <b>Заявка отправлена</b>\n\nСкриншот передан администратору. После проверки статус обновится автоматически."
    return get_env_text("TEXT_REQUEST_SENT", default)


# --- ПЛАНИРОВЩИК УВЕДОМЛЕНИЙ ---

def build_expiry_three_days_reminder_text() -> str:
    default = (
        "⚠️ <b>Внимание! Ваша подписка истекает через 3 дня</b>\n\n"
        "Чтобы интернет не отключился в самый неподходящий момент, вы можете продлить "
        "подписку уже сейчас через главное меню бота."
    )
    return get_env_text("TEXT_EXPIRY_3_DAYS", default)


def build_expiry_reminder_text() -> str:
    default = (
        "⏰ <b>Напоминание</b>\n\n"
        "Ваша подписка истечёт <b>через 1 день</b>.\n"
        "Если Вы хотите сохранить доступ без перерыва — продлите её заранее."
    )
    return get_env_text("TEXT_EXPIRY_1_DAY", default)


# --- АДМИН-ПАНЕЛЬ И МОДЕРАЦИЯ ---

def build_admin_request_caption(
    request_id: int,
    display_name: str,
    telegram_id: int,
    tariff_title: str,
    amount: int,
) -> str:
    # Текст оповещения админа о новом платеже
    default = (
        "🆕 <b>Новая заявка на продление</b>\n\n"
        "<b>ID заявки:</b> {request_id}\n"
        "<b>Пользователь:</b> {display_name}\n"
        "<b>Telegram ID:</b> <code>{telegram_id}</code>\n"
        "<b>Тариф:</b> {tariff_title}\n"
        "<b>Сумма:</b> {amount} ₽"
    )
    template = get_env_text("TEXT_ADMIN_REQUEST_CAPTION", default)
    return template.format(
        request_id=request_id,
        display_name=display_name,
        telegram_id=telegram_id,
        tariff_title=escape(tariff_title),
        amount=amount
    )


def build_user_request_accepted_text(days: int) -> str:
    default = "✅ <b>Заявка одобрена</b>\n\nПодписка успешно продлена на <b>{days}</b> дн."
    template = get_env_text("TEXT_REQUEST_ACCEPTED", default)
    return template.format(days=days)


def build_user_request_rejected_text() -> str:
    default = "❌ <b>Заявка отклонена</b>\n\nЕсли это ошибка, напишите в общий чат поддержки."
    return get_env_text("TEXT_REQUEST_REJECTED", default)


def build_admin_panel_text() -> str:
    default = "🛠 <b>Админ-панель</b>\n\nЗдесь можно управлять доступом пользователей к боту."
    return get_env_text("TEXT_ADMIN_PANEL", default)


def build_admin_users_list_text(
    users: list[dict],
    access_value: int,
    page: int,
    total_pages: int,
    total_users: int,
) -> str:
    # Постраничный список пользователей в админке
    active_title = get_env_text("TEXT_ADMIN_USERS_ACTIVE_TITLE", "✅ Активные пользователи")
    inactive_title = get_env_text("TEXT_ADMIN_USERS_INACTIVE_TITLE", "❌ Отключённые пользователи")
    title = active_title if access_value == 1 else inactive_title

    if not users:
        default_empty = "👥 <b>{title}</b>\n\nСписок пуст.\nСтраница {page}/{total_pages}."
        template_empty = get_env_text("TEXT_ADMIN_USERS_LIST_EMPTY", default_empty)
        return template_empty.format(title=title, page=page, total_pages=total_pages)

    user_lines = []
    for idx, user in enumerate(users, start=1):
        name = safe_user_name(user.get("username"), user.get("full_name"), user["telegram_id"])
        access_icon = "✅" if user.get("access_granted") == 1 else "❌"
        user_lines.append(f"{idx}. {access_icon} {name} — <code>{user['telegram_id']}</code>")

    user_lines_str = "\n".join(user_lines)

    default_body = (
        "👥 <b>{title}</b>\n\n"
        "<b>Всего:</b> {total_users}\n"
        "<b>Страница:</b> {page}/{total_pages}\n\n"
        "{user_lines}\n\n"
        "Нажмите на пользователя, чтобы открыть карточку."
    )
    template_body = get_env_text("TEXT_ADMIN_USERS_LIST_BODY", default_body)
    return template_body.format(
        title=title,
        total_users=total_users,
        page=page,
        total_pages=total_pages,
        user_lines=user_lines_str
    )


def build_admin_user_card_text(user: dict) -> str:
    # Подробная карточка управления пользователем
    name = safe_user_name(user.get("username"), user.get("full_name"), user["telegram_id"])
    access_icon = "✅" if user.get("access_granted") == 1 else "❌"
    access_text = "Активен" if user.get("access_granted") == 1 else "Отключён"

    subscription_url = user.get("subscription_url") or "Нет"
    expires_at = user.get("subscription_expires_at") or "Нет"

    default = (
        "👤 <b>Карточка пользователя</b>\n\n"
        "<b>Имя:</b> {name}\n"
        "<b>Telegram ID:</b> <code>{telegram_id}</code>\n"
        "<b>Доступ:</b> {access_icon} {access_text}\n"
        "<b>UUID панели:</b> <code>{uuid}</code>\n"
        "<b>Подписка:</b> {subscription_url}\n"
        "<b>Окончание:</b> <code>{expires_at}</code>"
    )
    template = get_env_text("TEXT_ADMIN_USER_CARD", default)
    return template.format(
        name=name,
        telegram_id=user['telegram_id'],
        access_icon=access_icon,
        access_text=access_text,
        uuid=escape(str(user.get('remnawave_user_uuid') or '-')),
        subscription_url=escape(str(subscription_url)),
        expires_at=escape(str(expires_at))
    )