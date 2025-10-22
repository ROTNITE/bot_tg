# app/middlewares/__init__.py
"""
Public API for app.middlewares.

Exports:
- SubscriptionGuard — middleware that blocks updates until channel subscription is verified.
"""

from .subscription import SubscriptionGuard

__all__ = ["SubscriptionGuard"]
