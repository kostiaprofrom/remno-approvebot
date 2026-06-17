from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import (
    TARIFFS,
    TRIAL_BUTTON_ENABLED,
    SUPPORT_BUTTON_ENABLED,
    SUPPORT_LINK,
    BTN_TRIAL,
    BTN_RENEW,
    BTN_REFERRAL,
    BTN_SUPPORT,
    BTN_REFRESH,
    BTN_ADMIN,
    BTN_BACK,
    BTN_TO_MAIN,
    BTN_BACK_TARIFFS,
    BTN_APPROVE,
    BTN_REJECT,
    BTN_APPROVED,
    BTN_REJECTED,
    BTN_ACCESS_MANAGE,
    BTN_ACTIVE,
    BTN_INACTIVE,
    BTN_BACK_ADMIN,
    BTN_DISABLE,
    BTN_ENABLE,
    BTN_TO_LIST,
    BTN_TO_FILTERS,
    BTN_PREV,
    BTN_NEXT,
)


def get_main_menu_keyboard(
    is_admin: bool = False,
    show_trial_button: bool = False,
    show_referral_button: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if TRIAL_BUTTON_ENABLED and show_trial_button:
        builder.row(InlineKeyboardButton(text=BTN_TRIAL, callback_data="activate_trial"))

    builder.row(InlineKeyboardButton(text=BTN_RENEW, callback_data="open_tariffs"))

    if show_referral_button:
        builder.row(InlineKeyboardButton(text=BTN_REFERRAL, callback_data="referral_menu"))

    if SUPPORT_BUTTON_ENABLED and SUPPORT_LINK:
        builder.row(InlineKeyboardButton(text=BTN_SUPPORT, url=SUPPORT_LINK))

    builder.row(InlineKeyboardButton(text=BTN_REFRESH, callback_data="refresh_main"))

    if is_admin:
        builder.row(InlineKeyboardButton(text=BTN_ADMIN, callback_data="admin_panel"))

    builder.adjust(1)
    return builder.as_markup()


def get_tariffs_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for tariff in TARIFFS.values():
        # Жёсткий шаблон без переменной
        text = f"🟢 {tariff.title} — {tariff.price} ₽"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"tariff:{tariff.code}"
            )
        )

    builder.row(InlineKeyboardButton(text=BTN_BACK, callback_data="back_to_main"))
    builder.adjust(1)
    return builder.as_markup()


def get_tariff_selected_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=BTN_BACK, callback_data="open_tariffs"),
        InlineKeyboardButton(text=BTN_TO_MAIN, callback_data="back_to_main"),
    )
    builder.adjust(1)
    return builder.as_markup()


def get_back_to_tariffs_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=BTN_BACK_TARIFFS, callback_data="open_tariffs"),
        InlineKeyboardButton(text=BTN_TO_MAIN, callback_data="back_to_main"),
    )
    builder.adjust(1)
    return builder.as_markup()


def get_admin_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=BTN_APPROVE, callback_data=f"admin_approve:{request_id}"),
        InlineKeyboardButton(text=BTN_REJECT, callback_data=f"admin_reject:{request_id}"),
    )
    return builder.as_markup()


def get_admin_processed_keyboard(status: str) -> InlineKeyboardMarkup:
    label = BTN_APPROVED if status == "approved" else BTN_REJECTED
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=label, callback_data="admin_processed_noop"))
    return builder.as_markup()


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=BTN_ACCESS_MANAGE, callback_data="admin_access_menu"),
        InlineKeyboardButton(text=BTN_TO_MAIN, callback_data="back_to_main"),
    )
    builder.adjust(1)
    return builder.as_markup()


def get_admin_access_filters_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=BTN_ACTIVE, callback_data="admin_users:1:1"),
        InlineKeyboardButton(text=BTN_INACTIVE, callback_data="admin_users:0:1"),
    )
    builder.row(InlineKeyboardButton(text=BTN_BACK_ADMIN, callback_data="admin_panel"))
    return builder.as_markup()


def get_admin_users_keyboard(
    users: list[dict],
    access_value: int,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for user in users:
        label = user.get("username") or user.get("full_name") or str(user["telegram_id"])
        # Жёсткий шаблон без переменной
        text = f"👤 {label} ({user['telegram_id']})"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"admin_user_card:{user['telegram_id']}:{access_value}:{page}",
            )
        )

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text=BTN_PREV, callback_data=f"admin_users:{access_value}:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text=BTN_NEXT, callback_data=f"admin_users:{access_value}:{page + 1}"))

    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text=BTN_TO_FILTERS, callback_data="admin_access_menu"))
    builder.row(InlineKeyboardButton(text=BTN_TO_MAIN, callback_data="back_to_main"))

    return builder.as_markup()


def get_admin_user_card_keyboard(
    telegram_id: int,
    current_access: int,
    return_access_value: int,
    return_page: int,
) -> InlineKeyboardMarkup:
    new_access = 0 if current_access == 1 else 1
    button_text = BTN_DISABLE if current_access == 1 else BTN_ENABLE

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=button_text,
            callback_data=f"admin_toggle_access:{telegram_id}:{new_access}:{return_access_value}:{return_page}",
        ),
        InlineKeyboardButton(
            text=BTN_TO_LIST,
            callback_data=f"admin_users:{return_access_value}:{return_page}",
        ),
        InlineKeyboardButton(text=BTN_TO_MAIN, callback_data="back_to_main"),
    )
    builder.adjust(1)
    return builder.as_markup()