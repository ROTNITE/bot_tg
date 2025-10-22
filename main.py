# app/main.py
from __future__ import annotations

import asyncio
import logging
import os
import stat

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app import config as cfg
from app.db.core import db, init_db
from app.runtime import load_settings_cache
from app.middlewares.subscription import SubscriptionGuard

# Роутеры обработчиков
from app.handlers import router as user_router
from app.handlers.admin import router as admin_router

# Сервисы, которым нужен bot при старте
from app.services.feedback import init_feedback

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("mephi")


async def _resolve_channel_id(bot: Bot) -> None:
    """
    Пытаемся получить numeric id канала и сохранить его в cfg.RESOLVED_CHANNEL_ID.
    Если не вышло (бот не админ/нет доступа) — оставляем None, гейт подстрахуется.
    """
    try:
        chat = await bot.get_chat(cfg.CHANNEL_USERNAME)
        cfg.RESOLVED_CHANNEL_ID = chat.id  # например: -1001234567890
        log.info("Channel id resolved: %s", cfg.RESOLVED_CHANNEL_ID)
    except Exception as e:
        log.warning("Channel resolve failed: %r", e)
        cfg.RESOLVED_CHANNEL_ID = None


async def _fix_stale_chats() -> None:
    """
    Мягко деактивируем слишком старые активные матчи (например, старше суток).
    """
    async with db() as conn:
        await conn.execute(
            "UPDATE matches SET active=0 "
            "WHERE active=1 AND started_at < strftime('%s','now') - 86400"
        )
        await conn.commit()


async def main() -> None:
    # 1) Бот и диспетчер
    bot = Bot(cfg.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # 2) Инициализации/миграции/кеши
    await init_db()
    await load_settings_cache()
    await _fix_stale_chats()

    # 3) Логируем путь к БД и снимаем read-only, если вдруг стоит
    log.info("DB path: %s", cfg.DB_PATH)
    try:
        if os.path.exists(cfg.DB_PATH):
            os.chmod(cfg.DB_PATH, stat.S_IWRITE | stat.S_IREAD)
    except Exception:
        pass

    # 4) Резолвим id канала (если получится)
    await _resolve_channel_id(bot)

    # 5) Подключаем мидлварь «подписка на канал»
    dp.message.middleware(SubscriptionGuard())
    dp.callback_query.middleware(SubscriptionGuard())

    # 6) Регистрируем все роутеры
    dp.include_router(user_router)
    dp.include_router(admin_router)

    # 7) Инициализируем сервисы, которым нужен bot
    init_feedback(bot)

    log.info("Bot started. Polling…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
