# app/keyboards/common.py (обновлённый — без админских клавиатур)
from __future__ import annotations

from typing import Optional, Iterable, Sequence

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.config import CHANNEL_LINK, FACULTIES

# ============ Пользовательские клавиатуры ============

def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="🧭 Режимы"))
    kb.add(KeyboardButton(text="👤 Анкета"))
    kb.add(KeyboardButton(text="🆘 Поддержка"))
    return kb.as_markup(resize_keyboard=True)

def modes_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="📇 Просмотр анкет"))
    kb.add(KeyboardButton(text="🕵️ Анонимный чат"))
    kb.add(KeyboardButton(text="⬅️ В главное меню"))
    return kb.as_markup(resize_keyboard=True)

def subscription_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➡️ Подписаться", url=CHANNEL_LINK)
    b.button(text="✅ Проверить подписку", callback_data="sub_check")
    b.adjust(1)
    return b.as_markup()

def anon_chat_menu_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="🔎 Найти собеседника"))
    kb.add(KeyboardButton(text="⬅️ В главное меню"))
    return kb.as_markup(resize_keyboard=True)

def cancel_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="❌ Отмена"))
    return kb.as_markup(resize_keyboard=True)

def rate_or_complain_kb(mid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text=str(i), callback_data=f"rate:{mid}:{i}")
    b.button(text="🚩 Пожаловаться", callback_data=f"complain:{mid}")
    b.adjust(5, 1)
    return b.as_markup()

def post_chat_rate_kb(mid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text=str(i), callback_data=f"rate:{mid}:{i}")
    b.button(text="🚩 Пожаловаться", callback_data=f"complain:{mid}")
    b.button(text="➡️ Пропустить", callback_data=f"postfb:skip:{mid}")
    b.adjust(5, 1, 1)
    return b.as_markup()

def shop_kb(items: Iterable[Sequence]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    any_items = False
    for (id_, name, price, type_, payload) in items:
        any_items = True
        b.button(text=f"{name} — {price}💰", callback_data=f"shop_buy:{id_}")
    if not any_items:
        b.button(text="Пока пусто 😅", callback_data="noop")
    b.adjust(1)
    return b.as_markup()

def gender_self_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="Я девушка"))
    kb.add(KeyboardButton(text="Я парень"))
    return kb.as_markup(resize_keyboard=True)

def seeking_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="Девушки"))
    kb.add(KeyboardButton(text="Парни"))
    kb.add(KeyboardButton(text="Не важно"))
    return kb.as_markup(resize_keyboard=True)

def faculties_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, f in enumerate(FACULTIES):
        b.button(text=f, callback_data=f"fac:{i}")
    b.adjust(2)
    return b.as_markup()

def reveal_entry_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="⬅️ В главное меню"))
    kb.add(KeyboardButton(text="✏️ Заполнить / Перезаполнить"))
    return kb.as_markup(resize_keyboard=True)

def about_kb(*, refill: bool = False, has_prev: bool = False) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="Пропустить"))
    if refill and has_prev:
        kb.add(KeyboardButton(text="Оставить текущее"))
    kb.add(KeyboardButton(text="❌ Отмена"))
    return kb.as_markup(resize_keyboard=True)

def post_chat_actions_kb(mid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⭐️ Оценить", callback_data=f"postfb:rate:{mid}")
    b.button(text="🚩 Пожаловаться", callback_data=f"postfb:complain:{mid}")
    b.button(text="➡️ Пропустить", callback_data=f"postfb:skip:{mid}")
    b.adjust(2, 1)
    return b.as_markup()

def rate_stars_kb(mid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text=str(i), callback_data=f"rate:{mid}:{i}")
    b.button(text="↩️ Назад", callback_data=f"postfb:back:{mid}")
    b.adjust(5, 1)
    return b.as_markup()

def photos_empty_kb(*, refill: bool = False, has_prev: bool = False) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    if refill and has_prev:
        kb.add(KeyboardButton(text="Оставить текущее"))
    kb.add(KeyboardButton(text="❌ Отмена"))
    return kb.as_markup(resize_keyboard=True)

def photos_progress_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="Готово"))
    kb.add(KeyboardButton(text="Сбросить фото"))
    kb.add(KeyboardButton(text="❌ Отмена"))
    return kb.as_markup(resize_keyboard=True)

def statuses_kb(inventory: list[str], current: Optional[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in inventory:
        mark = " ✅" if current and t == current else ""
        b.button(text=f"{t}{mark}", callback_data=f"use_status:{t}")
    if current:
        b.button(text="Снять статус", callback_data="use_status:__none__")
    b.adjust(1)
    return b.as_markup()

def chat_hint() -> str:
    return (
        "Команды в чате:\n"
        "<code>!next</code> — следующий собеседник\n"
        "<code>!stop</code> — закончить\n"
        "<code>!reveal</code> — взаимное раскрытие (если анкеты есть у обоих)\n"
    )

__all__ = [
    "main_menu", "modes_kb", "subscription_kb", "anon_chat_menu_kb", "cancel_kb",
    "rate_or_complain_kb", "post_chat_rate_kb", "shop_kb",
    "gender_self_kb", "seeking_kb", "faculties_kb",
    "reveal_entry_menu", "about_kb",
    "post_chat_actions_kb", "rate_stars_kb",
    "photos_empty_kb", "photos_progress_kb",
    "statuses_kb", "chat_hint",
]
