# app/handlers/admin/settings.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.common import admin_settings_kb
from app.runtime import safe_edit_message, g_support_enabled
from app.services.admin import require_admin, set_numeric_setting

from app.runtime import set_setting  # для support_toggle
from app.states import AdminSettings

router = Router(name="admin_settings")


@router.callback_query(F.data == "admin:settings")
async def admin_settings(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    await safe_edit_message(c.message, text="⚙️ Настройки", reply_markup=admin_settings_kb())


@router.callback_query(F.data.startswith("admin:set:"))
async def admin_settings_select(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return

    key = c.data.split(":", 2)[2]
    if key == "support_toggle":
        await set_setting("support_enabled", "0" if g_support_enabled() else "1")
        await safe_edit_message(c.message, text="⚙️ Настройки обновлены.", reply_markup=admin_settings_kb())
        return

    await state.set_state(AdminSettings.wait_value)
    await state.update_data(key=key)
    nice = {
        "inactivity_seconds": "⏱️ Неактивность (сек)",
        "block_rounds": "🔁 Блок-раундов",
        "daily_bonus_points": "🎁 Daily бонус",
        "ref_bonus_points": "🎯 Referral бонус",
    }.get(key, key)
    await c.message.edit_text(f"Введи новое значение для: <b>{nice}</b>\n(целое число)")


@router.message(AdminSettings.wait_value)
async def admin_settings_set(m: Message, state: FSMContext):
    if not await require_admin(m):
        await state.clear()
        return
    d = await state.get_data()
    key = d.get("key")
    try:
        val = int((m.text or "").strip())
        if val < 0:
            raise ValueError
    except Exception:
        return await m.answer("Нужно целое неотрицательное число. Попробуй ещё.")
    await set_numeric_setting(key, val)
    await state.clear()
    await m.answer("✅ Сохранено.", reply_markup=admin_settings_kb())
