# app/services/feedback.py
from __future__ import annotations

from typing import Dict, Optional

from aiogram import Bot

# Берём готовые билдеры из общего модуля клавиатур
from app.keyboards.common import (
    rate_or_complain_kb,
    post_chat_rate_kb,
    post_chat_actions_kb,
    rate_stars_kb,
)

# ====== Контекст: аккуратно пробрасываем Bot ======
_CTX: Dict[str, Optional[Bot]] = {"bot": None}

def init_feedback(bot: Bot) -> None:
    """
    Вызови один раз при старте, чтобы модуль мог отправлять сообщения:
        from app.services import feedback
        feedback.init_feedback(bot)
    """
    _CTX["bot"] = bot

def _bot() -> Bot:
    b = _CTX.get("bot")
    if b is not None:
        return b
    # Попытка достать текущий Bot из контекста aiogram (v3)
    try:  # type: ignore[attr-defined]
        return Bot.get_current()  # pyright: ignore[reportAttributeAccessIssue]
    except Exception as e:
        raise RuntimeError("feedback.init_feedback(bot) must be called before use") from e


# ====== Публичное API ======
async def send_post_chat_feedback(user_id: int, peer_id: int, mid: int) -> None:
    """
    Показывает пост-чатовый экран с вариантами:
    ⭐️ Оценить | 🚩 Пожаловаться | ➡️ Пропустить

    :param user_id: кому показываем экран
    :param peer_id: id собеседника (сейчас не используется, оставлен для совместимости сигнатуры)
    :param mid: id матча (вшивается в callback_data)
    """
    try:
        await _bot().send_message(
            user_id,
            "Как тебе собеседник? Выбери оценку (1–5), можешь пожаловаться или пропустить:",
            reply_markup=post_chat_rate_kb(mid),
        )
    except Exception:
        # не валим поток, если пользователь закрыл ЛС/заблокировал бота и т.п.
        pass


# Что отдаём наружу
__all__ = [
    "init_feedback",
    "send_post_chat_feedback",
    # реэкспорт клавиатур для удобства импортов
    "rate_or_complain_kb",
    "post_chat_rate_kb",
    "post_chat_actions_kb",
    "rate_stars_kb",
]
