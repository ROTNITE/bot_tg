# app/handlers/admin/admins.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db.core import db
from app.keyboards.admin import admin_admins_kb
from app.services.admin import require_admin, list_admin_ids
from app.states import AdminAdmins

router = Router(name="admin_admins")


@router.callback_query(F.data == "admin:admins")
async def admin_admins(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    ids = await list_admin_ids()
    txt = "👥 Админы:\n" + ("\n".join([f"• <code>{i}</code>" for i in ids]) or "пока пусто")
    await c.message.edit_text(txt, reply_markup=admin_admins_kb())


@router.callback_query(F.data == "admin:admins:add")
async def admin_admins_add(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    await state.set_state(AdminAdmins.mode)
    await state.update_data(mode="add")
    await state.set_state(AdminAdmins.wait_user_id)
    await c.message.edit_text("Введи <code>tg_id</code> пользователя, которого сделать админом.")


@router.callback_query(F.data == "admin:admins:del")
async def admin_admins_del(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    await state.set_state(AdminAdmins.mode)
    await state.update_data(mode="del")
    await state.set_state(AdminAdmins.wait_user_id)
    await c.message.edit_text("Введи <code>tg_id</code> пользователя, которого лишить прав админа.")


@router.message(AdminAdmins.wait_user_id)
async def admin_admins_apply(m: Message, state: FSMContext):
    if not await require_admin(m):
        await state.clear()
        return

    d = await state.get_data()
    mode = d.get("mode")
    try:
        uid = int((m.text or "").strip())
    except Exception:
        return await m.answer("Нужен целый id пользователя.")

    if uid == m.from_user.id:
        return await m.answer("Нельзя менять свои права этим способом.")

    async with db() as conn:
        if mode == "add":
            await conn.execute("UPDATE users SET role='admin' WHERE tg_id=?", (uid,))
            await conn.commit()
            await m.answer(f"✅ Пользователь {uid} теперь админ.", reply_markup=admin_admins_kb())
        else:
            await conn.execute("UPDATE users SET role='user' WHERE tg_id=?", (uid,))
            await conn.commit()
            await m.answer(f"✅ Пользователь {uid} разжалован.", reply_markup=admin_admins_kb())

    await state.clear()
