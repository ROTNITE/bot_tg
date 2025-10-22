# app/services/inactivity.py
from __future__ import annotations

import asyncio
from math import ceil
from typing import Awaitable, Callable, Dict, Optional, Tuple

from aiogram import Bot

from app.runtime import (
    ACTIVE, LAST_SEEN,
    DEADLINE, LAST_SHOWN, WATCH, WARNED,
    COUNTDOWN_TASKS, COUNTDOWN_MSGS,
    _nowm, _now, g_inactivity,
)
from app.services.matching import end_current_chat


# ====== Контекст (Bot и коллбеки верхнего уровня) ======

_MenuFor = Callable[[int], Awaitable]                       # async def menu_for(user_id) -> ReplyKeyboardMarkup
_SendFeedback = Callable[[int, int, int], Awaitable[None]]  # async def send_post_chat_feedback(me, peer, mid) -> None

_CTX: Dict[str, object] = {"bot": None, "menu_for": None, "send_fb": None}

def init_inactivity(bot: Bot,
                    menu_for: _MenuFor,
                    send_post_chat_feedback: _SendFeedback) -> None:
    """
    Инициализирует сервис.
    Вызывать один раз при старте приложения.
    """
    _CTX["bot"] = bot
    _CTX["menu_for"] = menu_for
    _CTX["send_fb"] = send_post_chat_feedback

def _bot() -> Bot:
    bot = _CTX["bot"]
    assert bot is not None, "inactivity.init_inactivity(bot, ...) not called"
    return bot  # type: ignore[return-value]

def _menu_for() -> _MenuFor:
    f = _CTX["menu_for"]
    assert f is not None, "inactivity.init_inactivity(..., menu_for=...) not called"
    return f  # type: ignore[return-value]

def _send_fb() -> _SendFeedback:
    f = _CTX["send_fb"]
    assert f is not None, "inactivity.init_inactivity(..., send_post_chat_feedback=...) not called"
    return f  # type: ignore[return-value]


# ====== Публичные утилиты для RAM-таймера ======

async def _watch_inactivity(mid: int, a: int, b: int):
    """
    Каждую секунду проверяет дедлайн молчания.
    За 60 сек до автозакрытия — показывает обратный отсчёт.
    На нуле — завершает матч и шлёт фидбек-форму.
    """
    bot = _bot()
    menu_for = _menu_for()
    send_fb = _send_fb()

    try:
        while True:
            await asyncio.sleep(1)

            # матч всё ещё актуален?
            if a not in ACTIVE or b not in ACTIVE:
                return
            if ACTIVE.get(a, (None, None))[1] != mid or ACTIVE.get(b, (None, None))[1] != mid:
                return

            now = _nowm()
            deadline = DEADLINE.get(mid, now + g_inactivity())
            remaining = ceil(deadline - now)

            # показать предупреждение и запустить счётчик
            if 0 < remaining <= 60 and not WARNED.get(mid):
                WARNED[mid] = True
                warn_text = (
                    f"⌛️ Тишина… Чат автоматически завершится через {remaining} сек.\n"
                    f"Напиши любое сообщение, чтобы продолжить разговор."
                )
                try:
                    ma = await bot.send_message(a, warn_text)
                    mb = await bot.send_message(b, warn_text)
                    COUNTDOWN_MSGS[mid] = (ma.message_id, mb.message_id)
                except Exception:
                    COUNTDOWN_MSGS[mid] = (None, None)
                COUNTDOWN_TASKS[mid] = asyncio.create_task(_countdown(mid, a, b))

            # дедлайн — закрываем
            if remaining <= 0:
                await _stop_countdown(mid, a, b, delete_msgs=True)
                await end_current_chat(a)
                await end_current_chat(b)
                _cleanup_match(mid, a, b)
                DEADLINE.pop(mid, None)
                LAST_SHOWN.pop(mid, None)
                try:
                    await bot.send_message(a, "Чат завершён из-за неактивности.",
                                           reply_markup=(await menu_for(a)))
                    await bot.send_message(b, "Чат завершён из-за неактивности.",
                                           reply_markup=(await menu_for(b)))
                except Exception:
                    pass
                # запрос фидбека
                await send_fb(a, b, mid)
                await send_fb(b, a, mid)
                return
    except asyncio.CancelledError:
        return


def _cleanup_match(mid: int, a: int, b: int) -> None:
    """
    Сбрасывает RAM-структуры по матчу и отменяет фоновые задачи.
    Ничего не делает с БД — это обязанность вызывающего кода.
    """
    ACTIVE.pop(a, None)
    ACTIVE.pop(b, None)
    LAST_SEEN.pop(a, None)
    LAST_SEEN.pop(b, None)

    t = WATCH.pop(mid, None)
    if t and not t.done():
        t.cancel()

    DEADLINE.pop(mid, None)
    LAST_SHOWN.pop(mid, None)
    WARNED.pop(mid, None)

    t2 = COUNTDOWN_TASKS.pop(mid, None)
    if t2 and not t2.done():
        t2.cancel()
    COUNTDOWN_MSGS.pop(mid, None)


async def _countdown(mid: int, a: int, b: int):
    """
    Обновляет текст «⌛️ Осталось N сек…» раз в секунду до 60 сек.
    Сбрасывается, если тишина прерывается (DEADLINE уходит > 60 сек).
    """
    bot = _bot()
    try:
        while True:
            await asyncio.sleep(1)

            # актуальность матча
            if a not in ACTIVE or b not in ACTIVE:
                return
            if ACTIVE.get(a, (None, None))[1] != mid or ACTIVE.get(b, (None, None))[1] != mid:
                return

            now = _nowm()
            deadline = DEADLINE.get(mid, now + g_inactivity())
            remaining = ceil(deadline - now)

            if remaining > 60:
                await _stop_countdown(mid, a, b, delete_msgs=True)
                return
            if remaining <= 0:
                return
            if LAST_SHOWN.get(mid) == remaining:
                continue
            LAST_SHOWN[mid] = remaining

            ids = COUNTDOWN_MSGS.get(mid)
            if not ids:
                continue
            a_msg, b_msg = ids
            text = f"⌛️ Тишина… Осталось {remaining} сек.\nНапиши, чтобы продолжить."
            try:
                if a_msg:
                    await bot.edit_message_text(chat_id=a, message_id=a_msg, text=text)
            except Exception:
                pass
            try:
                if b_msg:
                    await bot.edit_message_text(chat_id=b, message_id=b_msg, text=text)
            except Exception:
                pass
    except asyncio.CancelledError:
        return


async def _stop_countdown(mid: int, a: int, b: int, *, delete_msgs: bool = True) -> None:
    """
    Отключает и (опционально) удаляет сообщения обратного отсчёта.
    """
    t = COUNTDOWN_TASKS.pop(mid, None)
    if t and not t.done():
        t.cancel()

    ids = COUNTDOWN_MSGS.pop(mid, None)
    if delete_msgs and ids:
        bot = _bot()
        a_msg, b_msg = ids
        try:
            if a_msg:
                await bot.delete_message(chat_id=a, message_id=a_msg)
        except Exception:
            pass
        try:
            if b_msg:
                await bot.delete_message(chat_id=b, message_id=b_msg)
        except Exception:
            pass
    WARNED.pop(mid, None)


__all__ = [
    "init_inactivity",
    "_watch_inactivity",
    "_countdown",
    "_stop_countdown",
    "_cleanup_match",
]
