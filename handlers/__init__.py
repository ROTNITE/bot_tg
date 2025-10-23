# app/handlers/__init__.py
from __future__ import annotations

from aiogram import Router
from aiogram.types import ReplyKeyboardMarkup

from app import config as cfg
from app.db.repo import get_role
from app.keyboards.common import main_menu
from app.keyboards.admin import admin_reply_menu


async def menu_for(user_id: int) -> ReplyKeyboardMarkup:
    """
    Унифицированный выбор клавиатуры: если админ — показываем админ-кнопку,
    иначе — обычное главное меню.
    """
    role = await get_role(user_id)
    if role == "admin" or user_id in cfg.ADMIN_IDS:
        return admin_reply_menu()
    return main_menu()


# ↓ только после определения menu_for импортируем роутеры,
#   чтобы market.py мог "from app.handlers import menu_for"
from .start_help import router as start_help_router
from .modes_menu import router as modes_router
from .profile import router as profile_router
from .chat import router as chat_router
from .support import router as support_router
from .complaints import router as complaints_router
from .market import router as market_router
from .referrals import router as referrals_router
from .fallback import router as fallback_router

router = Router(name="user_root")
router.include_router(start_help_router)
router.include_router(modes_router)
router.include_router(profile_router)
router.include_router(chat_router)
router.include_router(support_router)
router.include_router(complaints_router)
router.include_router(market_router)
router.include_router(referrals_router)
router.include_router(fallback_router)

__all__ = ["router", "menu_for"]
