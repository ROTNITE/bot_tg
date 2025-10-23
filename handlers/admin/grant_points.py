# app/handlers/admin/grant_points.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.keyboards.admin import admin_main_kb
from app.services.admin import require_admin, grant_points_and_notify
from app.states import AdminGrantPoints

router = Router(name="admin_grant")


@router.callback_query(F.data == "admin:grant")
async def admin_grant_start(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    await state.set_state(AdminGrantPoints.wait_user_id)
    await c.message.edit_text("💳 Кому начислить очки? Введи <code>tg_id</code> пользователя.")


@router.message(AdminGrantPoints.wait_user_id)
async def admin_grant_user(m: Message, state: FSMContext):
    if not await require_admin(m):
        await state.clear()
        return
    try:
        uid = int((m.text or "").strip())
    except Exception:
        return await m.answer("Нужен целый <code>tg_id</code>. Попробуй ещё.")
    await state.update_data(grant_uid=uid)
    await state.set_state(AdminGrantPoints.wait_amount)
    await m.answer(f"Сколько очков начислить пользователю <code>{uid}</code>? "
                   "Можно отрицательное число, чтобы списать.")


@router.message(AdminGrantPoints.wait_amount)
async def admin_grant_amount(m: Message, state: FSMContext):
    if not await require_admin(m):
        await state.clear()
        return
    try:
        amount = int((m.text or "").strip())
    except Exception:
        return await m.answer("Нужно целое число (например: 50 или -20). Попробуй ещё.")
    data = await state.get_data()
    uid = int(data.get("grant_uid"))
    new_pts = await grant_points_and_notify(m.bot, uid, amount)
    await state.clear()
    await m.answer(
        f"✅ Пользователь <code>{uid}</code>: изменение {amount} очков. Текущий баланс: {new_pts}.",
        reply_markup=admin_main_kb()
    )


@router.message(AdminGrantPoints.wait_user_id, F.text.in_({"❌ Отмена", "🛠 Админ", "/admin"}))
@router.message(AdminGrantPoints.wait_amount,  F.text.in_({"❌ Отмена", "🛠 Админ", "/admin"}))
async def admin_grant_cancel(m: Message, state: FSMContext):
    if not await require_admin(m):
        await state.clear()
        return
    await state.clear()
    await m.answer("Отменено. Возврат в панель администратора.", reply_markup=admin_main_kb())


@router.message(Command("grant"))
async def admin_grant_cmd(m: Message):
    if not await require_admin(m):
        return
    # Формат: /grant <tg_id> <amount> [reason...]
    parts = (m.text or "").strip().split(maxsplit=3)
    if len(parts) < 3:
        return await m.answer("Формат: <code>/grant &lt;tg_id&gt; &lt;amount&gt; [reason]</code>\n"
                              "Например: <code>/grant 123456789 50 За активность</code>")
    try:
        _, uid_s, amt_s, *maybe_reason = parts
        uid = int(uid_s)
        amount = int(amt_s)
        reason = maybe_reason[0] if maybe_reason else ""
    except Exception:
        return await m.answer("Проверь формат. Пример: <code>/grant 123456789 50 За активность</code>")

    new_pts = await grant_points_and_notify(m.bot, uid, amount, reason)
    await m.answer(
        f"✅ Пользователю <code>{uid}</code> {'начислено' if amount>=0 else 'списано'} {abs(amount)} очков."
        f"\nТекущий баланс: {new_pts}."
    )
