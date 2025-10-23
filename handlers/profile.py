# app/handlers/profile.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app import config as cfg
from app.db.repo import (
    ensure_user, get_user, get_user_or_create, get_points,
    get_status, get_status_inventory, count_referrals, purchases_summary,
    set_user_fields,
)
from app.keyboards.common import (
    gender_self_kb, seeking_kb, reveal_entry_menu, cancel_kb,
    statuses_kb,
)
from app.keyboards.admin import admin_reply_menu  # ⬅️ раньше тянули admin_main_kb из common
from app.services.matching import in_queue, format_profile_text
from app.states import GState, RevealForm
from app.services.reveal_form import start_reveal_form

router = Router(name="profile")

# …и ниже по тексту: в единственном месте, где было `reply_markup=admin_main_kb()`,
# заменить на `reply_markup=admin_reply_menu()`.

@router.message(Command("profile"))
@router.message(F.text.in_({"👤 Анкета", "Анкета"}))
async def show_or_edit_reveal(m: Message, state: FSMContext):
    # Админам профиль (анкеты) не доступен — только панель
    from app.db.repo import get_role
    role = await get_role(m.from_user.id)
    if role == "admin" or m.from_user.id in cfg.ADMIN_IDS:
        await m.answer("Раздел «Анкета» недоступен для администраторов. Открой /admin.", reply_markup=admin_reply_menu())
        return

    if not await ensure_user(m.from_user.id):
        # ensure_user возвращает None — всё ок, просто гарантируем запись
        pass

    if await in_queue(m.from_user.id):
        await m.answer("Идёт поиск. Доступна только «❌ Отмена».", reply_markup=cancel_kb())
        return

    u = await get_user(m.from_user.id)
    if not u or not u[1] or not u[2]:
        await m.answer("Сначала выбери свой пол.", reply_markup=gender_self_kb())
        await state.update_data(start_form_after_prefs=True, is_refill=False)
        await state.set_state(GState.pick_gender)
        if not (m.from_user.username or ""):
            await m.answer("ℹ️ Для анкеты нужен @username. Его можно создать в настройках Telegram.")
        return

    ready = bool(u[3]) if u else False
    if not ready:
        await m.answer("Анкета не заполнена. Можно заполнить сейчас.", reply_markup=reveal_entry_menu())
        return

    txt = format_profile_text(u)
    photos = [p for p in (u[10], u[11], u[12]) if p]
    if photos:
        for p in photos[:-1]:
            await m.answer_photo(p)
        await m.answer_photo(photos[-1], caption=txt)
    else:
        await m.answer(txt)
    await m.answer("Что дальше?", reply_markup=reveal_entry_menu())


@router.message(F.text.in_({"✏️ Заполнить / Перезаполнить", "Заполнить / Перезаполнить"}))
async def fill_or_refill_btn(m: Message, state: FSMContext):
    from app.services.subscription_gate import gate_subscription
    if not await gate_subscription(m):
        return

    await ensure_user(m.from_user.id)

    if await in_queue(m.from_user.id):
        await m.answer("Идёт поиск. Доступна только «❌ Отмена».", reply_markup=cancel_kb())
        return

    u = await get_user(m.from_user.id)
    if not u or not u[1] or not u[2]:
        await m.answer("Сначала выберем твой пол.", reply_markup=gender_self_kb())
        await state.update_data(start_form_after_prefs=True, is_refill=False, refill_mode=False)
        await state.set_state(GState.pick_gender)
        if not (m.from_user.username or ""):
            await m.answer("ℹ️ Для анкеты нужен @username. Его можно создать позже в настройках Telegram.")
        return

    ready = bool(u[3])
    await state.update_data(refill_mode=ready, is_refill=ready)

    # для анкеты нужен username — проверку делает сервис форм
    await start_reveal_form(m, state, is_refill=ready)


# ====== Выбор пола/кого ищешь (GState) ======

@router.message(GState.pick_gender)
async def pick_gender_msg(m: Message, state: FSMContext):
    from app.db.repo import set_user_fields
    await ensure_user(m.from_user.id)
    text = (m.text or "").strip().casefold()
    if text not in {"я девушка", "я парень"}:
        await m.answer("Выбери одну из кнопок: «Я девушка» или «Я парень».", reply_markup=gender_self_kb())
        return
    gender = "Девушка" if text == "я девушка" else "Парень"

    data = await state.get_data()
    if data.get("refill_mode"):
        await state.update_data(new_gender=gender)
    else:
        await set_user_fields(m.from_user.id, gender=gender)

    await m.answer("Кто тебе интересен?", reply_markup=seeking_kb())
    await state.set_state(GState.pick_seeking)


@router.message(GState.pick_seeking)
async def pick_seeking_msg(m: Message, state: FSMContext):
    from app.db.repo import set_user_fields
    await ensure_user(m.from_user.id)
    text_raw = (m.text or "").strip()
    text = text_raw.capitalize()
    if text not in {"Девушки", "Парни", "Не важно"}:
        await m.answer("Выбери: «Девушки», «Парни» или «Не важно».", reply_markup=seeking_kb())
        return

    data = await state.get_data()
    refill_mode = data.get("refill_mode")
    if refill_mode:
        await state.update_data(new_seeking=text)
        await start_reveal_form(m, state, is_refill=True)
        return

    await set_user_fields(m.from_user.id, seeking=text)
    after_prefs = data.get("start_form_after_prefs", False)
    is_refill = data.get("is_refill", False)
    await state.update_data(start_form_after_prefs=False)
    await state.clear()

    if after_prefs:
        await start_reveal_form(m, state, is_refill=is_refill)
        return

    from . import menu_for
    await m.answer("Параметры сохранены.", reply_markup=(await menu_for(m.from_user.id)))


# ====== Глобальная «Отмена» ======
@router.message(F.text == "❌ Отмена")
async def global_cancel(m: Message, state: FSMContext):
    from . import menu_for
    from app.services.matching import in_queue, dequeue
    from app.states import SupportState

    # Если в чате — не трогаем (пересылка разрулит)
    from app.services.matching import active_peer
    if await active_peer(m.from_user.id):
        return

    cur_state = await state.get_state()
    data = await state.get_data()
    refill_mode = bool(data.get("refill_mode"))

    # 1) Если на форме анкеты — сбрасываем
    if cur_state in {
        RevealForm.name.state, RevealForm.faculty.state, RevealForm.age.state,
        RevealForm.about.state, RevealForm.photos.state,
    }:
        await state.clear()
        if refill_mode:
            await m.answer("Перезаполнение отменено. Старая анкета сохранена.", reply_markup=(await menu_for(m.from_user.id)))
        else:
            await set_user_fields(
                m.from_user.id, reveal_ready=0,
                first_name=None, last_name=None, faculty=None,
                age=None, about=None, photo1=None, photo2=None, photo3=None
            )
            await m.answer("Анкета отменена.", reply_markup=(await menu_for(m.from_user.id)))
        return

    # 2) Если в поддержке — выходим
    if cur_state == SupportState.waiting.state:
        await state.clear()
        await m.answer("Вы вышли из поддержки.", reply_markup=(await menu_for(m.from_user.id)))
        return

    # 3) Если стоит в очереди — отменяем поиск
    if await in_queue(m.from_user.id):
        await dequeue(m.from_user.id)
        await m.answer("Поиск отменён.", reply_markup=(await menu_for(m.from_user.id)))
        return

    # 4) Иначе просто меню
    await m.answer("Главное меню.", reply_markup=(await menu_for(m.from_user.id)))
