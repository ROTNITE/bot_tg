# app/db/repo.py
from __future__ import annotations

from typing import Optional, List, Tuple
import string
import secrets

from app.db.core import db
from app.config import ADMIN_IDS

# Базовые бесплатные статусы держим рядом с инвентарём
# (как в исходнике).
DEFAULT_FREE_STATUSES = ["Котик 12 кафедры", "Вайбкодер", "Странный чел"]

# -------------------------- Пользователи --------------------------

async def ensure_user(tg_id: int):
    async with db() as conn:
        await conn.execute("INSERT OR IGNORE INTO users(tg_id) VALUES(?)", (tg_id,))
        if tg_id in ADMIN_IDS:
            await conn.execute("UPDATE users SET role='admin' WHERE tg_id=?", (tg_id,))
        await conn.commit()
    # гарантируем бесплатные статусы в инвентаре
    await ensure_free_statuses(tg_id)

async def set_user_fields(tg_id: int, **kwargs):
    if not kwargs:
        return
    cols = ", ".join([f"{k}=?" for k in kwargs.keys()])
    vals = list(kwargs.values()) + [tg_id]
    async with db() as conn:
        await conn.execute(f"UPDATE users SET {cols} WHERE tg_id=?", vals)
        await conn.commit()

async def get_user(tg_id: int):
    async with db() as conn:
        cur = await conn.execute(
            """
            SELECT tg_id,gender,seeking,reveal_ready,first_name,last_name,
                   faculty,age,about,username,photo1,photo2,photo3
            FROM users WHERE tg_id=?
            """,
            (tg_id,),
        )
        return await cur.fetchone()

async def get_user_or_create(tg_id: int):
    u = await get_user(tg_id)
    if not u:
        await ensure_user(tg_id)
        u = await get_user(tg_id)
    return u

async def get_role(tg_id: int) -> str:
    async with db() as conn:
        cur = await conn.execute("SELECT role FROM users WHERE tg_id=?", (tg_id,))
        row = await cur.fetchone()
        return row[0] if row else "user"

# ---------------------------- Очки -----------------------------

async def add_points(tg_id: int, delta: int):
    async with db() as conn:
        await conn.execute(
            "UPDATE users SET points = COALESCE(points,0) + ? WHERE tg_id=?",
            (delta, tg_id),
        )
        await conn.commit()

async def get_points(tg_id: int) -> int:
    async with db() as conn:
        cur = await conn.execute(
            "SELECT COALESCE(points,0) FROM users WHERE tg_id=?", (tg_id,)
        )
        row = await cur.fetchone()
        return int(row[0] if row else 0)

# ---------------------------- Магазин -----------------------------

async def list_items():
    async with db() as conn:
        cur = await conn.execute(
            "SELECT id,name,price,type,payload FROM shop_items "
            "WHERE is_active=1 ORDER BY price ASC, id ASC"
        )
        return await cur.fetchall()

async def add_item(name: str, price: int, type_: str, payload: str):
    async with db() as conn:
        await conn.execute(
            "INSERT INTO shop_items(name,price,type,payload) VALUES(?,?,?,?)",
            (name, price, type_, payload),
        )
        await conn.commit()

async def del_item(item_id: int):
    async with db() as conn:
        await conn.execute("DELETE FROM shop_items WHERE id=?", (item_id,))
        await conn.commit()

async def get_item(item_id: int):
    async with db() as conn:
        cur = await conn.execute(
            "SELECT id,name,price,type,payload FROM shop_items WHERE id=?", (item_id,)
        )
        return await cur.fetchone()

# ---------------------- Статусы / инвентарь ----------------------

async def add_status_to_inventory(user_id: int, title: str):
    async with db() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO user_statuses(user_id, title) VALUES(?,?)",
            (user_id, title),
        )
        await conn.commit()

async def get_status_inventory(user_id: int) -> list[str]:
    async with db() as conn:
        cur = await conn.execute(
            "SELECT title FROM user_statuses WHERE user_id=? ORDER BY title ASC",
            (user_id,),
        )
        return [r[0] for r in await cur.fetchall()]

async def ensure_free_statuses(user_id: int):
    inv = await get_status_inventory(user_id)
    missing = [s for s in DEFAULT_FREE_STATUSES if s not in inv]
    if not missing:
        return
    async with db() as conn:
        await conn.executemany(
            "INSERT OR IGNORE INTO user_statuses(user_id, title) VALUES(?,?)",
            [(user_id, s) for s in missing],
        )
        await conn.commit()

async def set_status(tg_id: int, title: Optional[str]):
    async with db() as conn:
        await conn.execute("UPDATE users SET status_title=? WHERE tg_id=?", (title, tg_id))
        await conn.commit()

async def get_status(tg_id: int) -> Optional[str]:
    async with db() as conn:
        cur = await conn.execute("SELECT status_title FROM users WHERE tg_id=?", (tg_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else None

# -------------------------- Рефералы -----------------------------

async def register_referral(inviter: int, invited: int) -> bool:
    if inviter == invited or inviter is None:
        return False
    async with db() as conn:
        cur = await conn.execute("SELECT 1 FROM referrals WHERE invited=?", (invited,))
        if await cur.fetchone():
            return False
        await conn.execute(
            "INSERT INTO referrals(inviter, invited) VALUES(?,?)", (inviter, invited)
        )
        await conn.commit()
    return True

async def count_referrals(inviter: int) -> int:
    async with db() as conn:
        # мягкая инициализация/миграции (как было в исходнике)
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS referrals("
            "inviter INTEGER, invited INTEGER PRIMARY KEY, "
            "ts INTEGER DEFAULT (strftime('%s','now')))"
        )
        cur = await conn.execute("PRAGMA table_info(referrals)")
        cols = {r[1] for r in await cur.fetchall()}
        if "inviter" not in cols:
            await conn.execute("ALTER TABLE referrals ADD COLUMN inviter INTEGER")
        cur = await conn.execute("SELECT COUNT(*) FROM referrals WHERE inviter=?", (inviter,))
        row = await cur.fetchone()
        return int(row[0] if row else 0)

# --- Непрозрачные коды для рефералок ---

ALPH = string.ascii_letters + string.digits

async def get_or_create_ref_code(inviter: int) -> str:
    async with db() as conn:
        cur = await conn.execute("SELECT code FROM ref_codes WHERE inviter=?", (inviter,))
        row = await cur.fetchone()
        if row:
            return row[0]
        code = "".join(secrets.choice(ALPH) for _ in range(12))
        await conn.execute("INSERT INTO ref_codes(code,inviter) VALUES(?,?)", (code, inviter))
        await conn.commit()
        return code

async def inviter_by_code(code: str) -> Optional[int]:
    async with db() as conn:
        cur = await conn.execute("SELECT inviter FROM ref_codes WHERE code=?", (code,))
        row = await cur.fetchone()
        return int(row[0]) if row else None

# ------------------------ Сводки / отчёты ------------------------

async def purchases_summary(user_id: int) -> tuple[int, list[str]]:
    """Возвращает (сумма_по_покупкам, названия_последних_5_покупок)"""
    async with db() as conn:
        cur = await conn.execute(
            """
            SELECT COALESCE(SUM(si.price),0)
            FROM purchases p JOIN shop_items si ON si.id=p.item_id
            WHERE p.user_id=?
            """,
            (user_id,),
        )
        total = int((await cur.fetchone())[0])
        cur = await conn.execute(
            """
            SELECT si.name
            FROM purchases p JOIN shop_items si ON si.id=p.item_id
            WHERE p.user_id=?
            ORDER BY p.ts DESC
            LIMIT 5
            """,
            (user_id,),
        )
        names = [r[0] for r in await cur.fetchall()]
    return total, names


__all__ = [
    # users/roles/points
    "ensure_user", "set_user_fields", "get_user", "get_user_or_create",
    "get_role", "add_points", "get_points",
    # shop
    "list_items", "add_item", "del_item", "get_item",
    # statuses/inventory
    "DEFAULT_FREE_STATUSES", "add_status_to_inventory", "get_status_inventory",
    "ensure_free_statuses", "set_status", "get_status",
    # referrals
    "register_referral", "count_referrals", "get_or_create_ref_code", "inviter_by_code",
    # reports
    "purchases_summary",
]
