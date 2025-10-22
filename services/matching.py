# app/services/matching.py
from __future__ import annotations
import re
from html import escape as h

import asyncio
from math import ceil
from typing import Optional, Tuple, Awaitable, Callable, Dict

from aiogram import Bot
from aiogram.types import ReplyKeyboardRemove

from app.db.core import db
from app.db.repo import get_status  # статусы пользователя для приветствия
from app.runtime import (
    ACTIVE, LAST_SEEN, DEADLINE, LAST_SHOWN, WATCH, WARNED,
    COUNTDOWN_TASKS, COUNTDOWN_MSGS,
    _nowm, _now, g_inactivity, g_block_rounds,
)

# ========================== Контекст ==========================

# Коллбеки, которые предоставляет слой хэндлеров:
#  - send_post_chat_feedback(user_id, peer_id, mid) -> Awaitable[None]
#  - menu_for(user_id) -> Awaitable[ReplyKeyboardMarkup]
_MenuFor = Callable[[int], Awaitable]
_SendFeedback = Callable[[int, int, int], Awaitable]

_CTX: Dict[str, object] = {
    "bot": None,
    "menu_for": None,
    "send_post_chat_feedback": None,
}

def init_matching(bot: Bot,
                  send_post_chat_feedback: _SendFeedback,
                  menu_for: _MenuFor) -> None:
    """Инициализируй сервис ссылками на Bot и вспомогательные коллбеки."""
    _CTX["bot"] = bot
    _CTX["menu_for"] = menu_for
    _CTX["send_post_chat_feedback"] = send_post_chat_feedback

def _bot() -> Bot:
    b = _CTX["bot"]
    assert b is not None, "matching.init_matching(bot, ...) not called"
    return b  # type: ignore[return-value]

def _menu_for() -> _MenuFor:
    mf = _CTX["menu_for"]
    assert mf is not None, "matching.init_matching(..., menu_for=...) not called"
    return mf  # type: ignore[return-value]

def _send_fb() -> _SendFeedback:
    f = _CTX["send_post_chat_feedback"]
    assert f is not None, "matching.init_matching(..., send_post_chat_feedback=...) not called"
    return f  # type: ignore[return-value]

# ====================== Очередь / состояния =====================

async def active_peer(tg_id: int) -> Optional[int]:
    """Вернуть ID собеседника, если у пользователя активный чат."""
    if tg_id in ACTIVE:
        return ACTIVE[tg_id][0]
    async with db() as conn:
        cur = await conn.execute(
            "SELECT a_id,b_id FROM matches "
            "WHERE active=1 AND (a_id=? OR b_id=?) "
            "ORDER BY id DESC LIMIT 1",
            (tg_id, tg_id),
        )
        row = await cur.fetchone()
        if not row:
            return None
        a, b = int(row[0]), int(row[1])
        return b if a == tg_id else a

async def end_current_chat(tg_id: int) -> None:
    """Завершить все активные матчи пользователя в БД."""
    async with db() as conn:
        await conn.execute(
            "UPDATE matches SET active=0 WHERE active=1 AND (a_id=? OR b_id=?)",
            (tg_id, tg_id),
        )
        await conn.commit()

async def enqueue(tg_id: int, gender: str, seeking: str) -> None:
    async with db() as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO queue(tg_id, gender, seeking, ts) "
            "VALUES(?,?,?,strftime('%s','now'))",
            (tg_id, gender, seeking),
        )
        await conn.commit()

async def dequeue(tg_id: int) -> None:
    async with db() as conn:
        await conn.execute("DELETE FROM queue WHERE tg_id=?", (tg_id,))
        await conn.commit()

async def in_queue(tg_id: int) -> bool:
    async with db() as conn:
        cur = await conn.execute("SELECT 1 FROM queue WHERE tg_id=?", (tg_id,))
        return (await cur.fetchone()) is not None

# ========================== Антиповтор ==========================

async def record_separation(a: int, b: int) -> None:
    """После !next — отметим пару, чтобы пару раундов не матчить снова."""
    br = g_block_rounds()
    async with db() as conn:
        # двунаправленно
        for u, p in ((a, b), (b, a)):
            await conn.execute(
                "INSERT INTO recent_partners(u_id,partner_id,block_left) "
                "VALUES(?,?,?) "
                "ON CONFLICT(u_id,partner_id) DO UPDATE SET block_left=?",
                (u, p, br, br),
            )
        await conn.commit()

async def decay_blocks(u_id: int) -> None:
    """Снижаем счетчик 'block_left' у недавних партнёров пользователя."""
    async with db() as conn:
        await conn.execute(
            "UPDATE recent_partners SET block_left=block_left-1 "
            "WHERE u_id=? AND block_left>0",
            (u_id,),
        )
        await conn.execute(
            "DELETE FROM recent_partners WHERE u_id=? AND block_left<=0",
            (u_id,),
        )
        await conn.commit()

async def is_recent_blocked(u_id: int, candidate_id: int) -> bool:
    async with db() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM recent_partners "
            "WHERE u_id=? AND partner_id=? AND block_left>0",
            (u_id, candidate_id),
        )
        return (await cur.fetchone()) is not None

# ========================== Подбор пары ==========================

async def find_partner(for_id: int) -> Optional[int]:
    """
    Находит кандидата из очереди по предпочтениям и антиповтору.
    """
    async with db() as conn:
        cur = await conn.execute(
            "SELECT gender,seeking FROM users WHERE tg_id=?",
            (for_id,),
        )
        me = await cur.fetchone()
        if not me:
            return None
        my_gender, my_seek = (me[0] or ""), (me[1] or "")

        cur = await conn.execute(
            """
            SELECT q.tg_id
            FROM queue q
            JOIN users u ON u.tg_id=q.tg_id
            LEFT JOIN recent_partners rp
                   ON rp.u_id=? AND rp.partner_id=q.tg_id AND rp.block_left>0
            WHERE q.tg_id<>?
              AND ((?='Не важно') OR u.gender=CASE ? WHEN 'Парни' THEN 'Парень' WHEN 'Девушки' THEN 'Девушка' END)
              AND (u.seeking='Не важно' OR u.seeking=CASE ? WHEN 'Парень' THEN 'Парни' WHEN 'Девушка' THEN 'Девушки' END)
              AND rp.partner_id IS NULL
            ORDER BY q.ts ASC
            LIMIT 1
            """,
            (for_id, for_id, my_seek, my_seek, my_gender),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else None

async def try_match_now(tg_id: int) -> None:
    """Проверить очередь и сразу стартовать матч, если нашёлся кандидат."""
    mate = await find_partner(tg_id)
    if mate:
        await start_match(tg_id, mate)

# ======================= Запуск и RAM-учёт =======================

async def start_match(a: int, b: int) -> None:
    """
    Старт матча: создаёт запись, поднимает RAM-состояние, запускает вотчер,
    отправляет обоим приветственные сообщения с рейтингами/статусами.
    """
    bot = _bot()

    # лёгкое «старение» блоков перед новым матчем
    await decay_blocks(a)
    await decay_blocks(b)

    # создать матч и вынуть id
    async with db() as conn:
        await conn.execute("DELETE FROM queue WHERE tg_id IN (?,?)", (a, b))
        cur = await conn.execute("INSERT INTO matches(a_id,b_id) VALUES(?,?)", (a, b))
        mid = int(cur.lastrowid)
        await conn.commit()

    # материализуем RAM
    ACTIVE[a] = (b, mid)
    ACTIVE[b] = (a, mid)
    now_wall = _now()
    LAST_SEEN[a] = now_wall
    LAST_SEEN[b] = now_wall
    DEADLINE[mid] = _nowm() + g_inactivity()
    LAST_SHOWN.pop(mid, None)

    # запустим вотчер
    WATCH[mid] = asyncio.create_task(_watch_inactivity(mid, a, b))

    # приветствие: статусы + рейтинги
    sa = await get_status(a)
    sb = await get_status(b)

    pa, pcnt = await _get_avg_rating(b)  # рейтинг собеседника для A
    ma, mcnt = await _get_avg_rating(a)  # собственный рейтинг A (для себя)
    pb, bcnt = await _get_avg_rating(a)  # рейтинг собеседника для B
    mb, bmcnt = await _get_avg_rating(b) # собственный рейтинг B (для себя)

    def fmt(avg, cnt):
        return f"{avg:.1f} ({cnt})" if avg is not None else "— (0)"

    def greet_line(self_status: Optional[str], peer_rating: str, my_rating: str) -> str:
        who = self_status or "без статуса"
        return (
            f"Ваш собеседник — {who}. Вы анонимны.\n"
            f"Рейтинг собеседника: {peer_rating}\n"
            f"Твой рейтинг: {my_rating}\n\n"
            "Команды в чате:\n"
            "<code>!next</code> — следующий собеседник\n"
            "<code>!stop</code> — закончить\n"
            "<code>!reveal</code> — взаимное раскрытие (если анкеты есть у обоих)\n"
        )

    try:
        await bot.send_message(a, greet_line(sb, fmt(pa, pcnt), fmt(ma, mcnt)),
                               reply_markup=ReplyKeyboardRemove())
        await bot.send_message(b, greet_line(sa, fmt(pb, bcnt), fmt(mb, bmcnt)),
                               reply_markup=ReplyKeyboardRemove())
    except Exception:
        pass

async def _materialize_session_if_needed(user_id: int) -> Optional[Tuple[int, int]]:
    """
    Восстанавливает RAM-состояние (ACTIVE/WATCH/DEADLINE и т.д.) из БД,
    если бот перезапускался. Возвращает (peer_id, match_id) или None.
    """
    if user_id in ACTIVE:
        peer_id, mid = ACTIVE[user_id]
        # гарантируем, что вотчер жив
        if mid not in WATCH or WATCH[mid].done():
            a, b = user_id, peer_id
            WATCH[mid] = asyncio.create_task(_watch_inactivity(mid, a, b))
        return ACTIVE[user_id]

    # искать активный матч в БД
    async with db() as conn:
        cur = await conn.execute(
            "SELECT id,a_id,b_id FROM matches "
            "WHERE active=1 AND (a_id=? OR b_id=?) "
            "ORDER BY id DESC LIMIT 1",
            (user_id, user_id),
        )
        row = await cur.fetchone()
    if not row:
        return None

    mid, a, b = int(row[0]), int(row[1]), int(row[2])
    peer = b if a == user_id else a

    # поднять RAM
    ACTIVE[a] = (b, mid)
    ACTIVE[b] = (a, mid)
    now_wall = _now()
    LAST_SEEN[a] = now_wall
    LAST_SEEN[b] = now_wall
    DEADLINE[mid] = _nowm() + g_inactivity()
    LAST_SHOWN.pop(mid, None)
    if mid not in WATCH or WATCH[mid].done():
        WATCH[mid] = asyncio.create_task(_watch_inactivity(mid, a, b))

    return (peer, mid)

# ===================== Вотчер неактивности =====================

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
    """Сбрасывает RAM-структуры по матчу."""
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
    """Обновляет текст «⌛️ Осталось N сек…» раз в секунду до 60 сек."""
    bot = _bot()
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
    """Отключает и (опционально) удаляет сообщения обратного отсчёта."""
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

# ========================= Вспомогательное =========================

async def _get_avg_rating(user_id: int) -> tuple[Optional[float], int]:
    """AVG(stars), COUNT(*) по оценкам получателя user_id."""
    async with db() as conn:
        cur = await conn.execute(
            "SELECT AVG(stars), COUNT(*) FROM ratings WHERE to_user=?",
            (user_id,),
        )
        row = await cur.fetchone()
        avg = float(row[0]) if row and row[0] is not None else None
        cnt = int(row[1] or 0)
        return avg, cnt

# ========================= Текст/санитайз и карточки профиля =========================

# Маскируем контакты в тексте (анонимность)
USER_RE = re.compile(r'(?<!\w)@[\w_]{3,}', re.I)                 # @username
TME_RE  = re.compile(r'(?:https?://)?t\.me/[^\s]+', re.I)        # t.me/...
TGID_RE = re.compile(r'tg://user\?id=\d+', re.I)                 # tg://user?id=...
MAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', re.I)            # email
PHON_RE = re.compile(r'(?<!\d)(?:\+?\d[\d\-\s()]{8,}\d)')        # телефон

def sanitize_text(s: str) -> str:
    s = TGID_RE.sub('[hidden]', s)
    s = TME_RE.sub('[link hidden]', s)
    s = USER_RE.sub('@hidden', s)
    s = MAIL_RE.sub('[email hidden]', s)
    s = PHON_RE.sub('[phone hidden]', s)
    return s

async def send_text_anonym(peer: int, text: str) -> None:
    """Шлём текст без HTML, без превью и с защитой контента."""
    await _bot().send_message(
        peer,
        sanitize_text(text),
        parse_mode=None,
        disable_web_page_preview=True,
        protect_content=True,
    )

def clean_cap(caption: Optional[str]) -> Optional[str]:
    """Санитайз подписи к медиа (если есть)."""
    return sanitize_text(caption) if caption else None

def format_profile_text(u: tuple) -> str:
    """
    Формат карточки профиля (как в исходном bot.py).
    u = (tg_id, gender, seeking, reveal_ready, first_name, last_name,
         faculty, age, about, username, photo1, photo2, photo3)
    """
    first = h((u[4] or "").strip())
    last = h((u[5] or "").strip())
    name = first or (last.split()[0] if last else "Без имени")

    age = u[7]
    age_str = str(age) if isinstance(age, int) else "—"
    faculty = h((u[6] or "—").strip())

    about = (u[8] or "").strip()
    first_line, rest = "", ""
    if about:
        lines = [h(ln.strip()) for ln in about.splitlines() if ln.strip()]
        if lines:
            first_line = lines[0]
            if len(lines) > 1:
                rest = "\n".join(lines[1:])

    header = f"{name}, {age_str}, 📍 {faculty}"
    if first_line:
        header += f" — {first_line}"
    body = f"\n{rest}" if rest else ""
    username = h((u[9] or "").strip())
    tail = f"\n\n{username}" if username else ""
    return header + body + tail

# ========================= История матчей =========================

async def last_match_info(user_id: int) -> Optional[tuple[int, int, int]]:
    """
    Возвращает (match_id, peer_id, active) для последнего матча пользователя.
    active: 1/0 по столбцу matches.active
    """
    async with db() as conn:
        cur = await conn.execute(
            """
            SELECT id, a_id, b_id, active
            FROM matches
            WHERE a_id=? OR b_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, user_id),
        )
        row = await cur.fetchone()
        if not row:
            return None
        mid, a, b, active = int(row[0]), int(row[1]), int(row[2]), int(row[3])
        peer = b if a == user_id else a
        return mid, peer, active

__all__ = [
    # init
    "init_matching",
    # queue & sessions
    "active_peer", "end_current_chat", "enqueue", "dequeue", "in_queue",
    "record_separation", "decay_blocks", "is_recent_blocked",
    "find_partner", "start_match", "try_match_now",
    "_materialize_session_if_needed",
    # helpers just added
    "sanitize_text", "send_text_anonym", "clean_cap",
    "format_profile_text", "last_match_info",
]
