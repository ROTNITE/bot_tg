# app/services/admin.py
from __future__ import annotations

import asyncio
from typing import Iterable, Optional

from aiogram import Bot
from aiogram.types import Message, CallbackQuery

from app import config as cfg
from app.db.core import db
from app.db.repo import get_role, add_points, get_points, ensure_user
from app.runtime import (
    safe_edit_message, g_inactivity, g_block_rounds, g_daily_bonus, g_ref_bonus,
    g_support_enabled, _nowm, DEADLINE
)


# ====== Проверка прав администратора ======

async def is_admin(user_id: int) -> bool:
    if user_id in cfg.ADMIN_IDS:
        return True
    return (await get_role(user_id)) == "admin"


async def require_admin(event: Message | CallbackQuery) -> bool:
    """
    Возвращает True, если у пользователя есть права админа.
    Иначе показывает «Нет доступа» и возвращает False.
    """
    uid = event.from_user.id
    ok = await is_admin(uid)
    if ok:
        return True
    if isinstance(event, CallbackQuery):
        try:
            await event.answer("Нет доступа.", show_alert=True)
        except Exception:
            pass
    else:
        try:
            await event.answer("Нет доступа.")
        except Exception:
            pass
    return False


# ====== Выдача/списание очков ======

async def grant_points_and_notify(bot: Bot, to_user_id: int, amount: int, reason: str = "") -> int:
    """
    Начисляет/списывает очки и уведомляет получателя.
    Возвращает новый баланс.
    """
    await ensure_user(to_user_id)
    await add_points(to_user_id, amount)
    new_pts = await get_points(to_user_id)
    note = f"\nПричина: {reason}" if reason else ""
    try:
        await bot.send_message(
            to_user_id,
            f"💳 Тебе {'начислено' if amount >= 0 else 'списано'} {abs(amount)} очков.{note}\nБаланс: {new_pts}."
        )
    except Exception:
        pass
    return new_pts


# ====== Настройки (runtime cache) ======

async def set_numeric_setting(key: str, value: int) -> None:
    """
    Сохраняет числовую настройку в БД/кеш и мягко «продлевает» дедлайны чатов,
    если меняем таймаут неактивности.
    """
    from app.runtime import set_setting  # локальный импорт, чтобы избежать циклов
    await set_setting(key, str(value))
    if key == "inactivity_seconds":
        now = _nowm()
        for mid in list(DEADLINE.keys()):
            DEADLINE[mid] = now + g_inactivity()


# ====== Статистика ======

async def fetch_stats() -> dict[str, int]:
    """
    Собирает агрегаты для панели статистики.
    """
    async with db() as conn:
        ucnt = (await (await conn.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        qcnt = (await (await conn.execute("SELECT COUNT(*) FROM queue")).fetchone())[0]
        mact = (await (await conn.execute("SELECT COUNT(*) FROM matches WHERE active=1")).fetchone())[0]
        mtotal = (await (await conn.execute("SELECT COUNT(*) FROM matches")).fetchone())[0]
        sup_open = (await (await conn.execute("SELECT COUNT(*) FROM support_msgs WHERE status='open'")).fetchone())[0]
        ref_cnt = (await (await conn.execute("SELECT COUNT(*) FROM referrals")).fetchone())[0]
    return dict(
        users=ucnt, in_queue=qcnt, matches_active=mact, matches_total=mtotal,
        support_open=sup_open, referrals=ref_cnt
    )


def render_stats_text(agg: dict[str, int]) -> str:
    return (
        "<b>📊 Статистика</b>\n\n"
        f"👤 Пользователей: <b>{agg['users']}</b>\n"
        f"🧍‍♀️🧍‍♂️ В очереди: <b>{agg['in_queue']}</b>\n"
        f"💬 Активных чатов: <b>{agg['matches_active']}</b>\n"
        f"💬 Всего чатов: <b>{agg['matches_total']}</b>\n"
        f"🆘 Открытых тикетов: <b>{agg['support_open']}</b>\n"
        f"🎯 Рефералов всего: <b>{agg['referrals']}</b>\n"
        f"\n⚙️ Неактивность: {g_inactivity()} c | Блок-раундов: {g_block_rounds()}\n"
        f"🎁 Daily: {g_daily_bonus()} | 🎯 Referral: {g_ref_bonus()}\n"
        f"🆘 Support: {'ON' if g_support_enabled() else 'OFF'}"
    )


# ====== Поддержка ======

async def list_open_support_threads(limit: int = 10) -> list[tuple[int, int]]:
    """
    Возвращает [(from_user, last_ts), ...] по открытым тредам саппорта.
    """
    async with db() as conn:
        cur = await conn.execute("""
            SELECT from_user, MAX(ts) AS last_ts
            FROM support_msgs
            WHERE status='open'
            GROUP BY from_user
            ORDER BY last_ts DESC
            LIMIT ?
        """, (limit,))
        return [(int(u), int(ts)) for (u, ts) in await cur.fetchall()]


async def append_support_message(from_user: int, text: str) -> None:
    async with db() as conn:
        await conn.execute(
            "INSERT INTO support_msgs(from_user, text) VALUES(?,?)",
            (from_user, text)
        )
        await conn.commit()


async def close_support_thread(user_id: int) -> None:
    async with db() as conn:
        await conn.execute(
            "UPDATE support_msgs SET status='closed' WHERE from_user=?",
            (user_id,)
        )
        await conn.commit()


# ====== Рассылка ======

async def broadcast_all(bot: Bot, text: str, throttle: float = 0.05) -> tuple[int, int]:
    """
    Шлёт текст всем пользователям. Возвращает (успешно, всего).
    """
    async with db() as conn:
        cur = await conn.execute("SELECT tg_id FROM users")
        uids = [int(x[0]) for x in await cur.fetchall()]

    ok = 0
    for uid in uids:
        try:
            await bot.send_message(uid, text)
            ok += 1
        except Exception:
            pass
        await asyncio.sleep(throttle)

    return ok, len(uids)


# ====== Админы-учёт ======

async def list_admin_ids() -> list[int]:
    async with db() as conn:
        cur = await conn.execute("SELECT tg_id FROM users WHERE role='admin' ORDER BY tg_id ASC")
        return [int(x[0]) for x in await cur.fetchall()]
