# app/services/reveal_form.py
from __future__ import annotations

from typing import Awaitable, Callable, Dict, Optional, List

from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import FACULTIES
from app.db.repo import (
    set_user_fields,
    get_user_or_create,
    get_user,
)
from app.keyboards.common import (
    faculties_kb,
    about_kb,
    photos_empty_kb,
    photos_progress_kb,
    cancel_kb,
    main_menu,
)
from app.states import RevealForm


# ============= Контекст (коллбеки верхнего уровня) =============
# Нужен, чтобы не тянуть сюда логику ролей/меню и не создавать циклы импортов.
_MenuFor = Callable[[int], Awaitable]

_CTX: Dict[str, object] = {"menu_for": None}


def init_reveal_form(menu_for: _MenuFor) -> None:
    """
    Передай сюда асинхронную функцию menu_for(user_id) -> ReplyKeyboardMarkup.
    """
    _CTX["menu_for"] = menu_for


def _menu_for() -> _MenuFor:
    f = _CTX["menu_for"]
    # Если в проекте ещё не подключили menu_for — безопасно откатываемся к обычному main_menu()
    if f is None:
        async def _fallback(_: int):
            return main_menu()
        return _fallback  # type: ignore[return-value]
    return f  # type: ignore[return-value]


# ============= Внутренние утилиты =============

async def _require_username(m: Message) -> bool:
    """
    Проверяем, что у пользователя есть @username — он нужен для анкеты/раскрытия.
    """
    uname = m.from_user.username or ""
    if uname:
        return True
    await m.answer(
        "ℹ️ Для анкеты нужен @username в Telegram.\n"
        "Открой «Настройки → Изменить имя пользователя», установи его и вернись сюда.",
        reply_markup=await _menu_for()(m.from_user.id),
    )
    return False


# ============= Публичные шаги FSM анкеты =============

async def start_reveal_form(m: Message, state: FSMContext, *, is_refill: bool) -> None:
    """
    Точка входа в анкету (новую или перезаполнение).
    """
    await m.answer(
        "Анкета для взаимного раскрытия. Её увидят только при взаимном !reveal.\n"
        "Анкету нельзя оставить неполной — можно заполнить целиком или нажать «❌ Отмена».",
        reply_markup=cancel_kb(),
    )
    await m.answer("Как тебя зовут?", reply_markup=cancel_kb())
    await state.update_data(is_refill=is_refill)
    await state.set_state(RevealForm.name)


async def rf_name(m: Message, state: FSMContext) -> None:
    parts = (m.text or "").strip().split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""

    data = await state.get_data()
    if data.get("refill_mode"):
        await state.update_data(new_first=first, new_last=last)
    else:
        await set_user_fields(m.from_user.id, first_name=first, last_name=last)

    await m.answer("С какого ты института?", reply_markup=faculties_kb())
    await state.set_state(RevealForm.faculty)


async def rf_fac(c: CallbackQuery, state: FSMContext) -> None:
    idx = int((c.data or "fac:0").split(":")[1])
    fac = FACULTIES[idx]

    data = await state.get_data()
    if data.get("refill_mode"):
        await state.update_data(new_faculty=fac)
    else:
        await set_user_fields(c.from_user.id, faculty=fac)

    await c.message.edit_text(f"Факультет: <b>{fac}</b>")
    await c.message.answer("Сколько тебе лет?", reply_markup=cancel_kb())
    await state.set_state(RevealForm.age)
    await c.answer()


async def rf_age(m: Message, state: FSMContext) -> None:
    try:
        age = int((m.text or "").strip())
        if not (17 <= age <= 99):
            raise ValueError
    except Exception:
        await m.answer("Возраст числом 17–99, попробуй ещё раз.", reply_markup=cancel_kb())
        return

    data = await state.get_data()
    if data.get("refill_mode"):
        await state.update_data(new_age=age)
    else:
        await set_user_fields(m.from_user.id, age=age)

    u = await get_user_or_create(m.from_user.id)
    refill = bool(data.get("is_refill"))
    has_prev_about = bool(u[8])

    await m.answer(
        "Расскажи о себе (до 300 символов) или нажми «Пропустить».",
        reply_markup=about_kb(refill=refill, has_prev=has_prev_about),
    )
    await state.set_state(RevealForm.about)


async def rf_about_skip(m: Message, state: FSMContext) -> None:
    data = await state.get_data()
    uname = m.from_user.username or ""
    if data.get("refill_mode"):
        await state.update_data(new_about=None, new_username=(f"@{uname}" if uname else None))
    else:
        await set_user_fields(m.from_user.id, about=None)
        await set_user_fields(m.from_user.id, username=(f"@{uname}" if uname else None))

    u = await get_user_or_create(m.from_user.id)
    refill = bool(data.get("is_refill"))
    has_prev_photos = bool(u[10] or u[11] or u[12])

    await m.answer(
        "Пришли до 3 фото (как фото).",
        reply_markup=photos_empty_kb(refill=refill, has_prev=has_prev_photos),
    )
    await state.set_state(RevealForm.photos)


async def rf_about_keep(m: Message, state: FSMContext) -> None:
    u = await get_user(m.from_user.id)
    if not u or not u[8]:
        await m.answer(
            "Описание пустое — оставлять нечего. Напиши текст или нажми «Пропустить».",
            reply_markup=about_kb(refill=False, has_prev=False),
        )
        return

    data = await state.get_data()
    refill = bool(data.get("is_refill"))
    has_prev_photos = bool(u[10] or u[11] or u[12])

    await m.answer(
        "Пришли до 3 фото (как фото).",
        reply_markup=photos_empty_kb(refill=refill, has_prev=has_prev_photos),
    )
    await state.set_state(RevealForm.photos)


async def rf_about(m: Message, state: FSMContext) -> None:
    text_raw = (m.text or "").strip()

    if text_raw.casefold() == "пропустить":
        return await rf_about_skip(m, state)

    if text_raw and len(text_raw) > 300:
        await m.answer("Сделай описание короче (≤300 символов).")
        return

    data = await state.get_data()
    uname = m.from_user.username or ""
    if data.get("refill_mode"):
        await state.update_data(new_about=(text_raw or None), new_username=(f"@{uname}" if uname else None))
    else:
        await set_user_fields(m.from_user.id, about=(text_raw or None))
        await set_user_fields(m.from_user.id, username=(f"@{uname}" if uname else None))

    u = await get_user(m.from_user.id)
    refill = bool(data.get("is_refill"))
    has_prev_photos = bool(u[10] or u[11] or u[12])

    await m.answer(
        "Пришли до 3 фото (как фото).",
        reply_markup=photos_empty_kb(refill=refill, has_prev=has_prev_photos),
    )
    await state.set_state(RevealForm.photos)


async def rf_photos_keep(m: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("refill_mode"):
        await _commit_staged_profile(m.from_user.id, data, keep_old_photos=True)
        await state.clear()
        await m.answer(
            "Анкета сохранена (фото оставили прежние). Теперь можно жать «🔎 Найти собеседника».",
            reply_markup=await _menu_for()(m.from_user.id),
        )
        return

    await set_user_fields(m.from_user.id, reveal_ready=1)
    await state.clear()
    await m.answer(
        "Анкета сохранена (оставили прежние фото). Теперь можно жать «🔎 Найти собеседника».",
        reply_markup=await _menu_for()(m.from_user.id),
    )


async def rf_photos(m: Message, state: FSMContext) -> None:
    data = await state.get_data()
    file_id = m.photo[-1].file_id

    if data.get("refill_mode"):
        photos: List[str] = list(data.get("new_photos") or [])
        if len(photos) < 3:
            photos.append(file_id)
            await state.update_data(new_photos=photos)
            idx = len(photos)
            if idx < 3:
                await m.answer(f"Фото {idx} сохранено. Ещё?", reply_markup=photos_progress_kb())
            else:
                await m.answer("Фото 3 сохранено. Нажми «Готово».", reply_markup=photos_progress_kb())
        else:
            await m.answer("Уже есть 3 фото. Нажми «Готово».", reply_markup=photos_progress_kb())
        return

    # Первый проход заполнения — пишем прямо в БД по мере добавления
    u = await get_user_or_create(m.from_user.id)
    current = [u[10], u[11], u[12]]
    if current[0] is None:
        await set_user_fields(m.from_user.id, photo1=file_id)
        await m.answer("Фото 1 сохранено. Ещё?", reply_markup=photos_progress_kb())
    elif current[1] is None:
        await set_user_fields(m.from_user.id, photo2=file_id)
        await m.answer("Фото 2 сохранено. Ещё?", reply_markup=photos_progress_kb())
    elif current[2] is None:
        await set_user_fields(m.from_user.id, photo3=file_id)
        await m.answer("Фото 3 сохранено. Нажми «Готово».", reply_markup=photos_progress_kb())
    else:
        await m.answer("Уже есть 3 фото. Нажми «Готово».", reply_markup=photos_progress_kb())


async def rf_photos_reset(m: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("refill_mode"):
        await state.update_data(new_photos=[])
        await m.answer(
            "Все новые фото в черновике удалены. Пришли новое фото (до 3).",
            reply_markup=photos_empty_kb(refill=True, has_prev=True),
        )
        return

    await set_user_fields(m.from_user.id, photo1=None, photo2=None, photo3=None)
    await m.answer(
        "Все фото удалены. Пришли новое фото (до 3).",
        reply_markup=photos_empty_kb(refill=False, has_prev=False),
    )


async def rf_photos_done(m: Message, state: FSMContext) -> None:
    if not await _require_username(m):
        return

    data = await state.get_data()
    if data.get("refill_mode"):
        u = await get_user(m.from_user.id)
        old_have = bool(u and (u[10] or u[11] or u[12]))
        new_photos = data.get("new_photos") or []
        if not new_photos and not old_have:
            await m.answer(
                "Нужно минимум 1 фото. Пришли фото и снова нажми «Готово».",
                reply_markup=photos_empty_kb(refill=True, has_prev=False),
            )
            return

        await _commit_staged_profile(m.from_user.id, data, keep_old_photos=(len(new_photos) == 0))
        await state.clear()
        await m.answer(
            "Анкета сохранена. Теперь можно жать «🔎 Найти собеседника».",
            reply_markup=await _menu_for()(m.from_user.id),
        )
        return

    # Первый проход — проверяем, что в БД уже есть хотя бы одно фото
    u = await get_user(m.from_user.id)
    photos = [u[10], u[11], u[12]] if u else [None, None, None]
    if not any(photos):
        await m.answer(
            "Нужно минимум 1 фото. Пришли фото и снова нажми «Готово».",
            reply_markup=photos_empty_kb(refill=False, has_prev=False),
        )
        return

    await set_user_fields(m.from_user.id, reveal_ready=1)
    await state.clear()
    await m.answer(
        "Анкета сохранена. Теперь можно жать «🔎 Найти собеседника».",
        reply_markup=await _menu_for()(m.from_user.id),
    )


# ============= Коммит черновика (перезаполнение) =============

async def _commit_staged_profile(tg_id: int, staged: dict, *, keep_old_photos: bool = False) -> None:
    """
    Переносит staged-поля из FSM в users.* (и отмечает reveal_ready=1).
    Если keep_old_photos=False и есть new_photos — перезаписывает photo1..photo3.
    """
    fields: Dict[str, object] = {}

    if "new_gender" in staged:
        fields["gender"] = staged["new_gender"]
    if "new_seeking" in staged:
        fields["seeking"] = staged["new_seeking"]
    if "new_first" in staged:
        fields["first_name"] = staged["new_first"]
    if "new_last" in staged:
        fields["last_name"] = staged["new_last"]
    if "new_faculty" in staged:
        fields["faculty"] = staged["new_faculty"]
    if "new_age" in staged:
        fields["age"] = staged["new_age"]
    if "new_about" in staged:
        fields["about"] = staged["new_about"]
    if "new_username" in staged:
        fields["username"] = staged["new_username"]

    if not keep_old_photos:
        photos: List[str] = staged.get("new_photos") or []
        if photos:
            fields["photo1"] = photos[0] if len(photos) > 0 else None
            fields["photo2"] = photos[1] if len(photos) > 1 else None
            fields["photo3"] = photos[2] if len(photos) > 2 else None

    fields["reveal_ready"] = 1
    await set_user_fields(tg_id, **fields)


__all__ = [
    "init_reveal_form",
    "start_reveal_form",
    "rf_name",
    "rf_fac",
    "rf_age",
    "rf_about",
    "rf_about_skip",
    "rf_about_keep",
    "rf_photos",
    "rf_photos_keep",
    "rf_photos_reset",
    "rf_photos_done",
    "_commit_staged_profile",
]
