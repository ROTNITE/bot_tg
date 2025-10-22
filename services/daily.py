# app/services/daily.py
from __future__ import annotations

import time
from typing import Awaitable, Callable, Dict, Optional, Tuple

from aiogram.types import Message

from app.db.core import db
from app.db.repo import ensure_user, add_points, get_points, set_user_fields
from app.runtime import g_daily_bonus


# ====== Опциональный guard, чтобы не плодить циклические импорты ======
_DenyGuard = Callable[[Message], Awaitable[bool]]  # async def deny_actions_during_chat(m) -> bool

_CTX: Dict[str, object] = {"deny_guard": None}

def init_daily(deny_actions_during_chat: Optional[_DenyGuard] = None) -> None:
    """
    Передай, если хочешь автоматически блокировать команду во время активного чата.
    """
    _CTX["deny_guard"] = deny_actions_during_chat

def _deny_guard() -> Optional[_DenyGuard]:
    f = _CTX.get("deny_guard")
    return f if callable(f) else None  # type: ignore[return-value]


# ====== Константы ======
COOLDOWN_SECONDS: int = 24 * 60 * 60  # 24 часа


# ====== Вспомогательные ======
def _fmt_hhmmss(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


async def can_take_daily_cooldown(tg_id: int) -> Tuple[bool, int]:
    """
    Возвращает (can_take, remaining_seconds).
    can_take == True, если с последнего получения бонуса прошло >= 24 часов.
    """
    async with db() as conn:
        cur = await conn.execute("SELECT COALESCE(last_daily, 0) FROM users WHERE tg_id=?", (tg_id,))
        row = await cur.fetchone()
        last = int(row[0] if row else 0)

    if last == 0:
        return True, 0

    elapsed = int(time.time()) - last
    if elapsed >= COOLDOWN_SECONDS:
        return True, 0
    return False, COOLDOWN_SECONDS - elapsed


async def mark_daily_taken(tg_id: int) -> None:
    await set_user_fields(tg_id, last_daily=int(time.time()))


# ====== Обработчик команды /daily ======
async def daily_cmd(m: Message) -> None:
    """
    Хэндлер для /daily. Зарегистрируй его в своём Router:
        router.message.register(daily_cmd, Command("daily"))
    """
    guard = _deny_guard()
    if guard and await guard(m):
        return

    await ensure_user(m.from_user.id)

    can_take, remaining = await can_take_daily_cooldown(m.from_user.id)
    if not can_take:
        await m.answer(f"Сегодня бонус уже получен. Снова можно через {_fmt_hhmmss(remaining)}.")
        return

    await add_points(m.from_user.id, g_daily_bonus())
    await mark_daily_taken(m.from_user.id)
    pts = await get_points(m.from_user.id)
    await m.answer(f"🎁 Ежедневный бонус +{g_daily_bonus()} очков! Текущий баланс: {pts}.")


__all__ = [
    "init_daily",
    "daily_cmd",
    "COOLDOWN_SECONDS",
    "_fmt_hhmmss",
    "can_take_daily_cooldown",
    "mark_daily_taken",
]
