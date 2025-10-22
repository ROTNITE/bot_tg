"""
db package public API.

Собирает экспорт из:
- core.py  — CREATE_SQL, ALTERS, db(), init_db()
- repo.py  — функции репозитория (ensure_user, set_user_fields, points/shop/refs и т.п.)
"""

from .core import *   # noqa: F401,F403
from .repo import *   # noqa: F401,F403

# Аккуратно формируем __all__, даже если в модулях оно не определено
from . import core as _core
from . import repo as _repo

__all__ = []
__all__ += getattr(_core, "__all__", [])
__all__ += getattr(_repo, "__all__", [])

del _core, _repo
