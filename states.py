from aiogram.fsm.state import State, StatesGroup


class AccessStates(StatesGroup):
    waiting_for_access_code = State()


class PaymentStates(StatesGroup):
    waiting_for_screenshot = State()