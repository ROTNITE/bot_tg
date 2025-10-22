# app/handlers/referrals.py
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db.repo import count_referrals, ensure_user, get_role
from app.runtime import g_ref_bonus, g_daily_bonus
from app.handlers import menu_for

router = Router(name="referrals")


@router.message(Command("ref"))
async def cmd_ref(m: Message):
    if await get_role(m.from_user.id) == "admin":
        await m.answer("Админам рефералка не нужна. Используй /admin для панели.", reply_markup=(await menu_for(m.from_user.id)))
        return

    await ensure_user(m.from_user.id)
    me = await m.bot.get_me()
    bot_user = me.username or ""
    # ссылка формата r_<opaque>, см. services/refcodes (вынесено в db.repo в get_or_create_ref_code)
    from app.db.repo import get_or_create_ref_code
    code = await get_or_create_ref_code(m.from_user.id)
    link = f"https://t.me/{bot_user}?start=r_{code}" if bot_user else "—"
    cnt = await count_referrals(m.from_user.id)
    bonus = cnt * g_ref_bonus()
    await m.answer(
        "👥 Реферальная программа\n\n"
        f"Твоя ссылка: {link}\n"
        f"Приведено пользователей: <b>{cnt}</b>\n"
        f"Начислено бонусов: <b>{bonus}</b> очков\n\n"
        f"Начисление: +{g_ref_bonus()} очков за каждого нового пользователя.",
        disable_web_page_preview=True
    )
