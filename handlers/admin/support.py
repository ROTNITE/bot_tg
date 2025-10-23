# app/handlers/admin/support.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.admin import admin_main_kb
from app.services.admin import (
    require_admin, list_open_support_threads, close_support_thread
)
from app.states import AdminSupportReply

router = Router(name="admin_support")


@router.callback_query(F.data == "admin:support")
async def admin_support_menu(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return

    await c.message.edit_text("Диалоги саппорта (открытые):")
    users = await list_open_support_threads(limit=10)
    if not users:
        return await c.message.answer("Пусто. Новых обращений нет.", reply_markup=admin_main_kb())

    for (uid, _ts) in users:
        kb = InlineKeyboardBuilder()
        kb.button(text="✍️ Ответить", callback_data=f"admin:support:reply:{uid}")
        kb.button(text="✅ Закрыть", callback_data=f"sup_close:{uid}")
        kb.adjust(2)
        await c.message.bot.send_message(
            c.from_user.id, f"<b>#{uid}</b> — открыть диалог и ответить:", reply_markup=kb.as_markup()
        )


@router.callback_query(F.data.startswith("admin:support:reply:"))
async def admin_support_reply_start(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    uid = int(c.data.split(":")[-1])
    await state.set_state(AdminSupportReply.wait_text)
    await state.update_data(uid=uid)
    await c.answer()
    await c.message.bot.send_message(c.from_user.id, f"Напиши ответ для пользователя <code>{uid}</code> (одним сообщением).")


@router.message(AdminSupportReply.wait_text)
async def admin_support_reply_send(m: Message, state: FSMContext):
    if not await require_admin(m):
        await state.clear()
        return
    d = await state.get_data()
    uid = int(d.get("uid"))
    await m.bot.send_message(uid, f"🛠 Ответ админа:\n{m.text}")
    await m.answer("✅ Ответ отправлен.", reply_markup=admin_main_kb())
    await state.clear()


@router.callback_query(F.data.startswith("sup_close:"))
async def sup_close(c: CallbackQuery):
    if not await require_admin(c):
        return
    uid = int(c.data.split(":")[1])
    await close_support_thread(uid)
    await c.answer("Закрыто.")
    try:
        await c.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        await c.message.bot.send_message(
            uid,
            "🔧 Админ закрыл обращение. Если проблема осталась — открой новый запрос через «🆘 Поддержка»."
        )
    except Exception:
        pass
    await c.message.bot.send_message(c.from_user.id, "Тикет закрыт.")
