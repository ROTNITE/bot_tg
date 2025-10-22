# app/keyboards/admin.py
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.runtime import (
    g_inactivity, g_block_rounds, g_daily_bonus, g_ref_bonus, g_support_enabled,
)

def admin_main_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛍 Магазин", callback_data="admin:shop")
    b.button(text="⚙️ Настройки", callback_data="admin:settings")
    b.button(text="👥 Админы", callback_data="admin:admins")
    b.button(text="🧰 Поддержка", callback_data="admin:support")
    b.button(text="📣 Рассылка", callback_data="admin:broadcast")
    b.button(text="📊 Статистика", callback_data="admin:stats")
    b.button(text="💳 Выдать очки", callback_data="admin:grant")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()

def admin_shop_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить товар", callback_data="admin:shop:add")
    b.button(text="📦 Список", callback_data="admin:shop:list")
    b.button(text="🗑 Удалить", callback_data="admin:shop:del")
    b.button(text="↩️ Назад", callback_data="admin:home")
    b.adjust(1)
    return b.as_markup()

def admin_settings_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"⏱️ Неактивность: {g_inactivity()} c", callback_data="admin:set:inactivity_seconds")
    b.button(text=f"🔁 Блок-раундов: {g_block_rounds()}", callback_data="admin:set:block_rounds")
    b.button(text=f"🎁 Daily: {g_daily_bonus()}", callback_data="admin:set:daily_bonus_points")
    b.button(text=f"🎯 Referral: {g_ref_bonus()}", callback_data="admin:set:ref_bonus_points")
    b.button(text=f"🆘 Support: {'ON' if g_support_enabled() else 'OFF'}", callback_data="admin:set:support_toggle")
    b.button(text="↩️ Назад", callback_data="admin:home")
    b.adjust(1)
    return b.as_markup()

def admin_admins_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить админа", callback_data="admin:admins:add")
    b.button(text="➖ Удалить админа", callback_data="admin:admins:del")
    b.button(text="↩️ Назад", callback_data="admin:home")
    b.adjust(1)
    return b.as_markup()

def admin_reply_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="🛠 Админ"))
    return kb.as_markup(resize_keyboard=True)


__all__ = [
    "admin_main_kb",
    "admin_shop_kb",
    "admin_settings_kb",
    "admin_admins_kb",
    "admin_reply_menu",
]
