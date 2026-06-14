import asyncio
import math
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv

# 1. Настройка системы логирования

def setup_logging():
    from dotenv import load_dotenv
    load_dotenv()

    env_level = os.getenv("LOG_LEVEL", "INFO").upper()
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    log_level = levels.get(env_level, logging.INFO)

    log_format = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Обработчик для вывода в консоль (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    console_handler.setLevel(log_level)

    # Корневой логгер: уровень и обработчик
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Удаляем старые хендлеры, чтобы не дублировать сообщения
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(console_handler)

    # Подавляем излишний DEBUG-спам от сторонних библиотек
    if log_level == logging.DEBUG:
        logging.getLogger("aiogram").setLevel(logging.INFO)
        logging.getLogger("aiohttp").setLevel(logging.INFO)
        logging.getLogger("aiosqlite").setLevel(logging.INFO)
    else:
        logging.getLogger("aiogram").setLevel(logging.WARNING)
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
        logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    # Подтверждение успешной инициализации логирования
    root_logger.info(f"Логирование успешно инициализировано. Текущий уровень: {env_level}")

# Выполняем настройку логирования сразу при загрузке модуля
setup_logging()
logger = logging.getLogger(__name__)

# 2. Импорты зависимостей проекта (aiogram, конфигурация, БД, API-клиенты)
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

# Конфигурационные параметры, загруженные из .env и config.py
from config import (
    ACCESS_CODE,
    CHAT_LINK,
    PAYMENT_LINK,
    DB_PATH,
    TARIFFS,
    HERO_IMAGE_PATH,
    WELCOME_IMAGE_PATH,
    REMIDER_CHECK_INTERVAL_SECONDS,
    ADMIN_USERS_PER_PAGE,
    REFERRAL_BONUS_DAYS,
    TRIAL_DAYS,
    TRIAL_BUTTON_ENABLED,
    REFERRAL_REQUIRE_PAYMENT,
)

# Состояния для FSM
from states import AccessStates, PaymentStates

# Клавиатуры (инлайн)
from keyboards import (
    get_main_menu_keyboard,
    get_tariffs_keyboard,
    get_admin_request_keyboard,
    get_admin_processed_keyboard,
    get_tariff_selected_keyboard,
    get_back_to_tariffs_keyboard,
    get_admin_panel_keyboard,
    get_admin_access_filters_keyboard,
    get_admin_users_keyboard,
    get_admin_user_card_keyboard,
)

# Функции работы с базой данных SQLite
from db import (
    init_db,
    create_or_update_user,
    get_user,
    grant_access,
    create_payment_request,
    get_request_by_id,
    update_request_status,
    set_user_subscription_data,
    clear_user_subscription_data,
    get_last_menu_message_id,
    set_last_menu_message_id,
    get_users_for_reminder_check,
    was_expiry_reminder_sent_by_type,
    mark_expiry_reminder_sent_by_type,
    count_users_by_access,
    get_users_by_access_paginated,
    set_user_access,
    set_referrer,
    get_referrer_id,
    count_referred_users,
    reward_referrer_if_exists,
    activate_user_trial,
    has_approved_payments,
)

# Генераторы текстов
from text_utils import (
    safe_user_name,
    calculate_days_left,
    build_main_menu_text,
    build_referral_menu_text,
    build_tariff_payment_text,
    build_admin_request_caption,
    build_user_request_accepted_text,
    build_user_request_rejected_text,
    build_access_prompt_text,
    build_access_success_text,
    build_access_error_text,
    build_invalid_screenshot_text,
    build_tariffs_text,
    build_request_sent_text,
    build_expiry_reminder_text,
    build_expiry_three_days_reminder_text,
    build_admin_panel_text,
    build_admin_users_list_text,
    build_admin_user_card_text,
)

# Клиент для взаимодействия с панелью Remnawave (VPN-сервис)
from remnawave_api_client import RemnawaveClient
import aiosqlite

# 3. Чтение обязательных переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0").strip())

REMNAWAVE_BASE_URL = os.getenv("REMNAWAVE_BASE_URL", "").strip()
REMNAWAVE_TOKEN = os.getenv("REMNAWAVE_TOKEN", "").strip()
REMNAWAVE_DEFAULT_SQUAD_UUID = os.getenv("REMNAWAVE_DEFAULT_SQUAD_UUID", "").strip()

# 4. Инициализация бота, диспетчера и клиента Remnawave
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
        link_preview_is_disabled=True,
    ),
)
dp = Dispatcher()

remnawave_client = RemnawaveClient(
    base_url=REMNAWAVE_BASE_URL,
    token=REMNAWAVE_TOKEN,
    default_squad_uuid=REMNAWAVE_DEFAULT_SQUAD_UUID,
    verify_ssl=True
)

@dp.shutdown()
async def on_shutdown():
    await remnawave_client.close()
    print("Сессия API успешно закрыта.")

# 5. Вспомогательные функции для работы с сообщениями

async def delete_user_message_safe(message: Message) -> None:
    """Безопасно удаляет сообщение пользователя (игнорирует ошибки)."""
    try:
        await message.delete()
    except Exception:
        pass

async def delete_message_safe(chat_id: int, message_id: int | None) -> None:
    """Безопасно удаляет сообщение по его ID."""
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

async def send_image_or_text(
    chat_id: int,
    text: str,
    image_path: str | None = None,
    reply_markup=None,
) -> Message:
    """
    Отправляет сообщение: если указан image_path и файл существует – отправляет фото с подписью,
    иначе – обычное текстовое сообщение.
    """
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            photo = BufferedInputFile(f.read(), filename=os.path.basename(image_path))
        return await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=text,
            reply_markup=reply_markup,
        )

    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )

# 6. Синхронизация данных пользователя с панелью Remnawave
async def sync_user_subscription_with_panel(telegram_id: int) -> dict | None:
    """
    Получает актуальные данные о подписке пользователя из панели Remnawave
    и обновляет локальную базу данных.
    Возвращает запись пользователя из БД (обновлённую).
    """
    user = await get_user(DB_PATH, telegram_id)
    if not user:
        return None

    panel_user = None
    try:
        panel_user = await remnawave_client.find_user(
            telegram_id=telegram_id,
            telegram_username=user.get("username"),
            current_user_uuid=user.get("remnawave_user_uuid"),
        )
    except Exception as e:
        logger.error(f"[SYNC] Ошибка синхронизации пользователя {telegram_id} с панелью: {e}")
        return user

    # Если пользователь не найден в панели – сбрасываем локальные данные подписки
    if panel_user is None:
        if (
            user.get("remnawave_user_uuid")
            or user.get("subscription_url")
            or user.get("subscription_expires_at")
        ):
            logger.warning(f"[SYNC] Пользователь {telegram_id} не найден в панели. Сброс подписки в локальной БД.")
            await clear_user_subscription_data(DB_PATH, telegram_id)
        return await get_user(DB_PATH, telegram_id)

    # Извлекаем данные из ответа панели
    expires_at = remnawave_client.extract_expire_at_iso(panel_user)
    subscription_url = remnawave_client.extract_subscription_url(panel_user)
    user_uuid = remnawave_client.extract_user_uuid(panel_user)

    # Обновляем локальную БД
    await set_user_subscription_data(
        DB_PATH,
        telegram_id=telegram_id,
        remnawave_user_uuid=user_uuid,
        subscription_url=subscription_url,
        subscription_expires_at=expires_at,
    )
    return await get_user(DB_PATH, telegram_id)

# 7. Отрисовка главного меню
async def render_single_main_menu(chat_id: int) -> Message:
    """
    Показывает главное меню пользователю с учетом триал-периода и истории оплат.
    """
    user = await sync_user_subscription_with_panel(chat_id)

    expires_at = user.get("subscription_expires_at") if user else None
    days_left = calculate_days_left(expires_at) if user else 0
    subscription_url = user.get("subscription_url") if user else None
    has_used_trial = bool(user.get("has_used_trial", 0)) if user else True

    # Проверяем, были ли у пользователя одобренные оплаты
    paid_user = await has_approved_payments(DB_PATH, chat_id)

    # Кнопка триала доступна, если не израсходована и нет активной подписки
    show_trial_button = TRIAL_BUTTON_ENABLED and (not has_used_trial) and (days_left <= 0)
    
    # Кнопка рефералки
    if not REFERRAL_REQUIRE_PAYMENT:
        show_referral_button = True
    else:
        show_referral_button = bool(paid_user)

    text = build_main_menu_text(
        days_left=days_left,
        subscription_url=subscription_url,
        chat_link=CHAT_LINK,
        is_admin=(chat_id == ADMIN_ID),
    )

    old_menu_message_id = await get_last_menu_message_id(DB_PATH, chat_id)
    if old_menu_message_id:
        await delete_message_safe(chat_id, old_menu_message_id)

    sent_message = await send_image_or_text(
        chat_id=chat_id,
        text=text,
        image_path=HERO_IMAGE_PATH,
        reply_markup=get_main_menu_keyboard(
            is_admin=(chat_id == ADMIN_ID), 
            show_trial_button=show_trial_button,
            show_referral_button=show_referral_button  # Передаем статус
        ),
    )

    # Сохраняем ID нового сообщения меню
    await set_last_menu_message_id(DB_PATH, chat_id, sent_message.message_id)
    return sent_message

# 8. Вспомогательные функции для административной панели
async def show_admin_panel(callback: CallbackQuery) -> None:
    """Показывает главное меню администратора."""
    text = build_admin_panel_text()
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=get_admin_panel_keyboard(),
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=get_admin_panel_keyboard(),
                disable_web_page_preview=True,
            )
    except Exception:
        await bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=get_admin_panel_keyboard(),
            disable_web_page_preview=True,
        )

async def show_admin_access_filters(callback: CallbackQuery) -> None:
    """Показывает меню фильтров для списка пользователей (все/с доступом/без доступа)."""
    text = (
        "👥 <b>Управление доступом</b>\n\n"
        "Выберите, какой список пользователей открыть."
    )
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=get_admin_access_filters_keyboard(),
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=get_admin_access_filters_keyboard(),
                disable_web_page_preview=True,
            )
    except Exception:
        await bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=get_admin_access_filters_keyboard(),
            disable_web_page_preview=True,
        )

async def show_admin_users_page(
    callback: CallbackQuery,
    access_value: int,
    page: int,
) -> None:
    """Показывает страницу со списком пользователей по заданному фильтру доступа."""
    total_users = await count_users_by_access(DB_PATH, access_value)
    total_pages = max(1, math.ceil(total_users / ADMIN_USERS_PER_PAGE))
    page = max(1, min(page, total_pages))

    users = await get_users_by_access_paginated(
        DB_PATH,
        access_value=access_value,
        page=page,
        per_page=ADMIN_USERS_PER_PAGE,
    )

    text = build_admin_users_list_text(
        users=users,
        access_value=access_value,
        page=page,
        total_pages=total_pages,
        total_users=total_users,
    )

    keyboard = get_admin_users_keyboard(
        users=users,
        access_value=access_value,
        page=page,
        total_pages=total_pages,
    )

    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=keyboard,
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
    except Exception:
        await bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

async def show_admin_user_card(
    callback: CallbackQuery,
    target_user_id: int,
    access_value: int,
    page: int,
) -> None:
    """Показывает карточку конкретного пользователя с возможностью изменить доступ."""
    user = await get_user(DB_PATH, target_user_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    text = build_admin_user_card_text(user)
    keyboard = get_admin_user_card_keyboard(
        telegram_id=target_user_id,
        current_access=user.get("access_granted", 0),
        return_access_value=access_value,
        return_page=page,
    )

    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=keyboard,
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
    except Exception:
        await bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

# 9. Обработчики команд и колбэков
@dp.callback_query(F.data == "activate_trial")
async def process_activate_trial(callback: CallbackQuery) -> None:
    """Обработка активации пробного периода."""
    chat_id = callback.from_user.id
    
    # 1. Повторно синхронизируем и запрашиваем данные пользователя для защиты от race condition
    user = await sync_user_subscription_with_panel(chat_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    days_left = calculate_days_left(user.get("subscription_expires_at"))
    has_used_trial = bool(user.get("has_used_trial", 0))

    # На всякий случай проверяем глобальный флаг
    if not TRIAL_BUTTON_ENABLED:
        await callback.answer("Пробный период недоступен.", show_alert=True)
        await render_single_main_menu(chat_id)
        return

    # 2. Проверка условий активации
    if has_used_trial or days_left > 0:
        await callback.answer("Пробный период недоступен.", show_alert=True)
        # Обновляем меню, чтобы убрать неактуальную кнопку
        await render_single_main_menu(chat_id)
        return

    # 3. Логика успешного выполнения
    now = datetime.now(timezone.utc)
    trial_expiry = now + timedelta(days=TRIAL_DAYS)
    trial_expiry_iso = trial_expiry.isoformat().replace("+00:00", "Z")

    try:
        # Интеграция с внешней панелью Remnawave
        # Метод ensure_user_and_extend создаст пользователя в панели, если его нет, или продлит
        await remnawave_client.ensure_user_and_extend(
            telegram_id=chat_id,
            telegram_username=callback.from_user.username,
            days=TRIAL_DAYS,
            current_user_uuid=user.get("remnawave_user_uuid")
        )
        
        # Обновляем локальную базу данных
        await activate_user_trial(DB_PATH, chat_id, trial_expiry_iso)
        
        # Форматируем дату для вывода пользователю (ДД.ММ.ГГГГ)
        formatted_date = trial_expiry.strftime("%d.%m.%Y")
        
        await callback.answer("Пробный период успешно активирован! 🎉", show_alert=False)
        await bot.send_message(
            chat_id=chat_id,
            text=f"🎁 <b>Пробный период на {TRIAL_DAYS} дней активирован!</b>\nДоступ предоставлен до {formatted_date}."
        )
        
    except Exception as e:
        logger.error(f"Ошибка при активации пробного периода для {chat_id}: {e}")
        await callback.answer("Произошла ошибка при подключении к серверу. Попробуйте позже.", show_alert=True)
        return

    # 4. Перерисовываем главное меню (кнопка исчезнет, так как has_used_trial станет True)
    await render_single_main_menu(chat_id)

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    Обработчик команды /start.
    - Проверяет реферальный параметр (ref_<id>).
    - Создаёт/обновляет пользователя в БД.
    - Если переход по реферальной ссылке – сразу выдаёт доступ.
    - Иначе запрашивает код доступа.
    """
    user = message.from_user
    referrer_id = None
    by_referral_link = False

    logger.info(f"Команда /start от пользователя {user.id} ({user.full_name})")

    # Разбираем аргументы команды /start
    args = message.text.split()
    if len(args) > 1:
        start_arg = args[1]
        if start_arg.startswith("ref_"):
            start_arg = start_arg.replace("ref_", "")
            
        if start_arg.isdigit():
            referrer_id = int(start_arg)
            if referrer_id != user.id:
                logger.info(f"Пользователь {user.id} перешёл по реферальной ссылке от {referrer_id}")
                await set_referrer(DB_PATH, user.id, referrer_id)
                by_referral_link = True
            else:
                logger.warning(f"Пользователь {user.id} попытался перейти по своей собственной ссылке.")

    # Создаем или обновляем пользователя в локальной БД
    await create_or_update_user(
        DB_PATH,
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
        referred_by=referrer_id
    )

    # Если пользователь пришел по реферальной ссылке, автоматически выдаем ему доступ
    if by_referral_link:
        logger.info(f"Автоматическая выдача доступа рефералу {user.id} пригласителя {referrer_id}")
        await grant_access(DB_PATH, user.id, f"referred_by_{referrer_id}")
        
        if WELCOME_IMAGE_PATH and os.path.exists(WELCOME_IMAGE_PATH):
            await send_image_or_text(
                chat_id=message.chat.id,
                text=build_access_success_text(),
                image_path=WELCOME_IMAGE_PATH,
            )
        else:
            await bot.send_message(message.chat.id, build_access_success_text())

    db_user = await get_user(DB_PATH, user.id)
    await delete_user_message_safe(message)

    # Если доступ уже есть – показываем главное меню
    if db_user and db_user.get("access_granted") == 1:
        await state.clear()
        await render_single_main_menu(user.id)
        return

    # Иначе переводим в состояние ожидания кода доступа
    await state.set_state(AccessStates.waiting_for_access_code)
    await bot.send_message(user.id, build_access_prompt_text())

@dp.message(AccessStates.waiting_for_access_code)
async def process_access_code(message: Message, state: FSMContext) -> None:
    """Проверяет введённый код доступа и при успехе выдаёт доступ."""
    entered_code = (message.text or "").strip()
    await delete_user_message_safe(message)

    if entered_code != ACCESS_CODE:
        logger.warning(f"Пользователь {message.from_user.id} ввёл неверный код доступа.")
        await bot.send_message(message.chat.id, build_access_error_text())
        return

    logger.info(f"Пользователь {message.from_user.id} успешно ввёл код доступа.")
    await grant_access(DB_PATH, message.from_user.id, entered_code)
    await state.clear()

    if WELCOME_IMAGE_PATH and os.path.exists(WELCOME_IMAGE_PATH):
        await send_image_or_text(
            chat_id=message.chat.id,
            text=build_access_success_text(),
            image_path=WELCOME_IMAGE_PATH,
        )
    else:
        await bot.send_message(message.chat.id, build_access_success_text())

    await render_single_main_menu(message.from_user.id)

# Основные колбэки интерфейса
@dp.callback_query(F.data == "open_tariffs")
async def open_tariffs(callback: CallbackQuery) -> None:
    """Открывает список тарифов."""
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=build_tariffs_text(),
                reply_markup=get_tariffs_keyboard(),
            )
        else:
            await callback.message.edit_text(
                build_tariffs_text(),
                reply_markup=get_tariffs_keyboard(),
                disable_web_page_preview=True,
            )
    except Exception:
        await render_single_main_menu(callback.from_user.id)

    await callback.answer()


@dp.callback_query(F.data == "referral_menu")
async def referral_menu_handler(callback: CallbackQuery) -> None:
    """Показывает реферальное меню со статистикой и ссылкой."""
    telegram_id = callback.from_user.id
    
    if REFERRAL_REQUIRE_PAYMENT and not await has_approved_payments(DB_PATH, telegram_id):
        await callback.answer("Реферальная программа доступна только после первой оплаты подписки.", show_alert=True)
        return
    
    referred_count = await count_referred_users(DB_PATH, telegram_id)
    bot_info = await bot.get_me()
    
    text = build_referral_menu_text(
        telegram_id=telegram_id,
        bot_username=bot_info.username,
        bonus_days=REFERRAL_BONUS_DAYS,
        referred_count=referred_count
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_main")]
    ])
    
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard)
        else:
            await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    except Exception:
        await bot.send_message(telegram_id, text, reply_markup=keyboard, disable_web_page_preview=True)
        
    await callback.answer()

@dp.callback_query(F.data == "refresh_main")
async def refresh_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Обновляет главное меню (перерисовывает)."""
    await state.clear()
    try:
        await delete_message_safe(callback.message.chat.id, callback.message.message_id)
    except Exception:
        pass

    await render_single_main_menu(callback.from_user.id)
    await callback.answer("Меню обновлено.")

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Возвращает пользователя в главное меню."""
    await state.clear()
    try:
        await delete_message_safe(callback.message.chat.id, callback.message.message_id)
    except Exception:
        pass

    await render_single_main_menu(callback.from_user.id)
    await callback.answer()

# ---------- Административные колбэки ----------
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery) -> None:
    """Панель администратора (только для ADMIN_ID)."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await show_admin_panel(callback)
    await callback.answer()

@dp.callback_query(F.data == "admin_access_menu")
async def admin_access_menu(callback: CallbackQuery) -> None:
    """Меню фильтров для управления доступом."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await show_admin_access_filters(callback)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_users:"))
async def admin_users_list(callback: CallbackQuery) -> None:
    """Показывает список пользователей согласно выбранному фильтру и странице."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    _, access_value, page = callback.data.split(":")
    await show_admin_users_page(
        callback=callback,
        access_value=int(access_value),
        page=int(page),
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_user_card:"))
async def admin_user_card(callback: CallbackQuery) -> None:
    """Показывает карточку выбранного пользователя."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    _, target_user_id, access_value, page = callback.data.split(":")
    await show_admin_user_card(
        callback=callback,
        target_user_id=int(target_user_id),
        access_value=int(access_value),
        page=int(page),
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_toggle_access:"))
async def admin_toggle_access_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Переключает доступ пользователя (вкл/выкл) по команде администратора.
    Если доступ отключается – чистит меню у пользователя.
    """
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    _, target_user_id, new_access, access_value, page = callback.data.split(":")
    target_user_id = int(target_user_id)
    new_access = int(new_access)
    access_value = int(access_value)
    page = int(page)

    logger.info(f"Администратор изменил статус доступа пользователя {target_user_id} на {new_access}")
    await set_user_access(DB_PATH, target_user_id, new_access)

    # Если доступ забрали – удаляем у пользователя меню
    if new_access == 0:
        await state.clear()
        old_menu_message_id = await get_last_menu_message_id(DB_PATH, target_user_id)
        if old_menu_message_id:
            await delete_message_safe(target_user_id, old_menu_message_id)
            await set_last_menu_message_id(DB_PATH, target_user_id, None)

    # Обновляем карточку пользователя у администратора
    await show_admin_user_card(
        callback=callback,
        target_user_id=target_user_id,
        access_value=access_value,
        page=page,
    )
    await callback.answer("Доступ обновлен.")

# ---------- Обработка оплаты (FSM) ----------
@dp.callback_query(F.data.startswith("tariff:"))
async def choose_tariff(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор тарифа: запоминаем данные и переходим в состояние ожидания скриншота."""
    tariff_code = callback.data.split(":")[1]
    tariff = TARIFFS.get(tariff_code)

    if not tariff:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    await state.update_data(
        tariff_code=tariff.code,
        tariff_days=tariff.days,
        amount=tariff.price,
        tariff_title=tariff.title,
    )
    await state.set_state(PaymentStates.waiting_for_screenshot)

    text = build_tariff_payment_text(
        tariff_title=tariff.title,
        amount=tariff.price,
        payment_link=PAYMENT_LINK,
    )

    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=get_tariff_selected_keyboard(),
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=get_tariff_selected_keyboard(),
                disable_web_page_preview=True,
            )
    except Exception:
        await bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=get_tariff_selected_keyboard(),
            disable_web_page_preview=True,
        )

    await callback.answer()

@dp.message(PaymentStates.waiting_for_screenshot, F.photo)
async def process_screenshot(message: Message, state: FSMContext) -> None:
    """
    Получает скриншот оплаты, сохраняет заявку в БД и отправляет её администратору.
    """
    data = await state.get_data()

    tariff_code = data.get("tariff_code")
    tariff_days = data.get("tariff_days")
    amount = data.get("amount")
    tariff_title = data.get("tariff_title")

    if not tariff_code:
        logger.error(f"Данные тарифа FSM не найдены для пользователя {message.from_user.id}")
        await bot.send_message(
            message.chat.id,
            "Ошибка: данные тарифа не найдены. Нажми /start и попробуйте снова.",
        )
        await state.clear()
        return

    screenshot_file_id = message.photo[-1].file_id

    request_id = await create_payment_request(
        DB_PATH,
        telegram_id=message.from_user.id,
        tariff_code=tariff_code,
        tariff_days=tariff_days,
        amount=amount,
        screenshot_file_id=screenshot_file_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(f"Создана заявка на оплату #{request_id} от пользователя {message.from_user.id} ({tariff_title})")
    await delete_user_message_safe(message)
    await bot.send_message(message.chat.id, build_request_sent_text())
    await state.clear()

    user = await get_user(DB_PATH, message.from_user.id)
    display_name = safe_user_name(
        username=user.get("username") if user else None,
        full_name=user.get("full_name") if user else None,
        user_id=message.from_user.id,
    )

    admin_caption = build_admin_request_caption(
        request_id=request_id,
        display_name=display_name,
        telegram_id=message.from_user.id,
        tariff_title=tariff_title,
        amount=amount,
    )

    # Отправляем заявку администратору
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=screenshot_file_id,
        caption=admin_caption,
        reply_markup=get_admin_request_keyboard(request_id),
    )

    await render_single_main_menu(message.from_user.id)

@dp.message(PaymentStates.waiting_for_screenshot)
async def process_non_photo_when_waiting_screenshot(message: Message, state: FSMContext) -> None:
    """Если пользователь отправляет не фото, а что-то другое – просим загрузить фото."""
    await delete_user_message_safe(message)

    old_menu_message_id = await get_last_menu_message_id(DB_PATH, message.from_user.id)
    if old_menu_message_id:
        await delete_message_safe(message.chat.id, old_menu_message_id)
        await set_last_menu_message_id(DB_PATH, message.from_user.id, None)

    await bot.send_message(
        message.chat.id,
        build_invalid_screenshot_text(),
        reply_markup=get_back_to_tariffs_keyboard(),
    )

# ---------- Обработка заявок администратором ----------
@dp.callback_query(F.data.startswith("admin_approve:"))
async def admin_approve_request(callback: CallbackQuery) -> None:
    """
    Одобрение заявки на оплату:
    - продлевает подписку в панели Remnawave,
    - обновляет БД,
    - начисляет реферальный бонус (если есть),
    - уведомляет пользователя.
    """
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У Вас нет доступа к этой функции.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    request_data = await get_request_by_id(DB_PATH, request_id)

    if not request_data:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if request_data["status"] != "pending":
        await callback.answer("Эта заявка уже обработана.", show_alert=True)
        return

    buyer_id = request_data["telegram_id"]
    user = await get_user(DB_PATH, buyer_id)
    if not user:
        logger.error(f"Пользователь для заявки #{request_id} не найден в базе данных.")
        await callback.message.answer(
            f"Ошибка: пользователь для заявки #{request_id} не найден в локальной базе."
        )
        await callback.answer()
        return

    try:
        logger.info(f"Администратор одобряет заявку #{request_id}. Продление в Remnawave на {request_data['tariff_days']} дней.")
        # 1. Продлеваем/активируем подписку покупателю в Remnawave
        result = await remnawave_client.ensure_user_and_extend(
            telegram_id=buyer_id,
            telegram_username=user.get("username"),
            days=request_data["tariff_days"],
            current_user_uuid=user.get("remnawave_user_uuid"),
        )

        # 2. Переводим заявку в статус одобренной
        await update_request_status(
            DB_PATH,
            request_id=request_id,
            status="approved",
            processed_at=datetime.now(timezone.utc).isoformat(),
            processed_by=callback.from_user.id,
        )

        # 3. Обновляем данные подписки покупателя в локальной БД
        await set_user_subscription_data(
            DB_PATH,
            telegram_id=buyer_id,
            remnawave_user_uuid=result.get("user_uuid"),
            subscription_url=result.get("subscription_url"),
            subscription_expires_at=result.get("expires_at"),
        )

        # Уведомляем покупателя об успешном продлении
        await bot.send_message(
            buyer_id,
            build_user_request_accepted_text(request_data["tariff_days"]),
        )

        # Реферальный бонус: если оплатил реферал – добавляем дни пригласившему
        if REFERRAL_BONUS_DAYS > 0:
            referrer_id = await reward_referrer_if_exists(DB_PATH, new_user_id=buyer_id, bonus_days=REFERRAL_BONUS_DAYS)
            
            if referrer_id:
                logger.info(f"Реферал {buyer_id} оплатил тариф. Начисление бонуса пригласителю {referrer_id}.")
                referrer_user = await get_user(DB_PATH, referrer_id)
                if referrer_user and referrer_user.get("access_granted") == 1:
                    try:
                        if referrer_user.get("remnawave_user_uuid"):
                            await remnawave_client.ensure_user_and_extend(
                                telegram_id=referrer_id,
                                telegram_username=referrer_user.get("username"),
                                days=REFERRAL_BONUS_DAYS,
                                current_user_uuid=referrer_user.get("remnawave_user_uuid")
                            )
                        
                        await bot.send_message(
                            referrer_id,
                            f"🎁 <b>Ваш реферал оплатил подписку!</b>\n\n"
                            f"Вам успешно начислено <b>+{REFERRAL_BONUS_DAYS} дней</b> к Вашей активной подписке. "
                            f"Спасибо, что рекомендуете наш сервис!"
                        )
                    except Exception as ref_err:
                        logger.error(f"[REFERRAL ERROR] Ошибка синхронизации бонуса с панелью для {referrer_id}: {ref_err}")

        # Обновляем главное меню покупателя
        await render_single_main_menu(buyer_id)

        # Изменяем клавиатуру у сообщения администратора (заменяем кнопки на "одобрено")
        try:
            await callback.message.edit_reply_markup(
                reply_markup=get_admin_processed_keyboard("approved"),
            )
        except Exception:
            pass

        await callback.answer("Заявка одобрена.")
    except Exception as e:
        logger.exception(f"Исключение при одобрении заявки #{request_id}:")
        await callback.message.answer(
            f"❌ <b>Ошибка при апруве заявки #{request_id}</b>\n\n"
            f"<code>{str(e)}</code>"
        )
        await callback.answer("Ошибка при обработке.", show_alert=True)

@dp.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject_request(callback: CallbackQuery) -> None:
    """Отклонение заявки: обновляем статус и уведомляем пользователя."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У Вас нет доступа к этой функции.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    request_data = await get_request_by_id(DB_PATH, request_id)

    if not request_data:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if request_data["status"] != "pending":
        await callback.answer("Эта заявка уже обработана.", show_alert=True)
        return

    logger.info(f"Администратор отклонил заявку #{request_id} от пользователя {request_data['telegram_id']}")
    await update_request_status(
        DB_PATH,
        request_id=request_id,
        status="rejected",
        processed_at=datetime.now(timezone.utc).isoformat(),
        processed_by=callback.from_user.id,
    )

    await bot.send_message(
        request_data["telegram_id"],
        build_user_request_rejected_text(),
    )
    await render_single_main_menu(request_data["telegram_id"])

    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_admin_processed_keyboard("rejected"),
        )
    except Exception:
        pass

    await callback.answer("Заявка отклонена.")

# 10. Фоновый планировщик напоминаний об окончании подписки
async def reminder_scheduler() -> None:
    """
    Периодически проверяет пользователей с активной подпиской:
    - за 3 дня до окончания отправляет предупреждение,
    - за 1 день – финальное напоминание.
    """
    logger.info("[REMINDER] Фоновый планировщик напоминаний успешно запущен.")
    while True:
        try:
            logger.debug("[REMINDER] Проверка истекающих подписок...")
            users = await get_users_for_reminder_check(DB_PATH)

            for user in users:
                telegram_id = user["telegram_id"]

                # Синхронизируем данные с панелью
                synced_user = await sync_user_subscription_with_panel(telegram_id)
                if not synced_user:
                    continue

                expires_at = synced_user.get("subscription_expires_at")
                if not expires_at:
                    continue

                days_left = calculate_days_left(expires_at)
                expiry_date_key = expires_at.split("T")[0]  # используем дату как ключ

                # Отправка напоминания за 3 дня
                if days_left == 3:
                    if not await was_expiry_reminder_sent_by_type(DB_PATH, telegram_id, "expiry_3_days", expiry_date_key):
                        await asyncio.sleep(0.05)  # небольшая задержка между сообщениями
                        try:
                            logger.info(f"[REMINDER] Отправка уведомления за 3 дня пользователю {telegram_id}")
                            await bot.send_message(telegram_id, build_expiry_three_days_reminder_text())
                            await mark_expiry_reminder_sent_by_type(DB_PATH, telegram_id, "expiry_3_days", expiry_date_key)
                        except Exception as e:
                            logger.error(f"[REMINDER] Ошибка отправки (3 дня) для {telegram_id}: {e}")

                # Отправка напоминания за 1 день
                elif days_left == 1:
                    if not await was_expiry_reminder_sent_by_type(DB_PATH, telegram_id, "expiry_1_day", expiry_date_key):
                        await asyncio.sleep(0.05)
                        try:
                            logger.info(f"[REMINDER] Отправка уведомления за 1 день пользователю {telegram_id}")
                            await bot.send_message(telegram_id, build_expiry_reminder_text())
                            await mark_expiry_reminder_sent_by_type(DB_PATH, telegram_id, "expiry_1_day", expiry_date_key)
                        except Exception as e:
                            logger.error(f"[REMINDER] Ошибка отправки (1 день) для {telegram_id}: {e}")

        except Exception as e:
            logger.exception("[REMINDER] Критическая ошибка в цикле планировщика напоминаний:")
            
        await asyncio.sleep(REMIDER_CHECK_INTERVAL_SECONDS)

# 11. Основная асинхронная функция запуска бота
async def main() -> None:
    """Инициализация БД, проверка конфигурации, запуск polling и планировщика."""
    # Валидация критических переменных среды
    if not BOT_TOKEN:
        logger.critical("Конфигурация повреждена: отсутствует BOT_TOKEN в файле конфигурации окружения.")
        raise ValueError("Не задан BOT_TOKEN в .env")

    if not ADMIN_ID:
        logger.critical("Конфигурация повреждена: отсутствует ADMIN_ID в файле конфигурации окружения.")
        raise ValueError("Не задан ADMIN_ID в .env")

    if not REMNAWAVE_BASE_URL or not REMNAWAVE_TOKEN:
        logger.critical("Конфигурация повреждена: не заданы параметры интеграции REMNAWAVE.")
        raise ValueError("Не заданы REMNAWAVE_BASE_URL или REMNAWAVE_TOKEN в .env")

    logger.info("Инициализация таблиц базы данных SQLite...")
    await init_db(DB_PATH)

    logger.info("Сброс старых вебхуков Telegram (drop_pending_updates=True)...")
    await bot.delete_webhook(drop_pending_updates=True)

    # Создание фоновой асинхронной задачи планировщика
    asyncio.create_task(reminder_scheduler())

    logger.info("🚀 Бот успешно прошёл инициализацию и начинает Polling!")
    logger.info(f"   Admin ID: {ADMIN_ID}")
    logger.info(f"   Remnawave URL: {REMNAWAVE_BASE_URL}")
    if REMNAWAVE_DEFAULT_SQUAD_UUID:
        logger.info(f"   Default squad UUID: {REMNAWAVE_DEFAULT_SQUAD_UUID[:8]}...")
    else:
        logger.warning("   Default squad UUID: НЕ ЗАДАН")
    logger.info(f"   Интервал проверки планировщика: {REMIDER_CHECK_INTERVAL_SECONDS} сек.")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception("Критическое исключение диспетчера в процессе опроса серверов:")
    finally:
        logger.info("Работа бота завершена.")

# 12. Точка входа
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Процесс завершён пользователем (SIGINT/SIGTERM).")