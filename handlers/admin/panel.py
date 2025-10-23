# app/handlers/admin/panel.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.db.repo import ensure_user
from app.keyboards.admin import admin_main_kb
from app.services.admin import require_admin
from app.services.matching import deny_actions_during_chat

router = Router(name="admin_panel")

@router.message(Command("admin"))
@router.message(F.text.in_({"🛠 Админ", "🛠️ Админ", "Админ"}))
async def admin_panel(m: Message, state: FSMContext):
    if await deny_actions_during_chat(m):
        return
    await ensure_user(m.from_user.id)
    if not await require_admin(m):
        return
    await state.clear()
    await m.answer("🛠 Панель администратора", reply_markup=admin_main_kb())

@router.callback_query(F.data == "admin:home")
async def admin_home(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    await state.clear()
    await c.message.edit_text("🛠 Панель администратора", reply_markup=admin_main_kb())


@router.message(F.text == "🛠 Админ")
async def open_admin_from_button(m: Message, state: FSMContext):
    return await admin_panel(m, state)
