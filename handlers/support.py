# app/handlers/support.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app import config as cfg
from app.db.core import db
from app.keyboards.common import cancel_kb
from app.keyboards.admin import admin_reply_menu  # ⬅️
from app.states import SupportState

router = Router(name="support")
# ... остальной код без изменений ...


@router.message(F.text == "🆘 Поддержка")
async def support_entry(m: Message, state: FSMContext):
    from app.db.repo import get_role
    role = await get_role(m.from_user.id)
    if role == "admin" or m.from_user.id in cfg.ADMIN_IDS:
        await m.answer("Для админов есть «🧰 Поддержка» внутри /admin.", reply_markup=admin_reply_menu())
        return
    await state.clear()
    await state.set_state(SupportState.waiting)
    await m.answer(
        "Напиши сообщение с вопросом/проблемой — я перешлю админам.\n"
        "Чтобы выйти — нажми «❌ Отмена».",
        reply_markup=cancel_kb()
    )


@router.message(SupportState.waiting)
async def support_collect(m: Message, state: FSMContext):
    from app.runtime import SUPPORT_RELAY
    # сохраняем в БД
    async with db() as conn:
        cur = await conn.execute(
            "INSERT INTO support_msgs(from_user, text) VALUES(?,?)",
            (m.from_user.id, m.text or "")
        )
        _row_id = cur.lastrowid
        await conn.commit()

    # пересылаем админам
    for admin_id in (cfg.ADMIN_IDS or []):
        sent = await m.bot.send_message(
            admin_id,
            f"🆘 Запрос от {m.from_user.id} (@{m.from_user.username or '—'}):\n\n{m.text}"
        )
        SUPPORT_RELAY[sent.message_id] = m.from_user.id

    await m.answer("✉️ Сообщение отправлено админам. Ответ придёт сюда.")


@router.message(F.text == "/done")
async def support_done(m: Message):
    async with db() as conn:
        await conn.execute(
            "UPDATE support_msgs SET status='closed' WHERE from_user=? AND status='open'",
            (m.from_user.id,)
        )
        await conn.commit()
    await m.answer("✅ Обращение закрыто. Если что — пиши снова: «🆘 Поддержка».")
