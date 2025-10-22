# app/config.py
from __future__ import annotations

import os
from dotenv import load_dotenv

# --- Загружаем переменные окружения (.env) ---
load_dotenv()

# === Токен и админы ===
BOT_TOKEN: str | None = os.getenv("BOT_TOKEN")
if not BOT_TOKEN or not isinstance(BOT_TOKEN, str):
    raise RuntimeError("BOT_TOKEN is missing. Put it into .env (BOT_TOKEN=...)")

# Админы: список id через запятую в .env, например ADMIN_IDS=111,222,333
ADMIN_IDS: set[int] = {
    int(x) for x in (os.getenv("ADMIN_IDS", "") or "").split(",") if x.strip()
}

# === Бонусы и тайминги (дефолты; могут переопределяться настройками в БД) ===
DAILY_BONUS_POINTS: int = 10         # ежедневный бонус
REF_BONUS_POINTS: int = 20           # бонус за реферала
INACTIVITY_SECONDS: int = 180        # авто-завершение при молчании, сек

# === Канал ===
CHANNEL_USERNAME: str = "@nektomephi"
CHANNEL_LINK: str = "https://t.me/nektomephi"

# === Пути к данным/БД ===
APPDATA_DIR: str = os.path.join(os.path.expanduser("~"), "AppData", "Local", "mephi_dating")
os.makedirs(APPDATA_DIR, exist_ok=True)
DB_PATH: str = os.path.join(APPDATA_DIR, "bot.db")

# === Тексты ===
BLOCK_TXT: str = "Сейчас идёт анонимный чат. Доступны только команды: !stop, !next, !reveal."

INTRO_TEXT: str = (
    "⚠️ Перед использованием нужно подписаться на канал: t.me/nektomephi\n\n"
    "👋 Добро пожаловать! Это анонимный чат-бот <b>исключительно для студентов МИФИ</b>.\n\n"
    "!!! В НАСТОЯЩЕЕ ВРЕМЯ РАБОТАЕТ В ТЕСТОВОМ РЕЖИМЕ !!!\n"
    "Бот <b>не является официальным проектом университета</b> — это независимая студенческая инициатива, "
    "созданная для безопасного и комфортного общения внутри сообщества.\n\n"
    "Это гибрид дайвинчика и nekto.me: ты общаешься анонимно, а при взаимном согласии "
    "можно <b>раскрыть личности</b> через команду <code>!reveal</code> (только если у обоих заполнены анкеты).\n\n"
    "💡 На данный момент доступен только режим <b>Анонимный чат</b>.\n"
    "📇 Режим <b>Просмотр анкет</b> — находится в разработке.\n\n"
    "⚙️ Как пользоваться:\n"
    "1️⃣ Выбери свой пол и кого ищешь.\n"
    "2️⃣ По желанию заполни анкету — она нужна только для взаимного раскрытия.\n"
    "3️⃣ Нажми «🔎 Найти собеседника» и начни анонимный диалог.\n\n"
    "💬 Во время чата доступны команды:\n"
    "<code>!next</code> — следующий собеседник\n"
    "<code>!stop</code> — завершить диалог\n"
    "<code>!reveal</code> — запросить взаимное раскрытие\n\n"
    "⚠️ Если кто-то молчит более 180 секунд, диалог автоматически завершается у обоих."
)

# === Справочные списки ===
FACULTIES: list[str] = [
    "ИИКС", "ФБИУКС", "ИМО", "ИФТИС",
    "ИНТЭЛ", "ИФТЭБ", "ИФИБ", "ЛАПЛАЗ",
    "ИЯФИТ",
]

# Что экспортируем «наружу»
__all__ = [
    "BOT_TOKEN", "ADMIN_IDS",
    "DAILY_BONUS_POINTS", "REF_BONUS_POINTS", "INACTIVITY_SECONDS",
    "CHANNEL_USERNAME", "CHANNEL_LINK",
    "APPDATA_DIR", "DB_PATH",
    "BLOCK_TXT", "INTRO_TEXT", "FACULTIES",
]
