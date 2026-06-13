from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import TARIFFS, TRIAL_BUTTON_ENABLED, SUPPORT_BUTTON_ENABLED, SUPPORT_LINK

def get_main_menu_keyboard(
    is_admin: bool = False, 
    show_trial_button: bool = False,
    show_referral_button: bool = False  # ИСПРАВЛЕНО: Добавлен обязательный аргумент
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # 1. Кнопка пробного периода
    if TRIAL_BUTTON_ENABLED and show_trial_button:
        builder.row(
            InlineKeyboardButton(text="🎁 Активировать пробный период", callback_data="activate_trial")
        )
        
    # 2. Кнопка продления подписки
    builder.row(InlineKeyboardButton(text="💳 Продлить подписку", callback_data="open_tariffs"))
    
    # 3. Кнопка реферальной программы (показывается динамически)
    if show_referral_button:
        builder.row(InlineKeyboardButton(text="🤝 Реферальная программа", callback_data="referral_menu"))        
    
    # 4. Кнопка поддержки (внешняя ссылка)
    if SUPPORT_BUTTON_ENABLED and SUPPORT_LINK:
        builder.row(
            InlineKeyboardButton(text="👨‍💻 Поддержка", url=SUPPORT_LINK)
        )
    # 5. Кнопка обновления
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_main"))

    # 6. Кнопка админ-панели
    if is_admin:
        builder.row(InlineKeyboardButton(text="🛠 Админка", callback_data="admin_panel"))
        
    builder.adjust(1)
        
    return builder.as_markup()


def get_tariffs_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for tariff in TARIFFS.values():
        builder.row(
            InlineKeyboardButton(
                text=f"🟢 {tariff.title} — {tariff.price} ₽",
                callback_data=f"tariff:{tariff.code}"
            )
        )
    
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    builder.adjust(1)  # Делаем тарифы тоже в один столбец
    return builder.as_markup()


def get_tariff_selected_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="open_tariffs"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main")
    )
    builder.adjust(1)
    return builder.as_markup()


def get_back_to_tariffs_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад к тарифам", callback_data="open_tariffs"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main")
    )
    builder.adjust(1)
    return builder.as_markup()


def get_admin_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Кнопки «Апрув» и «Реджект» будут красиво стоять в один ряд (две колонки)
    builder.row(
        InlineKeyboardButton(text="✅ Апрув", callback_data=f"admin_approve:{request_id}"),
        InlineKeyboardButton(text="❌ Реджект", callback_data=f"admin_reject:{request_id}")
    )
    return builder.as_markup()


def get_admin_processed_keyboard(status: str) -> InlineKeyboardMarkup:
    label = "✅ Одобрено" if status == "approved" else "❌ Отклонено"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=label, callback_data="admin_processed_noop"))
    return builder.as_markup()


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Управление доступом", callback_data="admin_access_menu"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main")
    )
    builder.adjust(1)
    return builder.as_markup()


def get_admin_access_filters_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Фильтры («Активные» и «Отключённые») встанут в один ряд
    builder.row(
        InlineKeyboardButton(text="✅ Активные", callback_data="admin_users:1:1"),
        InlineKeyboardButton(text="❌ Отключённые", callback_data="admin_users:0:1")
    )
    # Кнопка возврата встанет строкой ниже
    builder.row(InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_panel"))
    return builder.as_markup()


def get_admin_users_keyboard(
    users: list[dict],
    access_value: int,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # Рендерим список пользователей (каждый на своей строке)
    for user in users:
        label = user.get("username") or user.get("full_name") or str(user["telegram_id"])
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {label} ({user['telegram_id']})",
                callback_data=f"admin_user_card:{user['telegram_id']}:{access_value}:{page}"
            )
        )

    # Строка навигации пагинации (стрелочки влево/вправо в один ряд)
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_users:{access_value}:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_users:{access_value}:{page + 1}"))
    
    if nav_row:
        builder.row(*nav_row)

    # Системные кнопки навигации
    builder.row(InlineKeyboardButton(text="⬅️ К фильтрам", callback_data="admin_access_menu"))
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main"))

    return builder.as_markup()


def get_admin_user_card_keyboard(
    telegram_id: int,
    current_access: int,
    return_access_value: int,
    return_page: int,
) -> InlineKeyboardMarkup:
    new_access = 0 if current_access == 1 else 1
    button_text = "🚫 Отключить доступ" if current_access == 1 else "♻️ Вернуть доступ"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=button_text,
            callback_data=f"admin_toggle_access:{telegram_id}:{new_access}:{return_access_value}:{return_page}"
        ),
        InlineKeyboardButton(text="⬅️ К списку", callback_data=f"admin_users:{return_access_value}:{return_page}"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main")
    )
    builder.adjust(1)
    return builder.as_markup()