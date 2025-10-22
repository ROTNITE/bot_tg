# app/middlewares/subscription.py
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram import Bot

from app.config import ADMIN_IDS
from app.db.core import db
from app.db.repo import get_role
from app.keyboards.common import subscription_kb


class SubscriptionGuard(BaseMiddleware):
    """
    Блокирует любые апдейты, пока пользователь не «подтвердил подписку».
    Пропускает:
      • /start
      • callback с префиксом "sub_check" (кнопка «✅ Проверить подписку»)
    Админам всегда разрешено.
    """
    def __init__(self):
        self.allowed_cmds = {"start"}
        self.allowed_callbacks_prefixes = {"sub_check"}

    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)
        user_id = user.id

        # 1) Админам — всегда можно
        if user_id in ADMIN_IDS or (await get_role(user_id)) == "admin":
            return await handler(event, data)

        # 2) Разрешаем /start, чтобы показать экран с подпиской
        if isinstance(event, Message) and (event.text or "").startswith("/"):
            cmd = (event.text or "").split()[0][1:].lower()
            if cmd in self.allowed_cmds:
                return await handler(event, data)

        # 3) Разрешаем коллбэк «Проверить подписку»
        if isinstance(event, CallbackQuery) and any(
            (event.data or "").startswith(p) for p in self.allowed_callbacks_prefixes
        ):
            return await handler(event, data)

        # 4) Проверяем одноразовую «верификацию» по флагу sub_verified
        async with db() as conn:
            cur = await conn.execute(
                "SELECT COALESCE(sub_verified,0) FROM users WHERE tg_id=?",
                (user_id,),
            )
            row = await cur.fetchone()
        sub_verified = bool(row and row[0])

        if sub_verified:
            return await handler(event, data)

        # 5) Блокируем: показываем клавиатуру подписки и выходим
        bot: Bot = data["bot"]  # Bot приходит в data из aiogram
        if isinstance(event, CallbackQuery):
            try:
                await event.answer(
                    "Подпишись на канал и нажми «✅ Проверить подписку».",
                    show_alert=True,
                )
            except Exception:
                pass
        try:
            await bot.send_message(
                user_id,
                "🔔 Перед использованием подпишись на канал и нажми «✅ Проверить подписку».",
                reply_markup=subscription_kb(),
            )
        except Exception:
            pass
        return  # не пропускаем дальше


__all__ = ["SubscriptionGuard"]
