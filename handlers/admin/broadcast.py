# app/handlers/admin/broadcast.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.admin import admin_main_kb
from app.services.admin import require_admin, broadcast_all
from app.states import AdminBroadcast

router = Router(name="admin_broadcast")


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    await state.set_state(AdminBroadcast.wait_text)
    await c.message.edit_text("Введи текст рассылки (уйдёт всем пользователям).")


@router.message(AdminBroadcast.wait_text)
async def admin_broadcast_run(m: Message, state: FSMContext):
    if not await require_admin(m):
        await state.clear()
        return
    text = m.text or ""
    await state.clear()
    ok, total = await broadcast_all(m.bot, text)
    await m.answer(f"📣 Разослано: {ok}/{total}", reply_markup=admin_main_kb())
