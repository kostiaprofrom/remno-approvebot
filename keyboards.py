from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TARIFFS


def get_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="💳 Продлить подписку",
                callback_data="open_tariffs"
            )
        ],
        [
            InlineKeyboardButton(
                text="🤝 Реферальная программа",
                callback_data="referral_menu"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="refresh_main"
            )
        ]
    ]

    if is_admin:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🛠 Админка",
                    callback_data="admin_panel"
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_tariffs_keyboard() -> InlineKeyboardMarkup:
    keyboard = []

    for tariff in TARIFFS.values():
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"🟢 {tariff.title} — {tariff.price} ₽",
                    callback_data=f"tariff:{tariff.code}"
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_tariff_selected_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="open_tariffs")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main")],
        ]
    )


def get_back_to_tariffs_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к тарифам", callback_data="open_tariffs")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main")],
        ]
    )


def get_admin_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Апрув",
                    callback_data=f"admin_approve:{request_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Реджект",
                    callback_data=f"admin_reject:{request_id}"
                ),
            ]
        ]
    )


def get_admin_processed_keyboard(status: str) -> InlineKeyboardMarkup:
    label = "✅ Одобрено" if status == "approved" else "❌ Отклонено"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data="admin_processed_noop"
                )
            ]
        ]
    )


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Управление доступом",
                    callback_data="admin_access_menu"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 В меню",
                    callback_data="back_to_main"
                )
            ],
        ]
    )


def get_admin_access_filters_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Активные",
                    callback_data="admin_users:1:1"
                ),
                InlineKeyboardButton(
                    text="❌ Отключённые",
                    callback_data="admin_users:0:1"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад в админку",
                    callback_data="admin_panel"
                )
            ],
        ]
    )


def get_admin_users_keyboard(
    users: list[dict],
    access_value: int,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    keyboard = []

    for user in users:
        label = user.get("username") or user.get("full_name") or str(user["telegram_id"])
        keyboard.append([
            InlineKeyboardButton(
                text=f"👤 {label} ({user['telegram_id']})",
                callback_data=f"admin_user_card:{user['telegram_id']}:{access_value}:{page}"
            )
        ])

    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"admin_users:{access_value}:{page - 1}"
            )
        )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"admin_users:{access_value}:{page + 1}"
            )
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton(
            text="⬅️ К фильтрам",
            callback_data="admin_access_menu"
        )
    ])
    keyboard.append([
        InlineKeyboardButton(
            text="🏠 В меню",
            callback_data="back_to_main"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_user_card_keyboard(
    telegram_id: int,
    current_access: int,
    return_access_value: int,
    return_page: int,
) -> InlineKeyboardMarkup:
    new_access = 0 if current_access == 1 else 1
    button_text = "🚫 Отключить доступ" if current_access == 1 else "♻️ Вернуть доступ"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"admin_toggle_access:{telegram_id}:{new_access}:{return_access_value}:{return_page}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ К списку",
                    callback_data=f"admin_users:{return_access_value}:{return_page}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 В меню",
                    callback_data="back_to_main"
                )
            ],
        ]
    )