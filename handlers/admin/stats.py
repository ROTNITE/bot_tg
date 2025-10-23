# app/handlers/admin/stats.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.runtime import safe_edit_message
from app.services.admin import require_admin, fetch_stats, render_stats_text
from app.keyboards.admin import admin_main_kb  # ← фикс

router = Router(name="admin_stats")


@router.callback_query(F.data == "admin:stats")
async def admin_stats(c: CallbackQuery):
    if not await require_admin(c):
        return
    agg = await fetch_stats()
    txt = render_stats_text(agg)
    await safe_edit_message(c.message, text=txt, reply_markup=admin_main_kb())
