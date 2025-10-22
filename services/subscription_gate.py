# app/services/subscription_gate.py
from __future__ import annotations

from typing import Optional

from aiogram import Bot
from aiogram.types import Message

from app.config import CHANNEL_USERNAME
from app.db.core import db
from app.keyboards.common import subscription_kb

# Кэш для числового ID канала (ускоряет и устойчив к смене @username)
_RESOLVED_CHANNEL_ID: Optional[int] = None


async def _resolve_channel_id(bot: Bot) -> Optional[int]:
    global _RESOLVED_CHANNEL_ID
    if _RESOLVED_CHANNEL_ID is not None:
        return _RESOLVED_CHANNEL_ID
    try:
        chat = await bot.get_chat(CHANNEL_USERNAME)
        _RESOLVED_CHANNEL_ID = chat.id
    except Exception:
        _RESOLVED_CHANNEL_ID = None
    return _RESOLVED_CHANNEL_ID


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """
    Реально проверяет, состоит ли пользователь в канале.
    Пытается использовать числовой ID (если удалось зарезолвить),
    иначе — проверяет по CHANNEL_USERNAME.
    """
    target = await _resolve_channel_id(bot) or CHANNEL_USERNAME
    try:
        cm = await bot.get_chat_member(target, user_id)
        status = str(getattr(cm, "status", "")).lower()
        if status in ("member", "administrator", "creator"):
            return True
        # Для старых версий ChatMember
        if hasattr(cm, "is_member") and bool(getattr(cm, "is_member")):
            return True
        return False
    except Exception:
        # если бот не админ канала или канал недоступен — считаем «не подписан»
        return False


async def gate_subscription(message: Message) -> bool:
    """
    «Одноразовые ворота». Пропускаем пользователя дальше, если в БД
    стоит флаг users.sub_verified=1. Иначе показываем клаву подписки.
    """
    uid = message.from_user.id
    async with db() as conn:
        cur = await conn.execute(
            "SELECT COALESCE(sub_verified,0) FROM users WHERE tg_id=?",
            (uid,),
        )
        row = await cur.fetchone()

    if bool(row and row[0]):
        return True

    await message.answer(
        "🔔 Перед использованием бота подпишись на канал и нажми «✅ Проверить подписку».",
        reply_markup=subscription_kb(),
    )
    return False


__all__ = ["is_subscribed", "gate_subscription"]
