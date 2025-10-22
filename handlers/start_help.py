# app/handlers/start_help.py
from __future__ import annotations

from typing import Optional

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app import config as cfg
from app.db.repo import (
    ensure_user, get_user, add_points, register_referral,
    inviter_by_code, set_user_fields,
)
from app.keyboards.common import main_menu, gender_self_kb, subscription_kb
from app.runtime import intro_text
from app.services.subscription_gate import gate_subscription, is_subscribed
from app.states import GState

router = Router(name="start_help")


@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    # Панель/меню админа не ломаем, но во время активного чата блоки разрулит chat.relay
    if not await gate_subscription(m):
        return

    await ensure_user(m.from_user.id)

    # deep-link /start r_<code> | ref_<id>
    try:
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) == 2:
            arg = parts[1]
            inviter_id: Optional[int] = None
            if arg.startswith("r_"):
                inviter_id = await inviter_by_code(arg[2:])
            elif arg.startswith("ref_"):
                inviter_id = int(arg[4:])
            if inviter_id and await register_referral(inviter_id, m.from_user.id):
                from app.runtime import g_ref_bonus  # локальный импорт, чтобы не тянуть всё
                await add_points(inviter_id, g_ref_bonus())
                try:
                    await m.bot.send_message(inviter_id, f"🎉 По твоей ссылке пришёл новый пользователь! +{g_ref_bonus()} очков.")
                except Exception:
                    pass
    except Exception:
        pass

    u = await get_user(m.from_user.id)
    if not u or not u[1] or not u[2]:
        await m.answer(intro_text(), disable_web_page_preview=True)
        await m.answer(
            "Сначала выберем твой пол и кого ищешь. Затем, при желании, можно заполнить анкету для деанонимизации.",
            reply_markup=gender_self_kb()
        )
        await state.update_data(start_form_after_prefs=True, is_refill=False)
        await state.set_state(GState.pick_gender)
        if not (m.from_user.username or ""):
            await m.answer("ℹ️ Для деанонимизации (анкеты) нужен @username в Telegram. Его можно создать позже.")
        return

    await m.answer("Главное меню.", reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(m: Message):
    from . import menu_for
    await m.answer(
        "ℹ️ Помощь\n\n"
        "Основное:\n"
        "• /profile — твой профиль, баланс, покупки\n"
        "• /market — магазин статусов и привилегий\n"
        "• /ref — реферальная ссылка и статистика\n"
        "• /help — эта справка\n\n"
        "Анонимный чат:\n"
        "• «🕵️ Анонимный чат» → «🔎 Найти собеседника»\n"
        "• !next — следующий собеседник\n"
        "• !stop — завершить чат\n"
        "• !reveal — запросить взаимное раскрытие (если анкеты у обоих)\n\n"
        "Навигация:\n"
        "• «❌ Отмена» — выйти из текущего режима к главному меню.",
        reply_markup=(await menu_for(m.from_user.id))
    )


@router.callback_query(F.data == "sub_check")
async def sub_check(c: CallbackQuery):
    await ensure_user(c.from_user.id)
    await set_user_fields(c.from_user.id, sub_verified=1)

    ok = False
    try:
        from app.services.subscription_gate import is_subscribed
        ok = await is_subscribed(c.message.bot, c.from_user.id)  # ⬅️ передаём bot
    except Exception:
        pass

    try:
        await c.message.edit_text("✅ Спасибо за подписку!" if ok else "✅ Готово.")
    except Exception:
        pass

    await c.answer("Подтверждено!")
    await c.message.bot.send_message(
        c.from_user.id, intro_text(), disable_web_page_preview=True, reply_markup=main_menu()
    )
