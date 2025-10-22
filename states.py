# app/states.py
from __future__ import annotations

from aiogram.fsm.state import StatesGroup, State


class ComplaintState(StatesGroup):
    """Жалобы: ждём текст жалобы; в state кладём mid и about_id."""
    wait_text = State()


class GState(StatesGroup):
    """Первичные предпочтения: свой пол и кого ищем."""
    pick_gender = State()
    pick_seeking = State()


class RevealForm(StatesGroup):
    """Анкета для взаимного раскрытия (!reveal)."""
    name = State()
    faculty = State()
    age = State()
    about = State()
    photos = State()


class AdminGrantPoints(StatesGroup):
    """Админ: выдача/списание очков."""
    wait_user_id = State()
    wait_amount = State()


class SupportState(StatesGroup):
    """Пользовательская поддержка."""
    waiting = State()


class AdminAddItem(StatesGroup):
    """Админ: добавление товара в магазин."""
    wait_name = State()
    wait_price = State()
    wait_type = State()
    wait_payload = State()


class AdminShopDel(StatesGroup):
    """Админ: удаление товара из магазина."""
    wait_id = State()


class AdminSettings(StatesGroup):
    """Админ: ввод значения для выбранной настройки."""
    wait_value = State()


class AdminAdmins(StatesGroup):
    """Админ: управление списком администраторов."""
    mode = State()          # 'add' или 'del'
    wait_user_id = State()


class AdminBroadcast(StatesGroup):
    """Админ: массовая рассылка по пользователям."""
    wait_text = State()


class AdminSupportReply(StatesGroup):
    """Админ: ответ пользователю в тикете поддержки."""
    wait_text = State()


__all__ = [
    "ComplaintState",
    "GState",
    "RevealForm",
    "AdminGrantPoints",
    "SupportState",
    "AdminAddItem",
    "AdminShopDel",
    "AdminSettings",
    "AdminAdmins",
    "AdminBroadcast",
    "AdminSupportReply",
]
