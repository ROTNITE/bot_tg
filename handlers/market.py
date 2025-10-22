# app/handlers/market.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.db.core import db
from app.db.repo import (
    list_items, get_item, get_points, add_points,
    add_status_to_inventory, set_status,
)
from app.keyboards.common import shop_kb
from app.handlers import menu_for
from app.db.repo import get_role

router = Router(name="market")


@router.message(Command("market"))
async def cmd_market(m: Message):
    if await get_role(m.from_user.id) == "admin":
        return await m.answer("Ты админ и не можешь покупать. Используй /admin.", reply_markup=(await menu_for(m.from_user.id)))
    items = await list_items()
    if not items:
        return await m.answer("🛍 Магазин пока пуст.", reply_markup=(await menu_for(m.from_user.id)))
    await m.answer("🛍 Магазин статусов и привилегий. Выбери товар:", reply_markup=shop_kb(items))


@router.callback_query(F.data.startswith("shop_buy:"))
async def shop_buy(c: CallbackQuery):
    if await get_role(c.from_user.id) == "admin":
        await c.answer("Админ не может покупать товары.", show_alert=True)
        return

    item_id = int(c.data.split(":")[1])
    item = await get_item(item_id)
    if not item:
        await c.answer("Товар уже недоступен.", show_alert=True)
        return

    _id, name, price, type_, payload = item
    pts = await get_points(c.from_user.id)
    if pts < price:
        await c.answer(f"Не хватает очков. Нужно {price}, у тебя {pts}.", show_alert=True)
        return

    await add_points(c.from_user.id, -price)
    applied_msg = ""
    if type_ == "status":
        # Кладём в инвентарь и сразу экипируем
        await add_status_to_inventory(c.from_user.id, payload)
        await set_status(c.from_user.id, payload)
        applied_msg = f"Теперь твой статус: «{payload}». (Добавлен в инвентарь)"
    elif type_ == "privilege":
        applied_msg = f"Привилегия активирована: {payload}"

    async with db() as conn:
        await conn.execute("INSERT INTO purchases(user_id,item_id) VALUES(?,?)", (c.from_user.id, _id))
        await conn.commit()

    new_pts = await get_points(c.from_user.id)
    try:
        await c.message.edit_text(
            f"✅ Покупка «{name}» за {price}💰 успешна!\n{applied_msg}\nБаланс: {new_pts}.", reply_markup=None
        )
    except Exception:
        pass
    await c.answer("Готово!")
