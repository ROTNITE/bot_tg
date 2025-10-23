# app/handlers/admin/shop.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db.repo import list_items, add_item, del_item
from app.keyboards.admin import admin_shop_kb
from app.runtime import safe_edit_message
from app.services.admin import require_admin
from app.states import AdminAddItem, AdminShopDel

router = Router(name="admin_shop")


@router.callback_query(F.data == "admin:shop")
async def admin_shop(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    await safe_edit_message(c.message, text="🛍 Магазин", reply_markup=admin_shop_kb())


@router.callback_query(F.data == "admin:shop:list")
async def admin_shop_list(c: CallbackQuery):
    if not await require_admin(c):
        return
    items = await list_items()
    txt = "📦 Товары:\n" + ("\n".join([f"{i[0]}. {i[1]} — {i[2]}💰 [{i[3]}] {i[4] or ''}" for i in items]) or "пусто")
    await safe_edit_message(c.message, text=txt, reply_markup=admin_shop_kb())


@router.callback_query(F.data == "admin:shop:add")
async def admin_shop_add(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    await state.set_state(AdminAddItem.wait_name)
    await c.message.edit_text("🧩 Шаг 1/4: Введи название товара\n\nНапример: <code>Самый Скромный</code>")


@router.message(AdminAddItem.wait_name)
async def admin_shop_add_name(m: Message, state: FSMContext):
    await state.update_data(name=(m.text or "").strip())
    await state.set_state(AdminAddItem.wait_price)
    await m.answer("🧩 Шаг 2/4: Цена (целое число)\n\nНапример: <code>50</code>")


@router.message(AdminAddItem.wait_price)
async def admin_shop_add_price(m: Message, state: FSMContext):
    try:
        price = int((m.text or "").strip())
        if price < 0:
            raise ValueError
    except Exception:
        return await m.answer("Некорректное число. Попробуй ещё раз.")
    await state.update_data(price=price)
    await state.set_state(AdminAddItem.wait_type)
    await m.answer("🧩 Шаг 3/4: Тип — напиши <code>status</code> или <code>privilege</code>")


@router.message(AdminAddItem.wait_type)
async def admin_shop_add_type(m: Message, state: FSMContext):
    t = (m.text or "").strip().lower()
    if t not in {"status", "privilege"}:
        return await m.answer("Тип должен быть <code>status</code> или <code>privilege</code>.")
    await state.update_data(type=t)
    await state.set_state(AdminAddItem.wait_payload)
    await m.answer("🧩 Шаг 4/4: Payload — текст статуса/описание привилегии")


@router.message(AdminAddItem.wait_payload)
async def admin_shop_add_payload(m: Message, state: FSMContext):
    d = await state.get_data()
    await add_item(d["name"], d["price"], d["type"], (m.text or "").strip())
    await state.clear()
    await m.answer("✅ Товар добавлен.", reply_markup=admin_shop_kb())


@router.callback_query(F.data == "admin:shop:del")
async def admin_shop_del(c: CallbackQuery, state: FSMContext):
    if not await require_admin(c):
        return
    await state.set_state(AdminShopDel.wait_id)
    await c.message.edit_text("Отправь ID товара, который удалить (см. «📦 Список»).")


@router.message(AdminShopDel.wait_id)
async def admin_shop_del_id(m: Message, state: FSMContext):
    try:
        await del_item(int((m.text or "").strip()))
        await m.answer("🗑 Удалено.", reply_markup=admin_shop_kb())
    except Exception:
        await m.answer("Не получилось удалить. Проверь ID.", reply_markup=admin_shop_kb())
    await state.clear()
