# app/handlers/modes_menu.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app import config as cfg
from app.db.repo import get_role
from app.keyboards.common import modes_kb, anon_chat_menu_kb
from app.keyboards.admin import admin_reply_menu  # ⬅️
from app.services.subscription_gate import gate_subscription

router = Router(name="modes_menu")
# ... остальной код без изменений ...

@router.message(F.text.in_({"🧭 Режимы", "Режимы"}))
async def modes_entry(m: Message, state: FSMContext):
    if (await get_role(m.from_user.id) == "admin") or m.from_user.id in cfg.ADMIN_IDS:
        await m.answer("Этот раздел недоступен админу. Открой панель: /admin", reply_markup=admin_reply_menu())
        return
    if not await gate_subscription(m):
        return
    await state.clear()
    await m.answer(
        "Выбери режим работы бота:\n\n"
        "<b>📇 Просмотр анкет</b> — лента анкет (в разработке)\n\n"
        "<b>🕵️ Анонимный чат</b> — случайные собеседники с возможностью взаимного раскрытия",
        reply_markup=modes_kb()
    )


@router.message(F.text.in_({"📇 Просмотр анкет", "Просмотр анкет"}))
async def mode_cards(m: Message):
    await m.answer("Раздел «Просмотр анкет» — <b>в разработке</b>.", reply_markup=modes_kb())


@router.message(F.text.in_({"🕵️ Анонимный чат", "Анонимный чат"}))
async def mode_anon_chat(m: Message):
    if (await get_role(m.from_user.id) == "admin") or m.from_user.id in cfg.ADMIN_IDS:
        await m.answer("Этот раздел недоступен админу. Открой панель: /admin", reply_markup=admin_reply_menu())
        return
    if not await gate_subscription(m):
        return
    await m.answer(
        "Режим «Анонимный чат». Здесь можно искать случайного собеседника.\n"
        "Используй кнопки ниже.",
        reply_markup=anon_chat_menu_kb()
    )


@router.message(F.text.in_({"⬅️ В главное меню", "В главное меню"}))
async def back_to_main_menu(m: Message, state: FSMContext):
    from . import menu_for
    await state.clear()
    await m.answer("Главное меню.", reply_markup=(await menu_for(m.from_user.id)))


# Фолбэк-навигация вне чатов/очередей/форм — безопасно возвращает меню
@router.message()
async def unknown_router(m: Message, state: FSMContext):
    # 1) Команды — не трогаем
    if m.text and m.text.startswith("/"):
        return
    # 2) Если пользователь в чате/очереди/форме — отдать другим обработчикам
    from app.services.matching import active_peer, in_queue
    if await active_peer(m.from_user.id):
        return
    if await in_queue(m.from_user.id):
        from app.keyboards.common import cancel_kb
        await m.answer("Идёт поиск. Доступна только «❌ Отмена».", reply_markup=cancel_kb())
        return
    if await state.get_state():
        return

    from . import menu_for
    await m.answer("Неизвестное действие. Возвращаю в главное меню.", reply_markup=(await menu_for(m.from_user.id)))
