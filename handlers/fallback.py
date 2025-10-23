# app/handlers/fallback.py
from __future__ import annotations
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.services.matching import active_peer, in_queue
from app.keyboards.common import cancel_kb

router = Router(name="fallback")

@router.message()
async def fallback_any(m: Message, state: FSMContext):
    # 1) Команды оставляем другим (если вдруг кто-то ещё их обработает)
    if m.text and m.text.startswith("/"):
        return

    # 2) Если пользователь в активном чате — пусть перехватит chat.relay
    if await active_peer(m.from_user.id):
        return

    # 3) В очереди — показываем «только Отмена»
    if await in_queue(m.from_user.id):
        await m.answer("Идёт поиск. Доступна только «❌ Отмена».", reply_markup=cancel_kb())
        return

    # 4) Если есть активное состояние FSM — не вмешиваемся
    if await state.get_state():
        return

    # 5) Универсальный возврат в меню (ленивый импорт, чтобы избежать циклов)
    from app.handlers import menu_for
    await m.answer("Неизвестное действие. Возвращаю в главное меню.", reply_markup=(await menu_for(m.from_user.id)))
