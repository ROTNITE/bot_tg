# app/handlers/complaints.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db.core import db
from app.keyboards.common import (
    rate_or_complain_kb,
    post_chat_actions_kb,
    rate_stars_kb,
    cancel_kb,
)
from app.runtime import safe_edit_message
from app.states import ComplaintState

router = Router(name="complaints")


# ------ Кнопки пост-чатового экрана ------

@router.callback_query(F.data.regexp(r"^rate:\d+:\d$"))
async def cb_rate(c: CallbackQuery):
    try:
        _, mid_s, stars_s = c.data.split(":")
        mid = int(mid_s); stars = int(stars_s)
        assert 1 <= stars <= 5
    except Exception:
        return await c.answer("Некорректная оценка.", show_alert=True)

    # проверяем, что пользователь был участником этого матча и узнаём peer
    async with db() as conn:
        cur = await conn.execute("SELECT a_id,b_id FROM matches WHERE id=?", (mid,))
        row = await cur.fetchone()
    if not row:
        return await c.answer("Матч не найден.", show_alert=True)

    a_id, b_id = int(row[0]), int(row[1])
    if c.from_user.id not in (a_id, b_id):
        return await c.answer("Это не твой диалог.", show_alert=True)

    to_user = b_id if c.from_user.id == a_id else a_id

    # фиксируем оценку (один раз за матч)
    try:
        async with db() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO ratings(match_id,from_user,to_user,stars) VALUES(?,?,?,?)",
                (mid, c.from_user.id, to_user, stars)
            )
            await conn.commit()
    except Exception:
        pass

    try:
        await safe_edit_message(c.message, text="Спасибо! Оценка сохранена.", reply_markup=None)
    except Exception:
        pass
    await c.answer("Оценка учтена.")


@router.callback_query(F.data.regexp(r"^postfb:rate:\d+$"))
async def postfb_rate(c: CallbackQuery):
    mid = int(c.data.split(":")[2])
    try:
        await safe_edit_message(
            c.message,
            text="Поставь оценку собеседнику (1–5):",
            reply_markup=rate_stars_kb(mid)
        )
    except Exception:
        pass
    await c.answer()


@router.callback_query(F.data.regexp(r"^postfb:complain:\d+$"))
async def postfb_complain(c: CallbackQuery, state: FSMContext):
    mid = int(c.data.split(":")[2])
    # найдём участника-«второго», на которого и будет жалоба
    async with db() as conn:
        cur = await conn.execute("SELECT a_id,b_id FROM matches WHERE id=?", (mid,))
        row = await cur.fetchone()
    if not row:
        return await c.answer("Матч не найден.", show_alert=True)

    a_id, b_id = int(row[0]), int(row[1])
    about_id = b_id if c.from_user.id == a_id else a_id

    await state.set_state(ComplaintState.wait_text)
    await state.update_data(mid=mid, about_id=about_id)

    try:
        await safe_edit_message(c.message, text="Опиши жалобу одним сообщением. Чем подробнее — тем лучше.", reply_markup=None)
    except Exception:
        pass
    await c.answer()


@router.callback_query(F.data.regexp(r"^postfb:skip:\d+$"))
async def postfb_skip(c: CallbackQuery):
    try:
        await safe_edit_message(c.message, text="Ок, пропустили. Спасибо!", reply_markup=None)
    except Exception:
        pass
    await c.answer("Пропущено.")


@router.callback_query(F.data.regexp(r"^postfb:back:\d+$"))
async def postfb_back(c: CallbackQuery):
    mid = int(c.data.split(":")[2])
    try:
        await safe_edit_message(
            c.message,
            text="Что сделать с завершённым диалогом?",
            reply_markup=post_chat_actions_kb(mid)
        )
    except Exception:
        pass
    await c.answer()


# ------ Текст жалобы ------

@router.message(ComplaintState.wait_text)
async def complaint_text(m: Message, state: FSMContext):
    from app import config as cfg
    from app.handlers import menu_for
    d = await state.get_data()
    mid = int(d.get("mid")); about_id = int(d.get("about_id"))
    text = (m.text or "").strip()

    async with db() as conn:
        await conn.execute(
            "INSERT INTO complaints(match_id,from_user,about_user,text) VALUES(?,?,?,?)",
            (mid, m.from_user.id, about_id, text)
        )
        await conn.commit()

    # шлём админам
    for admin_id in (cfg.ADMIN_IDS or []):
        try:
            await m.bot.send_message(
                admin_id,
                f"🚩 Жалоба от <code>{m.from_user.id}</code> на <code>{about_id}</code>\n"
                f"Матч: <code>{mid}</code>\n\n{text}"
            )
        except Exception:
            pass

    await state.clear()
    await m.answer("Жалоба отправлена админам. Спасибо!", reply_markup=(await menu_for(m.from_user.id)))


# Быстрые действия из главного меню
@router.message(F.text == "⭐️ Оценить собеседника")
async def rate_from_menu(m: Message):
    from app.handlers import menu_for
    from app.services.matching import last_match_info
    if not await last_match_info(m.from_user.id):
        return await m.answer("Пока не с кем — ещё не было диалогов.", reply_markup=(await menu_for(m.from_user.id)))
    mid, _peer, _active = await last_match_info(m.from_user.id)

    # проверим, не оценивал ли уже этот матч
    async with db() as conn:
        cur = await conn.execute("SELECT 1 FROM ratings WHERE match_id=? AND from_user=?", (mid, m.from_user.id))
        done = await cur.fetchone()
    if done:
        return await m.answer("Последний диалог уже оценён. Спасибо!", reply_markup=(await menu_for(m.from_user.id)))

    await m.answer("Оцени последнего собеседника:", reply_markup=rate_or_complain_kb(mid))


@router.message(F.text == "🚩 Пожаловаться")
async def complain_from_menu(m: Message, state: FSMContext):
    from app.handlers import menu_for
    from app.services.matching import last_match_info
    info = await last_match_info(m.from_user.id)
    if not info:
        return await m.answer("Пока не на кого — ещё не было диалогов.", reply_markup=(await menu_for(m.from_user.id)))
    mid, peer, _active = info
    await state.set_state(ComplaintState.wait_text)
    await state.update_data(mid=mid, about_id=peer)
    await m.answer("Опиши жалобу одним сообщением. Чем подробнее — тем лучше.", reply_markup=cancel_kb())
