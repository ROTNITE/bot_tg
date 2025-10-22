# app/handlers/admin/__init__.py
from __future__ import annotations

from aiogram import Router

from .panel import router as panel_router
from .grant_points import router as grant_router
from .shop import router as shop_router
from .settings import router as settings_router
from .admins import router as admins_router
from .broadcast import router as broadcast_router
from .support import router as support_router
from .stats import router as stats_router

router = Router(name="admin_root")
router.include_router(panel_router)
router.include_router(grant_router)
router.include_router(shop_router)
router.include_router(settings_router)
router.include_router(admins_router)
router.include_router(broadcast_router)
router.include_router(support_router)
router.include_router(stats_router)

__all__ = ["router"]
