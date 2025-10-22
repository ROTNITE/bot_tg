"""
keyboards package public API.

Собирает экспорт из:
- common.py — основные клавиатуры (main_menu, modes_kb, subscription_kb, …)
- admin.py  — админские клавиатуры (admin_main_kb, admin_shop_kb, …)
"""

from .common import *  # noqa: F401,F403
from .admin  import *  # noqa: F401,F403

# Аккуратно формируем __all__, даже если в модулях оно не определено
from . import common as _common
from . import admin  as _admin

__all__ = []
__all__ += getattr(_common, "__all__", [])
__all__ += getattr(_admin, "__all__", [])

del _common, _admin
