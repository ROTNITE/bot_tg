# app/handlers/chat.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove  # ⬅️ ReplyKeyboardRemove берём из aiogram.types

from app.keyboards.common import cancel_kb, main_menu
from app.keyboards.admin import admin_reply_menu  # ⬅️
from app import config as cfg

from app.services.matching import (
    active_peer, _materialize_session_if_needed, end_current_chat,
    record_separation, enqueue, try_match_now,
)
from app.services.inactivity import _stop_countdown as stop_countdown  # ⬅️ явный алиас
from app.runtime import (
    DEADLINE, LAST_SHOWN, WARNED, COUNTDOWN_TASKS, COUNTDOWN_MSGS,
    _now as now_wall, _nowm, g_inactivity,
)
from app.db.repo import get_role, get_user  # ⬅️ get_user берём из repo

router = Router(name="chat")

# локальные помощники, чтобы не требовать несуществующих функций из services.matching
async def is_chat_active(uid: int) -> bool:
    return (await active_peer(uid)) is not None

async def has_required_prefs(uid: int) -> bool:
    u = await get_user(uid)
    return bool(u and u[1] and u[2])

# …остальной код файла оставляем прежним (он уже использует main_menu/admin_reply_menu/stop_countdown) …

async def _menu_for(user_id: int):
    role = await get_role(user_id)
    return admin_reply_menu() if (role == "admin" or user_id in cfg.ADMIN_IDS) else main_menu()


# Блокируем нажатия «менюшных» кнопок во время активного чата (пусть relay заберёт апдейт)
@router.message(F.text.in_({"🧭 Режимы", "👤 Анкета", "🆘 Поддержка", "📇 Просмотр анкет",
                            "🕵️ Анонимный чат", "💰 Баланс", "⭐️ Оценить собеседника", "🚩 Пожаловаться"}))
async def block_menu_buttons_in_chat(m: Message):
    if await is_chat_active(m.from_user.id):
        raise SkipHandler
    raise SkipHandler


@router.message(F.text.regexp(r"^/"))
async def block_slash_cmds_in_chat(m: Message):
    if await is_chat_active(m.from_user.id):
        await _materialize_session_if_needed(m.from_user.id)
        await m.answer(cfg.BLOCK_TXT, reply_markup=ReplyKeyboardRemove())
        return
    raise SkipHandler


@router.message()
async def relay_chat(m: Message, state: FSMContext):
    # Обрабатываем только если действительно есть активный чат
    if not await is_chat_active(m.from_user.id):
        raise SkipHandler

    materialized = await _materialize_session_if_needed(m.from_user.id)
    if not materialized:
        raise SkipHandler
    peer, mid = materialized

    # Сброс таймера молчания и фиксация активности
    DEADLINE[mid] = _nowm() + g_inactivity()
    LAST_SHOWN.pop(mid, None)

    now = now_wall()
    # (восстановление LAST_SEEN делает matching._materialize_session_if_needed)

    await stop_countdown(mid, m.from_user.id, peer, delete_msgs=True)
    WARNED.pop(mid, None)
    t = COUNTDOWN_TASKS.pop(mid, None)
    if t and not t.done():
        t.cancel()
    COUNTDOWN_MSGS.pop(mid, None)

    # Команды внутри чата
    if m.text:
        ttxt = m.text.strip().lower()
        if ttxt == "!stop":
            a = m.from_user.id
            b = peer
            await end_current_chat(a)
            from app.services.matching import _cleanup_match  # локальный импорт
            _cleanup_match(mid, a, b)
            await send_post_chat_feedback(a, b, mid)
            await send_post_chat_feedback(b, a, mid)
            await m.answer("Чат завершён. Нажми «🔎 Найти собеседника», чтобы начать новый.", reply_markup=(await _menu_for(a)))
            await m.bot.send_message(b, "Собеседник завершил чат.", reply_markup=(await _menu_for(b)))
            return

        if ttxt == "!next":
            a = m.from_user.id
            b = peer
            if not await has_required_prefs(a):
                await end_current_chat(a)
                from app.services.matching import _cleanup_match
                _cleanup_match(mid, a, b)
                await send_post_chat_feedback(a, b, mid)
                await send_post_chat_feedback(b, a, mid)
                await m.answer("Чтобы продолжить поиск, укажи свой пол и кого ищешь.", reply_markup=gender_self_kb())
                await m.bot.send_message(b, "Собеседник завершил чат.", reply_markup=(await _menu_for(b)))
                return
            await record_separation(a, b)
            await end_current_chat(a)
            from app.services.matching import _cleanup_match
            _cleanup_match(mid, a, b)
            me = await get_user(a)
            await enqueue(a, me[1], me[2])
            await m.answer("Ищу следующего собеседника…", reply_markup=cancel_kb())
            await m.bot.send_message(b, "Собеседник ушёл к следующему. Ты можешь нажать «🔎 Найти собеседника».", reply_markup=(await _menu_for(b)))
            await try_match_now(a)
            return

        if ttxt == "!reveal":
            await _handle_reveal(m.from_user.id, peer)
            return

    # Пересылка контента с маскировкой
    await _relay_payload(m, peer)


@router.message(F.text.regexp(r"^!(stop|next|reveal)\b"))
async def bang_commands_when_db_active(m: Message, state: FSMContext):
    # Если RAM уже есть — relay_chat обработает
    from app.runtime import ACTIVE
    if m.from_user.id in ACTIVE:
        return

    mat = await _materialize_session_if_needed(m.from_user.id)
    if not mat:
        await m.answer("Нет активного чата.")
        return

    peer, mid = mat
    txt = (m.text or "").strip().lower()

    if txt.startswith("!stop"):
        a = m.from_user.id
        b = peer
        await end_current_chat(a)
        from app.services.matching import _cleanup_match
        _cleanup_match(mid, a, b)
        await send_post_chat_feedback(a, b, mid)
        await send_post_chat_feedback(b, a, mid)
        await m.answer("Чат завершён. Нажми «🔎 Найти собеседника», чтобы начать новый.", reply_markup=(await _menu_for(m.from_user.id)))
        await m.bot.send_message(b, "Собеседник завершил чат.", reply_markup=(await _menu_for(b)))
        return

    if txt.startswith("!next"):
        a = m.from_user.id
        b = peer
        if not await has_required_prefs(a):
            await end_current_chat(a)
            from app.services.matching import _cleanup_match
            _cleanup_match(mid, a, b)
            await send_post_chat_feedback(a, b, mid)
            await send_post_chat_feedback(b, a, mid)
            from app.keyboards.common import gender_self_kb
            await m.answer("Чтобы продолжить поиск, укажи свой пол и кого ищешь.", reply_markup=gender_self_kb())
            await m.bot.send_message(b, "Собеседник завершил чат.", reply_markup=(await _menu_for(b)))
            return
        await record_separation(a, b)
        await end_current_chat(a)
        from app.services.matching import _cleanup_match
        _cleanup_match(mid, a, b)
        me = await get_user(a)
        await enqueue(a, me[1], me[2])
        await m.answer("Ищу следующего собеседника…", reply_markup=cancel_kb())
        await m.bot.send_message(b, "Собеседник ушёл к следующему. Ты можешь нажать «🔎 Найти собеседника».", reply_markup=(await _menu_for(b)))
        await try_match_now(a)
        return

    if txt.startswith("!reveal"):
        await _handle_reveal(m.from_user.id, peer)
        return


# ---------- Вспомогательные для пересылки и reveal ----------

async def _relay_payload(m: Message, peer: int):
    from app.services.matching import send_text_anonym, clean_cap
    # Текст — с анонимайзером
    if m.text:
        await send_text_anonym(peer, m.text)
    elif m.photo:
        await m.bot.send_photo(peer, m.photo[-1].file_id, caption=clean_cap(m.caption), protect_content=True)
    elif m.animation:
        await m.bot.send_animation(peer, m.animation.file_id, caption=clean_cap(m.caption), protect_content=True)
    elif m.video:
        await m.bot.send_video(peer, m.video.file_id, caption=clean_cap(m.caption), protect_content=True)
    elif m.audio:
        await m.bot.send_audio(peer, m.audio.file_id, caption=clean_cap(m.caption), protect_content=True)
    elif m.voice:
        await m.bot.send_voice(peer, m.voice.file_id, caption=clean_cap(m.caption), protect_content=True)
    elif m.video_note:
        await m.bot.send_video_note(peer, m.video_note.file_id, protect_content=True)
    elif m.document:
        await m.bot.send_document(peer, m.document.file_id, caption=clean_cap(m.caption), protect_content=True)
    elif m.contact or m.location or m.venue or m.poll or m.dice or m.game:
        await m.answer("Этот тип вложений отключён в анонимном чате.")


async def _handle_reveal(me_id: int, peer_id: int):
    # Реализация из bot.py: проверка анкет, флаги a_reveal/b_reveal и показ карточек
    from app.db.core import db
    me = await get_user(me_id)
    peer = await get_user(peer_id)
    if not (me and peer and me[3] == 1 and peer[3] == 1):
        from aiogram import Bot
        await Bot.get_current().send_message(me_id, "Раскрытие невозможно: у одного из вас не заполнена анкета.")
        return

    async with db() as conn:
        cur = await conn.execute(
            "SELECT id,a_id,b_id,a_reveal,b_reveal FROM matches WHERE active=1 AND (a_id=? OR b_id=?) ORDER BY id DESC LIMIT 1",
            (me_id, me_id)
        )
        row = await cur.fetchone()
        if not row:
            from aiogram import Bot
            await Bot.get_current().send_message(me_id, "Нет активного чата.")
            return
        mid, a, b, ar, br = row
        is_a = (me_id == a)

        if (is_a and ar == 1) or ((not is_a) and br == 1):
            from aiogram import Bot
            await Bot.get_current().send_message(me_id, "Запрос на раскрытие уже отправлен. Ждём собеседника.")
            return

        if is_a:
            await conn.execute("UPDATE matches SET a_reveal=1 WHERE id=?", (mid,))
        else:
            await conn.execute("UPDATE matches SET b_reveal=1 WHERE id=?", (mid,))
        await conn.commit()

        cur = await conn.execute("SELECT a_reveal,b_reveal FROM matches WHERE id=?", (mid,))
        ar, br = await cur.fetchone()

    from aiogram import Bot
    if ar == 1 and br == 1:
        await _send_reveal_card(a, peer_id)
        await _send_reveal_card(b, me_id)
        await Bot.get_current().send_message(a, "Взаимное раскрытие выполнено.")
        await Bot.get_current().send_message(b, "Взаимное раскрытие выполнено.")
    else:
        await Bot.get_current().send_message(me_id, "Запрос на раскрытие отправлен. Ждём согласия собеседника.")


async def _send_reveal_card(to_id: int, whose_id: int):
    from aiogram import Bot
    from app.services.matching import format_profile_text
    from app.db.repo import get_user
    u = await get_user(whose_id)
    if not u:
        await Bot.get_current().send_message(to_id, "Профиль не найден.")
        return

    txt = format_profile_text(u)
    photos = [p for p in (u[10], u[11], u[12]) if p]
    if photos:
        for p in photos[:-1]:
            await Bot.get_current().send_photo(to_id, p, protect_content=True)
        await Bot.get_current().send_photo(to_id, photos[-1], caption=txt, protect_content=True, parse_mode=None)
    else:
        await Bot.get_current().send_message(to_id, txt, parse_mode=None, disable_web_page_preview=True, protect_content=True)
