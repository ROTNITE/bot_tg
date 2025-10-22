# app/runtime.py
from __future__ import annotations

import asyncio
import time
from typing import Dict, Tuple, Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from app.db.core import db

# ===================== Settings cache =====================

SETTINGS: Dict[str, str] = {}  # key -> value (строки, кастим при чтении)

DEFAULT_SETTINGS = {
    "inactivity_seconds": "180",   # ⏱️ тайм-аут молчания
    "ref_bonus_points":   "20",    # 🎯 реф-бонус
    "daily_bonus_points": "10",    # 🎁 ежедневный бонус
    "block_rounds":       "2",     # 🔁 сколько «раундов» не матчить ту же пару
    "support_enabled":    "1",     # 🆘 включен ли саппорт (1/0)
}

async def load_settings_cache() -> None:
    """Читает таблицу settings в память, докладывает дефолты при отсутствии ключей."""
    SETTINGS.clear()
    async with db() as conn:
        cur = await conn.execute("SELECT key, value FROM settings")
        for k, v in await cur.fetchall():
            SETTINGS[k] = str(v)

    # проставим дефолты, если чего-то нет
    async with db() as conn:
        for k, v in DEFAULT_SETTINGS.items():
            if k not in SETTINGS:
                await conn.execute(
                    "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                    (k, v),
                )
                SETTINGS[k] = v
        await conn.commit()

async def set_setting(key: str, value: str) -> None:
    """Обновляет значение настройки в БД и в кэше."""
    async with db() as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
            (key, str(value)),
        )
        await conn.commit()
    SETTINGS[key] = str(value)

def g_inactivity() -> int:
    return int(SETTINGS.get("inactivity_seconds", DEFAULT_SETTINGS["inactivity_seconds"]))

def g_ref_bonus() -> int:
    return int(SETTINGS.get("ref_bonus_points", DEFAULT_SETTINGS["ref_bonus_points"]))

def g_daily_bonus() -> int:
    return int(SETTINGS.get("daily_bonus_points", DEFAULT_SETTINGS["daily_bonus_points"]))

def g_block_rounds() -> int:
    return int(SETTINGS.get("block_rounds", DEFAULT_SETTINGS["block_rounds"]))

def g_support_enabled() -> bool:
    return SETTINGS.get("support_enabled", DEFAULT_SETTINGS["support_enabled"]) == "1"

def intro_text() -> str:
    """Версия приветственного текста с подстановкой текущего таймаута неактивности."""
    t = g_inactivity()
    return (
        "⚠️ Перед использованием нужно подписаться на канал: t.me/nektomephi\n\n"
        "👋 Добро пожаловать! Это анонимный чат-бот <b>исключительно для студентов МИФИ</b>.\n\n"
        "!!! В НАСТОЯЩЕЕ ВРЕМЯ РАБОТАЕТ В ТЕСТОВОМ РЕЖИМЕ !!!\n"
        "Бот <b>не является официальным проектом университета</b> — это независимая студенческая инициатива, "
        "созданная для безопасного и комфортного общения внутри сообщества.\n\n"
        "Это гибрид дайвинчика и nekto.me: ты общаешься анонимно, а при взаимном согласии "
        "можно <b>раскрыть личности</b> через команду <code>!reveal</code> (только если у обоих заполнены анкеты).\n\n"
        "💡 На данный момент доступен только режим <b>Анонимный чат</b>.\n"
        "📇 Режим <b>Просмотр анкет</b> — находится в разработке.\n\n"
        "⚙️ Как пользоваться:\n"
        "1️⃣ Выбери свой пол и кого ищешь.\n"
        "2️⃣ По желанию заполни анкету — она нужна только для взаимного раскрытия.\n"
        "3️⃣ Нажми «🔎 Найти собеседника» и начни анонимный диалог.\n\n"
        "💬 Во время чата доступны команды:\n"
        "<code>!next</code> — следующий собеседник\n"
        "<code>!stop</code> — завершить диалог\n"
        "<code>!reveal</code> — запросить взаимное раскрытие\n\n"
        f"⚠️ Если кто-то молчит более {t} секунд, диалог автоматически завершится у обоих."
    )

async def safe_edit_message(
    msg: Message, *, text: Optional[str] = None, reply_markup=None
) -> None:
    """
    Аккуратно правит сообщение: если текст не меняется — редактирует только клавиатуру.
    Игнорит 'message is not modified'.
    """
    try:
        current_text = msg.text or ""
        if text is not None and text != current_text:
            await msg.edit_text(text, reply_markup=reply_markup)
        elif reply_markup is not None:
            await msg.edit_reply_markup(reply_markup=reply_markup)
        # иначе менять нечего
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        raise

# ===================== Runtime (RAM) =====================

_nowm = time.monotonic            # монотоничные секунды (для дедлайнов)
def _now() -> float:             # «стенные» секунды (для LAST_SEEN)
    return time.time()

# Матчевые таймеры/счётчики
DEADLINE: Dict[int, float] = {}   # match_id -> monotonic deadline
LAST_SHOWN: Dict[int, int] = {}   # match_id -> последний показанный остаток (сек)

# Активные чаты и активность
ACTIVE: Dict[int, Tuple[int, int]] = {}   # user_id -> (peer_id, match_id)
LAST_SEEN: Dict[int, float] = {}          # user_id -> last_seen_unix

# Вотчеры/обратные отсчёты (таски создаются в сервисе неактивности)
WATCH: Dict[int, asyncio.Task] = {}              # match_id -> watcher task
WARNED: Dict[int, bool] = {}                     # match_id -> предупреждение о завершении
COUNTDOWN_TASKS: Dict[int, asyncio.Task] = {}    # match_id -> countdown task
COUNTDOWN_MSGS: Dict[int, Tuple[Optional[int], Optional[int]]] = {}  # match_id -> (msg_id_a, msg_id_b)

# Маршрутизация ответов админа в саппорте (msg_id бота -> user_id)
SUPPORT_RELAY: Dict[int, int] = {}

__all__ = [
    # settings cache + utils
    "SETTINGS", "DEFAULT_SETTINGS", "load_settings_cache", "set_setting",
    "g_inactivity", "g_ref_bonus", "g_daily_bonus", "g_block_rounds", "g_support_enabled",
    "intro_text", "safe_edit_message",
    # runtime clocks
    "_nowm", "_now",
    # RAM structures
    "DEADLINE", "LAST_SHOWN", "ACTIVE", "LAST_SEEN", "WATCH", "WARNED",
    "COUNTDOWN_TASKS", "COUNTDOWN_MSGS", "SUPPORT_RELAY",
]
