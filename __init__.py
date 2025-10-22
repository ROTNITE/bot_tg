# app/__init__.py
"""
MEPHI Dating Bot — application package.

Упрощённые экспорты (ленивая подгрузка по требованию):
- user_router        — корневой роутер пользовательских хэндлеров
- admin_router       — корневой роутер админских хэндлеров
- menu_for           — функция выбора главного меню (админ/пользователь)
- SubscriptionGuard  — middleware проверки подписки на канал
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"

__all__ = [
    "user_router",
    "admin_router",
    "menu_for",
    "SubscriptionGuard",
    "__version__",
]


def __getattr__(name: str) -> Any:
    # Ленивая подгрузка, чтобы не тянуть тяжёлые зависимости раньше времени
    if name == "user_router" or name == "menu_for":
        from .handlers import router as user_router, menu_for  # type: ignore
        if name == "user_router":
            return user_router
        return menu_for
    if name == "admin_router":
        from .handlers.admin import router as admin_router  # type: ignore
        return admin_router
    if name == "SubscriptionGuard":
        from .middlewares import SubscriptionGuard  # type: ignore
        return SubscriptionGuard
    raise AttributeError(f"module 'app' has no attribute {name!r}")
