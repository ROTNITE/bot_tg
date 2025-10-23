# app/handlers/reveal_form.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import RevealForm
# Импортируем сервис с логикой
from app.services import reveal_form as RF

router = Router(name="reveal_form")

# ---- Текстовые стадии ----

@router.message(RevealForm.name)
async def rf__name(m: Message, state: FSMContext):
    await RF.rf_name(m, state)

@router.message(RevealForm.faculty)
async def rf__faculty(m: Message, state: FSMContext):
    await RF.rf_fac(m, state)

@router.message(RevealForm.age)
async def rf__age(m: Message, state: FSMContext):
    await RF.rf_age(m, state)

@router.message(RevealForm.about)
async def rf__about(m: Message, state: FSMContext):
    await RF.rf_about(m, state)

@router.message(RevealForm.photos)
async def rf__photos(m: Message, state: FSMContext):
    # в этой стадии пользователь шлёт фото/медиа, RF.rf_photos сам разберёт тип
    await RF.rf_photos(m, state)

# ---- Кнопки «пропустить/оставить/готово» (если используются inline-клавиатуры) ----

@router.callback_query(F.data == "rf:about:skip")
async def rf__about_skip(c: CallbackQuery, state: FSMContext):
    await RF.rf_about_skip(c, state)

@router.callback_query(F.data == "rf:about:keep")
async def rf__about_keep(c: CallbackQuery, state: FSMContext):
    await RF.rf_about_keep(c, state)

@router.callback_query(F.data == "rf:photos:keep")
async def rf__photos_keep(c: CallbackQuery, state: FSMContext):
    await RF.rf_photos_keep(c, state)

@router.callback_query(F.data == "rf:photos:done")
async def rf__photos_done(c: CallbackQuery, state: FSMContext):
    await RF.rf_photos_done(c, state)
