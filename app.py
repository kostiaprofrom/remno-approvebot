import asyncio
import logging
import math
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

# Загрузка переменных окружения и настройка логирования в консоль
load_dotenv()
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").strip().upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Импорт конфигурационных данных, клавиатур, утилит и методов работы с БД
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
)
from states import AccessStates, PaymentStates
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
from db import (
    init_db,
    create_or_update_user,
    get_user,
    grant_access,
    create_payment_request,
    get_request_by_id,
    update_request_status,
    get_pending_requests,
    get_paginated_users_by_access,
    count_users_by_access,
    toggle_user_access,
    get_all_active_users_for_reminder,
    mark_expiry_reminder_sent_by_type,
    process_referral_on_access_grant,
)
from text_utils import (
    build_welcome_text,
    build_main_menu_text,
    build_tariffs_text,
    build_admin_panel_text,
    build_admin_requests_list_text,
    build_admin_request_details_text,
    build_admin_users_list_text,
    build_admin_user_card_text,
    build_expiry_reminder_text,
    build_referral_menu_text,
)
from remnawave_api_client import RemnawaveClient

# Проверка обязательных переменных окружения для работы бота и API
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0").strip())
REMNAWAVE_BASE_URL = os.getenv("REMNAWAVE_BASE_URL", "").strip()
REMNAWAVE_TOKEN = os.getenv("REMNAWAVE_TOKEN", "").strip()
REMNAWAVE_DEFAULT_SQUAD_UUID = os.getenv("REMNAWAVE_DEFAULT_SQUAD_UUID", "").strip()

# Инициализация объектов бота, диспетчера aiogram и клиента Remnawave
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
remnawave = RemnawaveClient(
    base_url=REMNAWAVE_BASE_URL,
    token=REMNAWAVE_TOKEN,
    default_squad_uuid=REMNAWAVE_DEFAULT_SQUAD_UUID,
)


async def send_or_edit_main_menu(
    telegram_id: int,
    username: str | None,
    full_name: str | None,
    message_to_edit_id: int | None = None,
    query_to_answer: CallbackQuery | None = None,
) -> None:
    # Вспомогательная функция для отображения или обновления главного меню
    user_data = await get_user(DB_PATH, telegram_id)
    if not user_data:
        user_data = await create_or_update_user(
            DB_PATH, telegram_id, username, full_name
        )

    is_admin = telegram_id == ADMIN_ID
    text = build_main_menu_text(user_data, is_admin)
    reply_markup = get_main_menu_keyboard(is_admin)

    try:
        if message_to_edit_id:
            await bot.edit_message_caption(
                chat_id=telegram_id,
                message_id=message_to_edit_id,
                caption=text,
                reply_markup=reply_markup,
            )
        else:
            if os.path.exists(HERO_IMAGE_PATH):
                with open(HERO_IMAGE_PATH, "rb") as f:
                    msg = await bot.send_photo(
                        chat_id=telegram_id,
                        photo=BufferedInputFile(f.read(), filename="menu.jpg"),
                        caption=text,
                        reply_markup=reply_markup,
                    )
                await create_or_update_user(
                    DB_PATH,
                    telegram_id,
                    username,
                    full_name,
                    last_menu_message_id=msg.message_id,
                )
            else:
                msg = await bot.send_message(
                    chat_id=telegram_id, text=text, reply_markup=reply_markup
                )
                await create_or_update_user(
                    DB_PATH,
                    telegram_id,
                    username,
                    full_name,
                    last_menu_message_id=msg.message_id,
                )
    except Exception as e:
        logger.error(f"Ошибка обновления/отправки главного меню для {telegram_id}: {e}")
        if not message_to_edit_id:
            await bot.send_message(
                chat_id=telegram_id, text=text, reply_markup=reply_markup
            )

    if query_to_answer:
        try:
            await query_to_answer.answer()
        except Exception:
            pass


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    # Обработчик команды /start, регистрация пользователя и проверка реферальной ссылки
    await state.clear()
    telegram_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    args = message.text.split()
    referred_by = None
    if len(args) > 1 and args[1].isdigit():
        ref_id_candidate = int(args[1])
        if ref_id_candidate != telegram_id:
            referred_by = ref_id_candidate

    user_data = await get_user(DB_PATH, telegram_id)
    if not user_data:
        user_data = await create_or_update_user(
            DB_PATH,
            telegram_id,
            username,
            full_name,
            referred_by=referred_by,
        )
        if referred_by:
            logger.info(f"Пользователь {telegram_id} зарегистрировался по ссылке от {referred_by}")

    if user_data.get("access_granted") == 1:
        await send_or_edit_main_menu(telegram_id, username, full_name)
        return

    text = build_welcome_text()
    if os.path.exists(WELCOME_IMAGE_PATH):
        with open(WELCOME_IMAGE_PATH, "rb") as f:
            await message.answer_photo(
                photo=BufferedInputFile(f.read(), filename="welcome.jpg"),
                caption=text,
            )
    else:
        await message.answer(text)

    await state.set_state(AccessStates.waiting_for_access_code)


@dp.message(AccessStates.waiting_for_access_code)
async def process_access_code(message: Message, state: FSMContext) -> None:
    # Проверка инвайт-кода и создание первой бесплатной подписки в Remnawave
    telegram_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    code_input = message.text.strip() if message.text else ""

    if code_input == ACCESS_CODE:
        await state.clear()
        logger.info(f"Пользователь {telegram_id} ввёл верный инвайт-код.")

        res = await remnawave.ensure_user_and_extend(
            telegram_id=telegram_id,
            telegram_username=username,
            days=30,
            current_user_uuid=None,
        )

        if res.get("success"):
            await grant_access(
                db_path=DB_PATH,
                telegram_id=telegram_id,
                code_used=code_input,
                remnawave_user_uuid=res.get("user_uuid"),
                subscription_url=res.get("subscription_url"),
                subscription_expires_at=res.get("expires_at"),
            )
            await process_referral_on_access_grant(DB_PATH, telegram_id, REFERRAL_BONUS_DAYS)
            await message.answer("🎉 Код верный! Доступ успешно предоставлен на 30 дней.")
            await send_or_edit_main_menu(telegram_id, username, full_name)
        else:
            logger.error(f"Remnawave error при вводе инвайт-кода для {telegram_id}: {res.get('error')}")
            await message.answer(
                "❌ Произошла ошибка на стороне VPN-панели при создании аккаунта. Обратитесь к администратору."
            )
    else:
        await message.answer("❌ Неверный код доступа. Пожалуйста, попробуйте еще раз или введите корректный инвайт-код:")


@dp.callback_query(F.data == "refresh_main")
async def callback_refresh_main(query: CallbackQuery) -> None:
    # Синхронизация статуса подписки и даты окончания из API Remnawave
    telegram_id = query.from_user.id
    user_data = await get_user(DB_PATH, telegram_id)

    if user_data and user_data.get("remnawave_user_uuid"):
        res = await remnawave.find_user(
            telegram_id=telegram_id,
            telegram_username=query.from_user.username,
            current_user_uuid=user_data.get("remnawave_user_uuid"),
        )
        if res:
            expires_at_str = res.get("expire_at") or res.get("expireAt") or ""
            subscription_url = remnawave._extract_subscription_url(res) or user_data.get("subscription_url")

            user_data = await create_or_update_user(
                DB_PATH,
                telegram_id,
                query.from_user.username,
                query.from_user.full_name,
                subscription_expires_at=expires_at_str,
                subscription_url=subscription_url,
            )
            logger.debug(f"Синхронизированы данные из Remnawave для {telegram_id}")

    await send_or_edit_main_menu(
        telegram_id=telegram_id,
        username=query.from_user.username,
        full_name=query.from_user.full_name,
        message_to_edit_id=query.message.message_id,
        query_to_answer=query,
    )


@dp.callback_query(F.data == "back_to_main")
async def callback_back_to_main(query: CallbackQuery, state: FSMContext) -> None:
    # Возврат пользователя в главное меню из любого состояния
    await state.clear()
    await send_or_edit_main_menu(
        telegram_id=query.from_user.id,
        username=query.from_user.username,
        full_name=query.from_user.full_name,
        message_to_edit_id=query.message.message_id,
        query_to_answer=query,
    )


@dp.callback_query(F.data == "referral_menu")
async def callback_referral_menu(query: CallbackQuery) -> None:
    # Отображение меню реферальной программы и генерация ссылки приглашения
    telegram_id = query.from_user.id
    bot_info = await bot.get_me()
    bot_username = bot_info.username

    user_data = await get_user(DB_PATH, telegram_id)
    text = build_referral_menu_text(user_data, bot_username, REFERRAL_BONUS_DAYS)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
        ]
    )

    await bot.edit_message_caption(
        chat_id=telegram_id,
        message_id=query.message.message_id,
        caption=text,
        reply_markup=keyboard,
    )
    await query.answer()


@dp.callback_query(F.data == "open_tariffs")
async def callback_open_tariffs(query: CallbackQuery) -> None:
    # Вывод списка доступных тарифов для продления
    text = build_tariffs_text()
    reply_markup = get_tariffs_keyboard()

    await bot.edit_message_caption(
        chat_id=query.from_user.id,
        message_id=query.message.message_id,
        caption=text,
        reply_markup=reply_markup,
    )
    await query.answer()


@dp.callback_query(F.data.startswith("tariff:"))
async def callback_select_tariff(query: CallbackQuery, state: FSMContext) -> None:
    # Выбор конкретного тарифа, вывод реквизитов и перевод в режим ожидания чека
    tariff_code = query.data.split(":")[1]
    tariff = TARIFFS.get(tariff_code)

    if not tariff:
        await query.answer("Тариф не найден.", show_alert=True)
        return

    await state.update_data(tariff_code=tariff.code, tariff_days=tariff.days, amount=tariff.price)

    text = (
        f"<b>Выбран тариф:</b> {tariff.title}\n"
        f"<b>Стоимость:</b> {tariff.price} ₽\n\n"
        f"Пожалуйста, переведите <code>{tariff.price}</code> ₽ по указанной ссылке:\n"
        f"🔗 <a href='{PAYMENT_LINK}'>Ссылка на оплату</a>\n\n"
        f"После оплаты отправьте <b>скриншот квитанции</b> (прямо сюда в чат) в качестве подтверждения."
    )
    reply_markup = get_back_to_tariffs_keyboard()

    await bot.edit_message_caption(
        chat_id=query.from_user.id,
        message_id=query.message.message_id,
        caption=text,
        reply_markup=reply_markup,
    )
    await state.set_state(PaymentStates.waiting_for_screenshot)
    await query.answer()


@dp.message(PaymentStates.waiting_for_screenshot, F.photo)
async def process_payment_screenshot(message: Message, state: FSMContext) -> None:
    # Обработка скриншота оплаты, создание заявки в БД и отправка уведомления админу
    telegram_id = message.from_user.id
    user_data = await get_user(DB_PATH, telegram_id)
    last_menu_id = user_data.get("last_menu_message_id") if user_data else None

    state_data = await state.get_data()
    tariff_code = state_data.get("tariff_code")
    tariff_days = state_data.get("tariff_days")
    amount = state_data.get("amount")

    screenshot_file_id = message.photo[-1].file_id
    created_at_str = datetime.now(timezone.utc).isoformat()

    req_id = await create_payment_request(
        db_path=DB_PATH,
        telegram_id=telegram_id,
        tariff_code=tariff_code,
        tariff_days=tariff_days,
        amount=amount,
        screenshot_file_id=screenshot_file_id,
        created_at=created_at_str,
    )

    await state.clear()
    logger.info(f"Пользователь {telegram_id} отправил скриншот оплаты. Создана заявка #{req_id}.")

    if last_menu_id:
        try:
            await bot.edit_message_reply_markup(
                chat_id=telegram_id, message_id=last_menu_id, reply_markup=None
            )
        except Exception:
            pass

    await message.answer(
        f"⏳ <b>Заявка #{req_id} успешно создана!</b>\n\n"
        f"Администратор проверит скриншот в ближайшее время. "
        f"Вы получите уведомление о результате проверки."
    )

    await send_or_edit_main_menu(telegram_id, message.from_user.username, message.from_user.full_name)

    try:
        admin_text = (
            f"🔔 <b>Новая заявка на оплату #{req_id}!</b>\n"
            f"От: ID {telegram_id} (@{message.from_user.username or 'нет'})\n"
            f"Сумма: {amount} ₽ (Тариф: {tariff_code})"
        )
        await bot.send_photo(
            chat_id=ADMIN_ID,
            photo=screenshot_file_id,
            caption=admin_text,
            reply_markup=get_admin_request_keyboard(req_id),
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление админу: {e}")


# Раздел административной панели бота
@dp.callback_query(F.data == "admin_panel")
async def callback_admin_panel(query: CallbackQuery) -> None:
    # Открытие главного меню панели администратора
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    text = build_admin_panel_text()
    reply_markup = get_admin_panel_keyboard()

    await bot.edit_message_caption(
        chat_id=ADMIN_ID,
        message_id=query.message.message_id,
        caption=text,
        reply_markup=reply_markup,
    )
    await query.answer()


@dp.callback_query(F.data == "admin_pending_requests")
async def callback_admin_pending_requests(query: CallbackQuery) -> None:
    # Просмотр списка всех необработанных заявок на оплату
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    reqs = await get_pending_requests(DB_PATH)
    text = build_admin_requests_list_text(reqs)

    keyboard = []
    for r in reqs:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"Заявка #{r['id']} ({r['amount']}₽)",
                    callback_data=f"admin_view_req:{r['id']}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_panel")])

    await bot.edit_message_caption(
        chat_id=ADMIN_ID,
        message_id=query.message.message_id,
        caption=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await query.answer()


@dp.callback_query(F.data.startswith("admin_view_req:"))
async def callback_admin_view_req(query: CallbackQuery) -> None:
    # Детальный просмотр конкретной заявки со скриншотом чека
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    req_id = int(query.data.split(":")[1])
    req = await get_request_by_id(DB_PATH, req_id)

    if not req:
        await query.answer("Заявка не найдена.", show_alert=True)
        return

    text = build_admin_request_details_text(req)

    try:
        await bot.delete_message(chat_id=ADMIN_ID, message_id=query.message.message_id)
    except Exception:
        pass

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=req["screenshot_file_id"],
        caption=text,
        reply_markup=get_admin_request_keyboard(req_id),
    )
    await query.answer()


@dp.callback_query(F.data.startswith("admin_approve:"))
async def callback_admin_approve(query: CallbackQuery) -> None:
    # Одобрение заявки, автоматическое продление подписки в Remnawave и уведомление юзера
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    req_id = int(query.data.split(":")[1])
    req = await get_request_by_id(DB_PATH, req_id)

    if not req or req["status"] != "pending":
        await query.answer("Заявка уже обработана или не найдена.", show_alert=True)
        return

    processed_at_str = datetime.now(timezone.utc).isoformat()
    await update_request_status(DB_PATH, req_id, "approved", processed_at_str, ADMIN_ID)
    logger.info(f"Администратор одобрил заявку #{req_id}.")

    target_id = req["telegram_id"]
    days_to_add = req["tariff_days"]

    target_user = await get_user(DB_PATH, target_id)
    current_uuid = target_user.get("remnawave_user_uuid") if target_user else None

    res = await remnawave.ensure_user_and_extend(
        telegram_id=target_id,
        telegram_username=target_user.get("username") if target_user else None,
        days=days_to_add,
        current_user_uuid=current_uuid,
    )

    if res.get("success"):
        await grant_access(
            db_path=DB_PATH,
            telegram_id=target_id,
            code_used=f"PURCHASE_{req['tariff_code']}",
            remnawave_user_uuid=res.get("user_uuid"),
            subscription_url=res.get("subscription_url"),
            subscription_expires_at=res.get("expires_at"),
        )

        try:
            if query.message.photo:
                await bot.edit_message_reply_markup(
                    chat_id=ADMIN_ID,
                    message_id=query.message.message_id,
                    reply_markup=get_admin_processed_keyboard("ОДОБРЕНО ✅"),
                )
            else:
                await bot.edit_message_text(
                    chat_id=ADMIN_ID,
                    message_id=query.message.message_id,
                    text=f"Заявка #{req_id} успешно одобрена. Доступ продлен.",
                    reply_markup=get_admin_processed_keyboard("ОДОБРЕНО ✅"),
                )
        except Exception:
            pass

        try:
            await bot.send_message(
                chat_id=target_id,
                text=f"✅ <b>Ваша заявка #{req_id} одобрена!</b>\nПродление на {days_to_add} дн. успешно активировано.",
            )
            if target_user and target_user.get("last_menu_message_id"):
                await send_or_edit_main_menu(
                    telegram_id=target_id,
                    username=target_user.get("username"),
                    full_name=target_user.get("full_name"),
                    message_to_edit_id=target_user.get("last_menu_message_id"),
                )
        except Exception as e:
            logger.error(f"Не удалось обновить меню или уведомить пользователя {target_id}: {e}")

        await query.answer("Заявка одобрена!", show_alert=False)
    else:
        logger.error(f"Remnawave error при одобрении заявки #{req_id}: {res.get('error')}")
        await query.answer(f"Ошибка Remnawave: {res.get('error')}", show_alert=True)


@dp.callback_query(F.data.startswith("admin_reject:"))
async def callback_admin_reject(query: CallbackQuery) -> None:
    # Отклонение заявки администратором с уведомлением пользователя
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    req_id = int(query.data.split(":")[1])
    req = await get_request_by_id(DB_PATH, req_id)

    if not req or req["status"] != "pending":
        await query.answer("Заявка уже обработана или не найдена.", show_alert=True)
        return

    processed_at_str = datetime.now(timezone.utc).isoformat()
    await update_request_status(DB_PATH, req_id, "rejected", processed_at_str, ADMIN_ID)
    logger.info(f"Администратор отклонил заявку #{req_id}.")

    try:
        if query.message.photo:
            await bot.edit_message_reply_markup(
                chat_id=ADMIN_ID,
                message_id=query.message.message_id,
                reply_markup=get_admin_processed_keyboard("ОТКЛОНЕНО ❌"),
            )
        else:
            await bot.edit_message_text(
                chat_id=ADMIN_ID,
                message_id=query.message.message_id,
                text=f"Заявка #{req_id} отклонена.",
                reply_markup=get_admin_processed_keyboard("ОТКЛОНЕНО ❌"),
            )
    except Exception:
        pass

    try:
        await bot.send_message(
            chat_id=req["telegram_id"],
            text=f"❌ <b>Ваша заявка #{req_id} на оплату отклонена.</b>\n"
            f"Если это ошибка, проверьте квитанцию или свяжитесь с администратором.",
        )
    except Exception:
        pass

    await query.answer("Заявка отклонена.", show_alert=False)


@dp.callback_query(F.data == "admin_access_menu")
async def callback_admin_access_menu(query: CallbackQuery) -> None:
    # Отображение фильтров для работы со списком пользователей
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    text = "Выберите фильтр для отображения списка пользователей:"
    reply_markup = get_admin_access_filters_keyboard()

    if query.message.photo:
        try:
            await bot.delete_message(chat_id=ADMIN_ID, message_id=query.message.message_id)
        except Exception:
            pass
        await bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=reply_markup)
    else:
        await bot.edit_message_text(
            chat_id=ADMIN_ID,
            message_id=query.message.message_id,
            text=text,
            reply_markup=reply_markup,
        )
    await query.answer()


@dp.callback_query(F.data.startswith("admin_users:"))
async def callback_admin_users_list(query: CallbackQuery) -> None:
    # Вывод постраничного списка пользователей с учетом выбранного фильтра
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    parts = query.data.split(":")
    access_value = int(parts[1])
    page = int(parts[2])

    total_users = await count_users_by_access(DB_PATH, access_value)
    total_pages = math.ceil(total_users / ADMIN_USERS_PER_PAGE)
    if total_pages == 0:
        total_pages = 1
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    users_list = await get_paginated_users_by_access(
        DB_PATH, access_value, page, ADMIN_USERS_PER_PAGE
    )
    text = build_admin_users_list_text(users_list, access_value, page, total_pages, total_users)
    reply_markup = get_admin_users_keyboard(users_list, access_value, page, total_pages)

    if query.message.photo:
        try:
            await bot.delete_message(chat_id=ADMIN_ID, message_id=query.message.message_id)
        except Exception:
            pass
        await bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=reply_markup)
    else:
        await bot.edit_message_text(
            chat_id=ADMIN_ID,
            message_id=query.message.message_id,
            text=text,
            reply_markup=reply_markup,
        )
    await query.answer()


@dp.callback_query(F.data.startswith("admin_user_card:"))
async def callback_admin_user_card(query: CallbackQuery) -> None:
    # Просмотр детальной карточки пользователя администратором
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    parts = query.data.split(":")
    target_id = int(parts[1])
    return_access_value = int(parts[2])
    return_page = int(parts[3])

    user_data = await get_user(DB_PATH, target_id)
    if not user_data:
        await query.answer("Пользователь не найден.", show_alert=True)
        return

    text = build_admin_user_card_text(user_data)
    reply_markup = get_admin_user_card_keyboard(
        telegram_id=target_id,
        current_access=user_data.get("access_granted", 0),
        return_access_value=return_access_value,
        return_page=return_page,
    )

    await bot.edit_message_text(
        chat_id=ADMIN_ID,
        message_id=query.message.message_id,
        text=text,
        reply_markup=reply_markup,
    )
    await query.answer()


@dp.callback_query(F.data.startswith("admin_toggle_access:"))
async def callback_admin_toggle_access(query: CallbackQuery) -> None:
    # Принудительное включение/выключение доступа пользователю из карточки
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    parts = query.data.split(":")
    target_id = int(parts[1])
    new_access = int(parts[2])
    return_access_value = int(parts[3])
    return_page = int(parts[4])

    await toggle_user_access(DB_PATH, target_id, new_access)
    logger.info(f"Администратор изменил доступ пользователя {target_id} на {new_access}.")

    target_user = await get_user(DB_PATH, target_id)
    if target_user and target_user.get("remnawave_user_uuid"):
        try:
            if new_access == 0:
                past_date = datetime(2000, 1, 1, tzinfo=timezone.utc)
                await remnawave.update_user_expiry(
                    user_uuid=target_user.get("remnawave_user_uuid"),
                    new_expire_at=past_date,
                    user=None,
                )
            else:
                future_date = datetime.now(timezone.utc) + asyncio.timedelta(days=30)
                await remnawave.update_user_expiry(
                    user_uuid=target_user.get("remnawave_user_uuid"),
                    new_expire_at=future_date,
                    user=None,
                )
        except Exception as e:
            logger.error(f"Не удалось обновить статус в панели Remnawave для {target_id}: {e}")

    updated_user = await get_user(DB_PATH, target_id)
    text = build_admin_user_card_text(updated_user)
    reply_markup = get_admin_user_card_keyboard(
        telegram_id=target_id,
        current_access=updated_user.get("access_granted", 0),
        return_access_value=return_access_value,
        return_page=return_page,
    )

    await bot.edit_message_text(
        chat_id=ADMIN_ID,
        message_id=query.message.message_id,
        text=text,
        reply_markup=reply_markup,
    )
    await query.answer("Статус доступа изменен.", show_alert=False)


# Фоновый планировщик уведомлений об окончании подписки
async def reminder_scheduler() -> None:
    # Бесконечный цикл проверки и рассылки уведомлений за 3 дня и за 1 день
    while True:
        try:
            logger.debug("Запуск проверки окончания подписок планировщиком...")
            active_users = await get_all_active_users_for_reminder(DB_PATH)
            now = datetime.now(timezone.utc)

            for user in active_users:
                telegram_id = user["telegram_id"]
                expires_str = user["subscription_expires_at"]

                if not expires_str:
                    continue

                try:
                    s = str(expires_str).replace("Z", "+00:00")
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
                except Exception:
                    continue

                diff = expire_dt - now
                days_left = diff.total_seconds() / 86400.0
                expiry_date_key = expire_dt.date().isoformat()

                if 2.0 < days_left <= 3.0:
                    if user.get("reminder_3_days_sent") != expiry_date_key:
                        await asyncio.sleep(0.05)
                        try:
                            await bot.send_message(
                                chat_id=telegram_id,
                                text="⚠️ <b>Внимание!</b> До окончания вашей подписки осталось менее 3 дней. Рекомендуем продлить её заранее.",
                            )
                            await mark_expiry_reminder_sent_by_type(
                                DB_PATH, telegram_id, "expiry_3_days", expiry_date_key
                            )
                        except Exception as e:
                            logger.error(f"Ошибка отправки напоминания (3 дня) пользователю {telegram_id}: {e}")

                elif 0.0 < days_left <= 1.0:
                    if user.get("reminder_1_day_sent") != expiry_date_key:
                        await asyncio.sleep(0.05)
                        try:
                            await bot.send_message(
                                chat_id=telegram_id,
                                text=build_expiry_reminder_text(),
                            )
                            await mark_expiry_reminder_sent_by_type(
                                DB_PATH, telegram_id, "expiry_1_day", expiry_date_key
                            )
                        except Exception as e:
                            logger.error(f"Ошибка отправки напоминания (1 день) пользователю {telegram_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка в работе планировщика уведомлений: {e}")

        await asyncio.sleep(REMIDER_CHECK_INTERVAL_SECONDS)


# Асинхронная точка входа для инициализации и запуска бота
async def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("Не задан BOT_TOKEN в .env")
    if not ADMIN_ID:
        raise ValueError("Не задан ADMIN_ID в .env")
    if not REMNAWAVE_BASE_URL or not REMNAWAVE_TOKEN:
        raise ValueError("Не заданы REMNAWAVE_BASE_URL или REMNAWAVE_TOKEN в .env")

    await init_db(DB_PATH)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(reminder_scheduler())

    logger.info("🚀 Бот запущен...")
    logger.info(f"   Admin ID: {ADMIN_ID}")
    logger.info(f"   Remnawave: {REMNAWAVE_BASE_URL}")
    if REMNAWAVE_DEFAULT_SQUAD_UUID:
        logger.info(f"   Default squad: {REMNAWAVE_DEFAULT_SQUAD_UUID[:8]}...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())