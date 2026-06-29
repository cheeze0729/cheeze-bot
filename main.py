"""
Telegram-бот для онлайн-магазина цифровых товаров и доната
----------------------------------------------------------
Стек: Python 3.11+, aiogram 3, aiosqlite (SQLite-хранилище)

УСТАНОВКА:
    pip install aiogram==3.13.1 aiosqlite

ЗАПУСК:
    python bot.py

Все настройки и тексты находятся в блоке CONFIG ниже —
смело редактируйте их под себя.
"""

import asyncio
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

MSK_TZ = timezone(timedelta(hours=3))


def _fmt_msk(iso_str: str) -> str:
    """Преобразует ISO-время (UTC) в строку в МСК."""
    if not iso_str:
        return ""
    s = iso_str.replace("T", " ")
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_msk = dt.astimezone(MSK_TZ)
        return dt_msk.strftime("%Y-%m-%d %H:%M МСК")
    except Exception:
        return s
from html import escape

import os

import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# =====================================================================
# CONFIG  --  ОТРЕДАКТИРУЙТЕ ЭТИ ЗНАЧЕНИЯ
# =====================================================================

# --- Основное ---
BOT_TOKEN = os.environ["BOT_TOKEN"]

# Telegram ID модератора (узнайте у @userinfobot).
# Сюда будут приходить уведомления о новых заказах и сообщения от клиентов.
# Если оставить 0 — пересылка будет отключена.
MODERATOR_CHAT_ID = 1727614596

# Юзернеймы (везде, где упоминается @username)
SUPPORT_USERNAME = "@cheeze0729"  # Поддержка
OTHER_APPS_USERNAME = "@cheeze0729"  # Донат в других приложениях
BRAWL_PROMO_USERNAME = "@cheeze0729"  # Акции по Brawl Stars

# Стартовое изображение (URL или file_id Telegram).
# Можно заменить на свою картинку.
WELCOME_IMAGE_URL = "https://i.postimg.cc/SxHKrmbd/IMG-3992.png"

# Реквизиты для пополнения баланса (карта/СБП).
# Эти реквизиты будут показаны пользователю после ввода суммы.
# Поддерживается HTML-разметка: <code>...</code> делает текст кликабельным
# для копирования в Telegram.
CARD_DETAILS = (
    "💳 <b>Карта Т-Банк:</b>\n"
    "<code>2200 7017 3823 7798</code>\n\n"
    "👤 <b>Получатель:</b> Марсель С.\n\n"
    "ℹ️ При невозможности оплаты по карте обратитесь в поддержку для оплаты по СБП."
)

# Ссылка на отзывы (канал, чат или страница с отзывами клиентов)
REVIEWS_URL = "https://t.me/cheezereviews"
# Username канала для публикации отзывов (бот должен быть администратором канала)
REVIEWS_CHANNEL = "@cheezereviews"

# =====================================================================
# КАРТИНКИ ДЛЯ КАЖДОГО РАЗДЕЛА
# =====================================================================
# Чтобы добавить картинку — впишите ссылку (URL) или Telegram file_id
# вместо None. Картинка будет показана над текстом раздела.
# Если оставить None — раздел будет без картинки.
# Подсказка: длина текста с картинкой не должна превышать 1024 символа.

SECTION_IMAGES: dict[str, str | None] = {
    "welcome": WELCOME_IMAGE_URL,  # /start, главное меню
    "shop": "images/shop.png",  # «Купить донат» (локальный файл)
    "roblox_instant": "https://i.ibb.co/0R5v4qFd/A48-CAFDF-8-C92-4-CA1-9-C68-E462-DD8-A34-D9.png",  # Roblox моментально
    "roblox_gamepass": "https://i.ibb.co/0R5v4qFd/A48-CAFDF-8-C92-4-CA1-9-C68-E462-DD8-A34-D9.png",  # Roblox геймпассом
    "brawl": "https://i.ibb.co/xqp3GzrQ/F42684-C7-1395-43-EF-A49-B-E817-B7-E73551.png",  # Brawl Stars
    "tgstars": "https://i.ibb.co/N2JJ5SHb/42-E499-C6-7-FE1-4-E03-94-A4-47-E6-A705-FEAA.png",  # Telegram Stars
    "other": None,  # Другие приложения
    "profile": "https://i.ibb.co/5x2bNNJK/56-D6214-E-F8-F0-4-BFE-AF06-EBA573966-CD0.png",  # Профиль
    "orders": "https://i.ibb.co/Gvpsmbnq/886-D71-D9-F7-B0-4-A9-E-A540-180-FFB450321.png",  # Мои заказы
    "topup": None,  # Пополнение баланса
    "support": "https://i.ibb.co/pvcyff13/13-B5-AB68-5-FDA-4598-B1-D7-12-F98-A0188-D7.png",  # Поддержка
    "info": "https://i.ibb.co/n8gT4YRD/4-AF7623-F-D966-4130-9-D7-F-592-ED9-C22935.png",  # Информация о магазине
    "guarantee": None,  # Гарантия
    # Карточки товаров (общие для всех товаров категории):
    "card_roblox_instant": None,
    "card_brawl": None,
}

# Курсы
ROBUX_GAMEPASS_RATE = 0.65  # 1 робукс = 0.65 ₽
ROBUX_GAMEPASS_PASS_PRICE_RATE = 0.7  # Цена геймпасса в Roblox
TG_STARS_RATE = 1.3  # 1 звезда = 1.3 ₽

# Минимальная сумма пополнения
MIN_TOPUP = 10  # рублей

# Минимальное количество Telegram Stars
MIN_TG_STARS = 50

# --- Тексты ---
WELCOME_TEXT = (
    "<b>Добро пожаловать в магазин цифровых товаров.</b>\n\n"
    "Здесь вы можете быстро и удобно купить донат, "
    "пополнить баланс и связаться с поддержкой."
)

INFO_TEXT = (
    "<b>О магазине</b>\n\n"
    "Мы предлагаем удобную покупку цифровых товаров и доната "
    "по выгодным ценам.\n\n"
    "<b>Почему выбирают нас:</b>\n"
    "— Быстрое оформление заказов\n"
    "— Удобное пополнение баланса\n"
    "— Поддержка клиентов\n"
    "— Широкий выбор услуг\n\n"
    "<b>Время работы поддержки:</b>\n"
    "Ежедневно: 10:00 – 22:00 МСК\n\n"
    f"По всем вопросам: {SUPPORT_USERNAME}"
)

SUPPORT_TEXT = (
    "<b>Поддержка</b>\n\n"
    "Если у вас возникли вопросы, напишите в поддержку: "
    f"{SUPPORT_USERNAME}"
)

GUARANTEE_TEXT = (
    "<b>🛡️ Наша гарантия</b>\n\n"
    "Почему нам можно доверять:\n"
    "— Работаем официально и долго\n"
    "— Тысячи довольных клиентов\n"
    "— Деньги возвращаются, если заказ не выполнен\n"
    "— Поддержка отвечает каждый день\n"
    "— Прозрачные цены без скрытых комиссий\n\n"
    "Все отзывы реальных покупателей доступны по кнопке ниже."
)

# =====================================================================
# Подсказки по данным для входа (для каждой категории — своя)
# =====================================================================
# Если значение задано — после оплаты бот попросит покупателя
# отправить эти данные сообщением, сохранит их к заказу и перешлёт
# модератору. Если оставить None — данные не запрашиваются.

LOGIN_HINTS = {
    "roblox_instant": "Отправьте логин (никнейм) в Roblox.",
    "roblox_gamepass": "Отправьте ссылку на созданный геймпасс в Roblox.",
    "brawl": "Отправьте почту, привязанную к вашему аккаунту и ожидайте код.",
    "tgstars": "Отправьте @username аккаунта Telegram для зачисления звёзд.",
}

# =====================================================================
# КАТАЛОГ ТОВАРОВ
# =====================================================================
# Чтобы добавить товар — просто добавьте новую запись в нужный список.
# Структура: (ключ, "Название для кнопки/карточки", цена ₽, "способ выдачи")

ROBUX_INSTANT = [
    ("rb_40", "40 робуксов", 59, "моментально"),
    ("rb_80", "80 робуксов", 99, "моментально"),
    ("rb_200", "200 робуксов", 249, "моментально"),
    ("rb_400", "400 робуксов", 449, "моментально"),
    ("rb_500", "500 робуксов", 499, "моментально"),
    ("rb_1000", "1000 робуксов", 879, "моментально"),
    ("rb_1700", "1700 робуксов", 1499, "моментально"),
    ("rb_2000", "2000 робуксов", 1699, "моментально"),
    ("rb_3600", "3600 робуксов", 3099, "моментально"),
]

BRAWL_PRODUCTS = [
    ("bs_pass", "Brawl Pass", 849, "по согласованию через Telegram"),
    ("bs_pass_plus", "Brawl Pass Plus", 1149, "по согласованию через Telegram"),
    ("bs_pro", "Pro Pass", 2099, "по согласованию через Telegram"),
]

# =====================================================================
# Инициализация бота
# =====================================================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class BlacklistMiddleware(BaseMiddleware):
    """Блокирует все действия пользователей из чёрного списка.
    Модератор всегда пропускается. Покупателю показывается сообщение
    с кнопкой связи с поддержкой.
    """

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)
        if MODERATOR_CHAT_ID and user.id == MODERATOR_CHAT_ID:
            return await handler(event, data)
        try:
            blocked = await db_is_blacklisted(user.id)
        except Exception:
            blocked = False
        if not blocked:
            return await handler(event, data)
        text = (
            "🚫 <b>Вы в чёрном списке.</b>\n\n"
            "Доступ к боту ограничен. Если считаете, что это ошибка — "
            "свяжитесь с поддержкой."
        )
        kb = kb_support()
        try:
            from aiogram.types import CallbackQuery as _CQ, Message as _MSG

            if isinstance(event, _CQ):
                await event.answer("Вы в чёрном списке", show_alert=True)
                try:
                    await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    pass
            elif isinstance(event, _MSG):
                await event.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"BlacklistMiddleware error: {e}")
        return None


dp.message.middleware(BlacklistMiddleware())
dp.callback_query.middleware(BlacklistMiddleware())

# База данных хранится ВНЕ git-репозитория — данные не сбрасываются при правках кода.
DB_PATH = "/home/runner/shop_data/shop.db"


# =====================================================================
# База данных
# =====================================================================


async def db_init() -> None:
    """Создаёт таблицы, если их ещё нет. Папка для БД создаётся автоматически."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_id          INTEGER PRIMARY KEY,
                username       TEXT,
                first_name     TEXT,
                balance        INTEGER NOT NULL DEFAULT 0,
                is_blacklisted INTEGER NOT NULL DEFAULT 0,
                created_at     TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id      INTEGER NOT NULL,
                title      TEXT NOT NULL,
                price      INTEGER NOT NULL,
                status     TEXT NOT NULL,
                category   TEXT,
                contact    TEXT,
                login_data TEXT,
                login_code TEXT,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id      INTEGER NOT NULL,
                amount     INTEGER NOT NULL,
                kind       TEXT NOT NULL,
                reason     TEXT,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id      INTEGER NOT NULL UNIQUE,
                tg_id         INTEGER NOT NULL,
                photo_file_id TEXT,
                comment       TEXT,
                created_at    TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                code          TEXT    UNIQUE NOT NULL COLLATE NOCASE,
                game          TEXT    NOT NULL,
                product_title TEXT    NOT NULL,
                promo_price   INTEGER NOT NULL,
                starts_at     TEXT,
                expires_at    TEXT,
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT    NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_promos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id      INTEGER NOT NULL,
                promo_id   INTEGER NOT NULL,
                claimed_at TEXT    NOT NULL,
                used_at    TEXT,
                UNIQUE(tg_id, promo_id)
            )
        """)
        cur = await db.execute("PRAGMA table_info(orders)")
        cols = [r[1] for r in await cur.fetchall()]
        if "login_data" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN login_data TEXT")
        if "login_code" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN login_code TEXT")
        if "category" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN category TEXT")

        cur = await db.execute("PRAGMA table_info(users)")
        ucols = [r[1] for r in await cur.fetchall()]
        if "is_blacklisted" not in ucols:
            await db.execute(
                "ALTER TABLE users ADD COLUMN is_blacklisted INTEGER NOT NULL DEFAULT 0"
            )
        await db.commit()


async def db_get_or_create_user(user) -> dict:
    """Возвращает запись пользователя, создавая её при первом обращении."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (user.id,))
        row = await cur.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO users (tg_id, username, first_name, balance, created_at)"
                " VALUES (?, ?, ?, 0, ?)",
                (
                    user.id,
                    user.username,
                    user.first_name,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (user.id,))
            row = await cur.fetchone()
        else:
            await db.execute(
                "UPDATE users SET username = ?, first_name = ? WHERE tg_id = ?",
                (user.username, user.first_name, user.id),
            )
            await db.commit()
        return dict(row)


async def db_get_balance(tg_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def db_add_balance(tg_id: int, amount: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE tg_id = ?",
            (amount, tg_id),
        )
        await db.commit()
    return await db_get_balance(tg_id)


async def db_try_charge(tg_id: int, amount: int) -> bool:
    """Списывает amount с баланса, если денег достаточно. Возвращает True/False."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        if not row or row[0] < amount:
            return False
        await db.execute(
            "UPDATE users SET balance = balance - ? WHERE tg_id = ?",
            (amount, tg_id),
        )
        await db.commit()
        return True


async def db_create_order(
    tg_id: int,
    title: str,
    price: int,
    status: str = "Оплачен",
    category: str | None = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (tg_id, title, price, status, category, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                tg_id,
                title,
                price,
                status,
                category,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        await db.commit()
        return cur.lastrowid


async def db_set_order_status(order_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (status, order_id),
        )
        await db.commit()


async def db_get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_set_order_contact(order_id: int, contact: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET contact = ? WHERE id = ?",
            (contact, order_id),
        )
        await db.commit()


async def db_set_order_login(order_id: int, login_data: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET login_data = ? WHERE id = ?",
            (login_data, order_id),
        )
        await db.commit()


async def db_set_order_login_code(order_id: int, code: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET login_code = ? WHERE id = ?",
            (code, order_id),
        )
        await db.commit()


async def db_add_review(
    order_id: int, tg_id: int, photo_file_id: str | None, comment: str
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT OR REPLACE INTO reviews "
            "(order_id, tg_id, photo_file_id, comment, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                order_id,
                tg_id,
                photo_file_id,
                comment,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        await db.commit()
        return cur.lastrowid


async def db_has_review(order_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM reviews WHERE order_id = ?", (order_id,)
        )
        return await cur.fetchone() is not None


async def db_add_transaction(
    tg_id: int, amount: int, kind: str, reason: str | None = None
) -> None:
    """Записывает движение по балансу. amount: +начисление / -списание."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO transactions (tg_id, amount, kind, reason, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                tg_id,
                amount,
                kind,
                reason,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        await db.commit()


async def db_get_transactions(tg_id: int, limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM transactions WHERE tg_id = ? ORDER BY id DESC LIMIT ?",
            (tg_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def db_set_balance(tg_id: int, value: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = ? WHERE tg_id = ?",
            (value, tg_id),
        )
        await db.commit()
    return await db_get_balance(tg_id)


async def db_set_blacklist(tg_id: int, value: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_blacklisted = ? WHERE tg_id = ?",
            (1 if value else 0, tg_id),
        )
        await db.commit()


async def db_is_blacklisted(tg_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT is_blacklisted FROM users WHERE tg_id = ?", (tg_id,)
        )
        row = await cur.fetchone()
        return bool(row[0]) if row else False


async def db_find_user(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_get_orders(tg_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders WHERE tg_id = ? ORDER BY id DESC LIMIT ?",
            (tg_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def db_orders_count(tg_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM orders WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def db_users_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def db_list_users(limit: int, offset: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT tg_id, username, first_name, balance, is_blacklisted "
            "FROM users ORDER BY rowid DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def db_create_promo(
    code: str,
    game: str,
    product_title: str,
    promo_price: int,
    starts_at: str | None = None,
    expires_at: str | None = None,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO promo_codes (code, game, product_title, promo_price, starts_at, expires_at, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (code.upper(), game, product_title, promo_price, starts_at, expires_at, now),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def db_get_promo_by_code(code: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM promo_codes WHERE code = ? COLLATE NOCASE",
            (code.strip(),),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_get_promo_by_id(promo_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM promo_codes WHERE id = ?", (promo_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_list_promos() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM promo_codes ORDER BY id DESC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def db_delete_promo(promo_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promo_codes WHERE id = ?", (promo_id,))
        await db.execute("DELETE FROM user_promos WHERE promo_id = ?", (promo_id,))
        await db.commit()


async def db_toggle_promo(promo_id: int, is_active: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE promo_codes SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, promo_id),
        )
        await db.commit()


async def db_claim_promo(tg_id: int, promo_id: int) -> bool:
    """Добавляет промокод в список пользователя. False — уже есть."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO user_promos (tg_id, promo_id, claimed_at) VALUES (?, ?, ?)",
                (tg_id, promo_id, now),
            )
            await db.commit()
            return True
        except Exception:
            return False


async def db_use_promo(tg_id: int, promo_id: int) -> bool:
    """Помечает промокод как использованный. False — уже использован."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT used_at FROM user_promos WHERE tg_id = ? AND promo_id = ?",
            (tg_id, promo_id),
        )
        row = await cur.fetchone()
        if not row or row[0] is not None:
            return False
        await db.execute(
            "UPDATE user_promos SET used_at = ? WHERE tg_id = ? AND promo_id = ?",
            (now, tg_id, promo_id),
        )
        await db.commit()
        return True


async def db_get_user_promos(tg_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT up.id, up.tg_id, up.promo_id, up.claimed_at, up.used_at, "
            "pc.code, pc.game, pc.product_title, pc.promo_price, "
            "pc.expires_at, pc.starts_at, pc.is_active "
            "FROM user_promos up "
            "JOIN promo_codes pc ON pc.id = up.promo_id "
            "WHERE up.tg_id = ? ORDER BY up.id DESC",
            (tg_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def db_promo_usage_count(promo_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM user_promos WHERE promo_id = ? AND used_at IS NOT NULL",
            (promo_id,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def db_get_all_user_ids() -> list[int]:
    """Возвращает tg_id всех не заблокированных пользователей (для рассылки)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT tg_id FROM users WHERE is_blacklisted = 0"
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]


# =====================================================================
# Состояния FSM (для ввода чисел и почты)
# =====================================================================


class ShopStates(StatesGroup):
    waiting_topup_amount = State()
    waiting_topup_confirm = State()
    waiting_robux_amount = State()
    waiting_stars_amount = State()
    waiting_email = State()
    waiting_login_data = State()
    waiting_login_code = State()
    waiting_promo_input = State()
    waiting_review_photo = State()
    waiting_review_text = State()


class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_credit_amount = State()
    waiting_credit_reason = State()
    waiting_reset_reason = State()
    waiting_block_reason = State()
    waiting_unblock_reason = State()
    waiting_gp_price = State()
    waiting_mod_reply = State()   # ответ покупателю из чата модератора
    waiting_broadcast = State()  # рассылка всем пользователям


class PromoStates(StatesGroup):
    waiting_code_input = State()
    waiting_product = State()
    waiting_price = State()
    waiting_dates = State()


# =====================================================================
# Клавиатуры
# =====================================================================


def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Купить донат", callback_data="shop")],
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                InlineKeyboardButton(text="📦 Мои заказы", callback_data="orders"),
            ],
            [
                InlineKeyboardButton(text="🛡️ Гарантия", callback_data="guarantee"),
                InlineKeyboardButton(text="📖 О магазине", callback_data="info"),
            ],
            [
                InlineKeyboardButton(text="⭐ Отзывы", url=REVIEWS_URL),
                InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"),
            ],
        ]
    )


def kb_shop() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟦 Roblox, моментально", callback_data="cat:roblox_instant"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎮 Roblox, геймпассом (5 дней)",
                    callback_data="cat:roblox_gamepass",
                )
            ],
            [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="cat:brawl")],
            [
                InlineKeyboardButton(
                    text="✨ Telegram Stars", callback_data="cat:tgstars"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 Другие приложения", callback_data="cat:other"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main")],
        ]
    )


def kb_back_main(back_cb: str = "shop") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb),
                InlineKeyboardButton(text="🏠 В меню", callback_data="main"),
            ],
        ]
    )


def kb_product_list(
    items: list[tuple], prefix: str, back_cb: str = "shop"
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{name} — {price}₽",
                callback_data=f"{prefix}:{key}",
            )
        ]
        for key, name, price, _ in items
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_product_card(buy_cb: str, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить с баланса", callback_data=buy_cb)],
            [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb),
                InlineKeyboardButton(text="🏠 В меню", callback_data="main"),
            ],
        ]
    )


def kb_after_purchase(
    order_id: int,
    needs_login: bool = False,
    needs_code: bool = False,
    login_label: str = "🔐 Отправить данные для входа",
) -> InlineKeyboardMarkup:
    rows = []
    if needs_login:
        rows.append(
            [
                InlineKeyboardButton(
                    text=login_label,
                    callback_data=f"send_login:{order_id}:{1 if needs_code else 0}",
                )
            ]
        )
    if needs_code:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📨 Отправить код для входа",
                    callback_data=f"send_code:{order_id}",
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="💬 Связаться с модератором через бота",
                    callback_data=f"contact_mod:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📧 Указать почту для связи",
                    callback_data=f"contact_email:{order_id}",
                )
            ],
            [InlineKeyboardButton(text="📦 Мои заказы", callback_data="orders")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_guarantee() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Посмотреть отзывы", url=REVIEWS_URL)],
            [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
        ]
    )


def kb_username_link(username: str, back_cb: str = "shop") -> InlineKeyboardMarkup:
    handle = username.lstrip("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↗️ Перейти по юзернейму",
                    url=f"https://t.me/{handle}",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb),
                InlineKeyboardButton(text="🏠 В меню", callback_data="main"),
            ],
        ]
    )


def kb_support() -> InlineKeyboardMarkup:
    handle = SUPPORT_USERNAME.lstrip("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Перейти в поддержку",
                    url=f"https://t.me/{handle}",
                )
            ],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
        ]
    )


def kb_info() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
        ]
    )


def kb_profile() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
            [InlineKeyboardButton(text="📦 История заказов", callback_data="orders")],
            [
                InlineKeyboardButton(
                    text="📜 История транзакций", callback_data="transactions"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎟️ Мои промокоды", callback_data="my_promos"
                ),
                InlineKeyboardButton(
                    text="✏️ Ввести промокод", callback_data="enter_promo"
                ),
            ],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
        ]
    )


def kb_topup_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="topup_go")],
            [InlineKeyboardButton(text="✏️ Изменить сумму", callback_data="topup")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="main")],
        ]
    )


def kb_topup_pay(amount: int, code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid:{amount}:{code}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="main")],
        ]
    )


def kb_calc_actions(buy_cb: str, change_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить с баланса", callback_data=buy_cb)],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить количество", callback_data=change_cb
                )
            ],
            [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="shop"),
                InlineKeyboardButton(text="🏠 В меню", callback_data="main"),
            ],
        ]
    )


def kb_order_actions(order: dict) -> InlineKeyboardMarkup:
    order_id = int(order["id"])
    category = order.get("category")
    rows = []

    if order_needs_login(category):
        login_label = (
            "🔗 Отправить ссылку на геймпасс"
            if category == "roblox_gamepass"
            else "🔐 Отправить данные для входа"
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=login_label,
                    callback_data=f"send_login:{order_id}:{1 if order_needs_code(category) else 0}",
                )
            ]
        )

    if order_needs_code(category):
        rows.append(
            [
                InlineKeyboardButton(
                    text="📨 Отправить код для входа",
                    callback_data=f"send_code:{order_id}",
                )
            ]
        )

    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="💬 Связаться с модератором через бота",
                    callback_data=f"contact_mod:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📧 Указать почту для связи",
                    callback_data=f"contact_email:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="orders"),
                InlineKeyboardButton(text="🏠 В меню", callback_data="main"),
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# =====================================================================
# Утилиты
# =====================================================================


def find_product(items: list[tuple], key: str) -> tuple | None:
    for item in items:
        if item[0] == key:
            return item
    return None


def order_needs_login(category: str | None) -> bool:
    return bool(category and LOGIN_HINTS.get(category))


def order_needs_code(category: str | None) -> bool:
    return category in ("roblox_instant", "brawl")


async def _try_delete(msg: Message) -> None:
    """Тихо удаляет сообщение, игнорируя ошибки."""
    try:
        await msg.delete()
    except Exception:
        pass


async def _edit_prompt(state: FSMContext, text: str,
                       kb: InlineKeyboardMarkup) -> None:
    """Редактирует сохранённое в FSM сообщение-подсказку бота.

    Если редактирование невозможно (фото, устарело и т.д.) — отправляет новое.
    Перед этим обновляет сохранённый msg_id на новый.
    """
    data = await state.get_data()
    chat_id: int | None = data.get("_prompt_chat_id")
    msg_id: int | None = data.get("_prompt_msg_id")
    if chat_id and msg_id:
        try:
            edited = await bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            await state.update_data(_prompt_msg_id=edited.message_id)
            return
        except Exception:
            pass
    # Если не получилось отредактировать — шлём новым сообщением
    sent = await bot.send_message(
        chat_id or 0,
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await state.update_data(_prompt_chat_id=sent.chat.id,
                            _prompt_msg_id=sent.message_id)


async def send_or_edit(target, text: str,
                       kb: InlineKeyboardMarkup) -> Message:
    """Для CallbackQuery удаляет старое сообщение и отправляет новое.
    Возвращает отправленное/отредактированное сообщение."""
    try:
        if isinstance(target, CallbackQuery):
            chat_id = target.message.chat.id
            try:
                await target.message.delete()
            except Exception:
                pass
            return await bot.send_message(
                chat_id,
                text,
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        else:
            return await target.answer(
                text,
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    except Exception:
        chat_id = (
            target.message.chat.id
            if isinstance(target, CallbackQuery)
            else target.chat.id
        )
        return await bot.send_message(
            chat_id,
            text,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


async def show_section(
    call: CallbackQuery, key: str, text: str, kb: InlineKeyboardMarkup
) -> Message:
    """Всегда удаляет старое сообщение и открывает новое. Возвращает Message."""
    image = SECTION_IMAGES.get(key)

    if image and len(text) <= 1024:
        if isinstance(image, str) and not image.startswith(("http://", "https://")):
            local_path = image
            if not os.path.isabs(local_path):
                local_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    local_path,
                )
            if os.path.exists(local_path):
                photo = FSInputFile(local_path)
            else:
                photo = image
        else:
            photo = image

        chat_id = call.message.chat.id
        try:
            await call.message.delete()
        except Exception:
            pass

        try:
            sent = await bot.send_photo(
                chat_id,
                photo=photo,
                caption=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return sent
        except Exception as e:
            logging.warning(f"Не удалось отправить картинку '{key}': {e}")

    return await send_or_edit(call, text, kb)


async def notify_moderator(
    text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    """Отправляет уведомление модератору, если задан MODERATOR_CHAT_ID."""
    if not MODERATOR_CHAT_ID:
        return
    try:
        await bot.send_message(
            MODERATOR_CHAT_ID, text, parse_mode="HTML", reply_markup=reply_markup
        )
    except Exception as e:
        logging.warning(f"Не удалось уведомить модератора: {e}")


def parse_positive_int(text: str) -> int | None:
    """Парсит положительное целое число из текста."""
    text = (text or "").strip().replace(" ", "")
    if not text.isdigit():
        return None
    value = int(text)
    if value <= 0:
        return None
    return value


def is_valid_email(text: str) -> bool:
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (text or "").strip()) is not None


# =====================================================================
# /start и главное меню
# =====================================================================


@dp.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await db_get_or_create_user(message.from_user)
    try:
        await message.answer_photo(
            photo=WELCOME_IMAGE_URL,
            caption=WELCOME_TEXT,
            reply_markup=kb_main_menu(),
            parse_mode="HTML",
        )
    except Exception:
        await message.answer(
            WELCOME_TEXT, reply_markup=kb_main_menu(), parse_mode="HTML"
        )


@dp.callback_query(F.data == "main")
async def cb_main(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_section(call, "welcome", WELCOME_TEXT, kb_main_menu())
    await call.answer()


@dp.callback_query(F.data == "guarantee")
async def cb_guarantee(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_section(call, "guarantee", GUARANTEE_TEXT, kb_guarantee())
    await call.answer()


@dp.callback_query(F.data == "support")
async def cb_support(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_section(call, "support", SUPPORT_TEXT, kb_support())
    await call.answer()


@dp.callback_query(F.data == "info")
async def cb_info(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_section(call, "info", INFO_TEXT, kb_info())
    await call.answer()


# =====================================================================
# Раздел "Купить донат"
# =====================================================================


@dp.callback_query(F.data == "shop")
async def cb_shop(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_section(
        call, "shop", "<b>Купить донат</b>\n\nВыберите категорию:", kb_shop()
    )
    await call.answer()


# --- Roblox моментально ---


@dp.callback_query(F.data == "cat:roblox_instant")
async def cb_roblox_instant(call: CallbackQuery) -> None:
    await show_section(
        call,
        "roblox_instant",
        "<b>Roblox — моментально</b>\n\nВыберите количество робуксов:",
        kb_product_list(ROBUX_INSTANT, "rbi"),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("rbi:"))
async def cb_roblox_instant_card(call: CallbackQuery) -> None:
    key = call.data.split(":", 1)[1]
    product = find_product(ROBUX_INSTANT, key)
    if not product:
        await call.answer("Товар не найден.", show_alert=True)
        return
    _, name, price, delivery = product
    text = (
        f"<b>{escape(name)}</b>\n\n"
        f"Цена: <b>{price}₽</b>\n"
        f"Способ выдачи: {escape(delivery)}\n"
        "Способ оплаты: Оплата с внутреннего баланса бота\n\n"
        "Для покупки на вашем внутреннем балансе должно быть достаточно средств."
    )
    await show_section(
        call,
        "card_roblox_instant",
        text,
        kb_product_card(f"buy:rbi:{key}", "cat:roblox_instant"),
    )
    await call.answer()


# --- Roblox геймпассом ---


@dp.callback_query(F.data == "cat:roblox_gamepass")
async def cb_roblox_gamepass(call: CallbackQuery, state: FSMContext) -> None:
    text = (
        "<b>Roblox — геймпассом (до 5 дней)</b>\n\n"
        "⚠️ <b>Данный способ покупки временно недоступен.</b>\n\n"
        "На данный момент покупка робуксов через геймпасс невозможна "
        "в связи с ограничениями на платформе Roblox.\n\n"
        "Воспользуйтесь покупкой <b>моментально</b> — она работает в штатном режиме."
    )
    await show_section(call, "roblox_gamepass", text, kb_back_main("shop"))
    await call.answer()


@dp.message(ShopStates.waiting_robux_amount)
async def msg_robux_amount(message: Message, state: FSMContext) -> None:
    qty = parse_positive_int(message.text)
    if qty is None:
        await message.answer(
            "Введите положительное число робуксов (например: 1500).",
            reply_markup=kb_back_main("shop"),
        )
        return

    price = max(1, round(qty * ROBUX_GAMEPASS_RATE))
    gamepass_price = max(1, round(qty / ROBUX_GAMEPASS_PASS_PRICE_RATE))

    await state.update_data(
        robux_qty=qty,
        robux_price=price,
        robux_gamepass_price=gamepass_price,
    )

    text = (
        f"<b>Roblox геймпассом</b>\n\n"
        f"Количество: <b>{qty}</b> робуксов\n"
        f"Курс оплаты: 1 робукс = {ROBUX_GAMEPASS_RATE}₽\n"
        f"Итого к оплате: <b>{price}₽</b>\n"
        f"Цена для создания геймпасса: <b>{gamepass_price} R$</b>\n"
        "Срок: до 5 дней\n"
        "Способ оплаты: Оплата с внутреннего баланса бота"
    )
    await message.answer(
        text,
        reply_markup=kb_calc_actions("buy:robux_gp", "cat:roblox_gamepass"),
        parse_mode="HTML",
    )


# --- Brawl Stars ---


@dp.callback_query(F.data == "cat:brawl")
async def cb_brawl(call: CallbackQuery) -> None:
    rows = [
        [InlineKeyboardButton(text=f"{n} — {p}₽", callback_data=f"bs:{k}")]
        for k, n, p, _ in BRAWL_PRODUCTS
    ]
    rows.append(
        [InlineKeyboardButton(text="🎁 Другие акции", callback_data="bs:promo")]
    )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")])
    await show_section(
        call,
        "brawl",
        "<b>Brawl Stars</b>\n\nВыберите товар:",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@dp.callback_query(F.data == "bs:promo")
async def cb_brawl_promo(call: CallbackQuery) -> None:
    text = (
        "Чтобы узнать об актуальных акциях в категории Brawl Stars, "
        f"напишите в Telegram: {BRAWL_PROMO_USERNAME}"
    )
    await show_section(
        call, "brawl", text, kb_username_link(BRAWL_PROMO_USERNAME, "cat:brawl")
    )
    await call.answer()


@dp.callback_query(F.data.startswith("bs:"))
async def cb_brawl_card(call: CallbackQuery) -> None:
    key = call.data.split(":", 1)[1]
    if key == "promo":
        return
    product = find_product(BRAWL_PRODUCTS, key)
    if not product:
        await call.answer("Товар не найден.", show_alert=True)
        return
    _, name, price, delivery = product
    text = (
        f"<b>{escape(name)}</b>\n\n"
        f"Цена: <b>{price}₽</b>\n"
        f"Способ выдачи: {escape(delivery)}\n"
        "Способ оплаты: Оплата с внутреннего баланса бота"
    )
    await show_section(
        call, "card_brawl", text, kb_product_card(f"buy:bs:{key}", "cat:brawl")
    )
    await call.answer()


# --- Telegram Stars ---


@dp.callback_query(F.data == "cat:tgstars")
async def cb_tgstars(call: CallbackQuery, state: FSMContext) -> None:
    text = (
        "<b>Telegram Stars</b>\n\n"
        f"Курс: 1 звезда = {TG_STARS_RATE}₽\n\n"
        "Введите количество звёзд одним сообщением (например: 100):"
    )
    sent = await show_section(call, "tgstars", text, kb_back_main("shop"))
    await state.set_state(ShopStates.waiting_stars_amount)
    await state.update_data(_prompt_chat_id=sent.chat.id,
                            _prompt_msg_id=sent.message_id)
    await call.answer()


@dp.message(ShopStates.waiting_stars_amount)
async def msg_stars_amount(message: Message, state: FSMContext) -> None:
    await _try_delete(message)
    qty = parse_positive_int(message.text)
    if qty is None:
        await _edit_prompt(state,
                           "⚠️ Введите положительное число звёзд (например: 100).",
                           kb_back_main("shop"))
        return
    if qty < MIN_TG_STARS:
        await _edit_prompt(state,
                           f"⚠️ Минимальное количество — {MIN_TG_STARS} звёзд.\n"
                           "Попробуйте ещё раз:",
                           kb_back_main("shop"))
        return
    price = max(1, round(qty * TG_STARS_RATE))
    await state.update_data(stars_qty=qty, stars_price=price)
    text = (
        f"<b>Telegram Stars</b>\n\n"
        f"Количество: <b>{qty}</b> ⭐\n"
        f"Курс: 1 звезда = {TG_STARS_RATE}₽\n"
        f"Итого: <b>{price}₽</b>\n"
        "Минимум: <b>50 звёзд</b>\n"
        "Способ выдачи: моментально\n"
        "Способ оплаты: Оплата с внутреннего баланса бота"
    )
    await _edit_prompt(state, text, kb_calc_actions("buy:stars", "cat:tgstars"))


# --- Другие приложения ---


@dp.callback_query(F.data == "cat:other")
async def cb_other(call: CallbackQuery) -> None:
    text = (
        "Для получения информации по донату в других приложениях "
        f"напишите в Telegram: {OTHER_APPS_USERNAME}"
    )
    await show_section(
        call, "other", text, kb_username_link(OTHER_APPS_USERNAME, "shop")
    )
    await call.answer()


# =====================================================================
# Покупка / списание с баланса
# =====================================================================


async def perform_purchase(
    call: CallbackQuery,
    title: str,
    price: int,
    category: str | None = None,
    extra: dict | None = None,
    state: FSMContext | None = None,
) -> None:
    """Списывает price с баланса и создаёт заказ."""
    await call.answer()
    user = call.from_user
    await db_get_or_create_user(user)

    ok = await db_try_charge(user.id, price)
    if ok and state is not None:
        await state.clear()
    if not ok:
        balance = await db_get_balance(user.id)
        text = (
            "❌ <b>Недостаточно средств на балансе.</b>\n\n"
            f"Сумма заказа: {price}₽\n"
            f"Ваш баланс: {balance}₽\n\n"
            "Пополните баланс и повторите попытку."
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💳 Пополнить баланс", callback_data="topup"
                    )
                ],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
            ]
        )
        await send_or_edit(call, text, kb)
        await call.answer()
        return

    order_id = await db_create_order(
        user.id,
        title,
        price,
        status="Оплачен",
        category=category,
    )
    await db_add_transaction(
        user.id,
        -price,
        kind="purchase",
        reason=f"Заказ #{order_id}: {title}",
    )
    new_balance = await db_get_balance(user.id)
    login_hint = LOGIN_HINTS.get(category) if category else None
    needs_code = category in ("roblox_instant", "brawl")
    login_label = "🔐 Отправить данные для входа"

    text = (
        "✅ <b>Оплата прошла успешно. Заказ принят в обработку.</b>\n\n"
        f"🧾 Номер заказа: <code>#{order_id}</code>\n"
        f"🎁 Товар: {escape(title)}\n"
        f"💰 Сумма: <b>{price}₽</b>\n"
        f"💼 Остаток на балансе: <b>{new_balance}₽</b>\n\n"
    )

    if category == "roblox_gamepass":
        login_label = "🔗 Отправить ссылку на геймпасс"
        if extra:
            gp_price = extra.get("gamepass_price")
            if gp_price:
                text += (
                    f"🎮 <b>Цена для создания геймпасса:</b> <b>{gp_price} R$</b>\n\n"
                )
        text += (
            "🔗 Создайте геймпасс на указанную сумму и нажмите "
            "«Отправить ссылку на геймпасс» — пришлите ссылку одним "
            "сообщением. Никакие данные от аккаунта и коды отправлять не нужно."
        )
    elif login_hint:
        text += (
            "🔐 <b>Для выполнения заказа нужны данные для входа.</b>\n"
            f"{escape(login_hint)}\n\n"
            "Нажмите «Отправить данные для входа» и пришлите их одним "
            "сообщением — модератор получит их вместе с заказом."
        )
        if needs_code:
            if category and category.startswith("roblox"):
                text += (
                    "\n\n📨 <b>Если у вас подключён двухфакторный вход</b> "
                    "(2FA) — на почту придёт код, когда модератор будет "
                    "заходить на аккаунт. Пришлите код кнопкой «Отправить "
                    "код для входа»."
                )
            else:
                text += (
                    "\n\n📨 Если на почту придёт код подтверждения, когда "
                    "модератор будет заходить — пришлите его кнопкой "
                    "«Отправить код для входа»."
                )
    else:
        text += "Выберите удобный способ связи с модератором:"

    await send_or_edit(
        call,
        text,
        kb_after_purchase(
            order_id,
            needs_login=bool(login_hint),
            needs_code=needs_code,
            login_label=login_label,
        ),
    )
    await call.answer("Заказ создан")

    username = f"@{user.username}" if user.username else "—"

    admin_rows = [
        [
            InlineKeyboardButton(
                text="✅ Завершить заказ",
                callback_data=f"ordone:{order_id}:{user.id}",
            )
        ],
    ]

    if category == "roblox_gamepass" and extra:
        gp_price = int(extra.get("gamepass_price", 0))
        if gp_price > 0:
            admin_rows.insert(
                0,
                [
                    InlineKeyboardButton(
                        text="🎮 Попросить изменить цену геймпасса",
                        callback_data=f"gpfix:{order_id}:{user.id}:{gp_price}",
                    )
                ],
            )

    admin_kb = InlineKeyboardMarkup(inline_keyboard=admin_rows)

    admin_text = (
        f"🆕 <b>Новый заказ #{order_id}</b>\n\n"
        f"Покупатель: {escape(user.first_name or '')} ({escape(username)})\n"
        f"Telegram ID: <code>{user.id}</code>\n"
        f"Товар: {escape(title)}\n"
        f"Сумма: {price}₽\n"
        f"Статус: Оплачен"
    )

    if category == "roblox_gamepass" and extra:
        gp_price = extra.get("gamepass_price")
        if gp_price:
            admin_text += f"\nЦена геймпасса: <b>{gp_price} R$</b> (допуск ±5 R$)"

    await notify_moderator(admin_text, reply_markup=admin_kb)


# --- Запрос данных для входа ---


@dp.callback_query(F.data.startswith("send_login:"))
async def cb_send_login(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    order_id = int(parts[1])
    needs_code = len(parts) > 2 and parts[2] == "1"
    await state.set_state(ShopStates.waiting_login_data)
    text = (
        f"🔐 Отправьте данные для входа по заказу <b>#{order_id}</b> "
        "одним сообщением.\n\n"
        "Например: логин/пароль, ссылка на геймпасс, Supercell ID, "
        "@username и т.д."
    )
    sent = await send_or_edit(call, text, kb_back_main(f"order_actions:{order_id}"))
    await state.update_data(login_order_id=order_id, login_needs_code=needs_code,
                            _prompt_chat_id=sent.chat.id, _prompt_msg_id=sent.message_id)
    await call.answer()


@dp.message(ShopStates.waiting_login_data)
async def msg_login_data(message: Message, state: FSMContext) -> None:
    await _try_delete(message)
    payload = (message.text or "").strip()
    data = await state.get_data()
    order_id = int(data.get("login_order_id", 0))
    needs_code = bool(data.get("login_needs_code", False))
    if not payload:
        await _edit_prompt(state, "⚠️ Пустое сообщение. Пришлите данные текстом.",
                           kb_back_main(f"order_actions:{order_id}"))
        return
    await state.clear()

    if order_id:
        await db_set_order_login(order_id, payload)

    user = message.from_user
    username = f"@{user.username}" if user.username else "—"
    await notify_moderator(
        f"🔐 Данные для входа по заказу <b>#{order_id}</b>\n\n"
        f"<pre>{escape(payload)}</pre>\n"
        f"Покупатель: {escape(user.first_name or '')} ({escape(username)})\n"
        f"Telegram ID: <code>{user.id}</code>"
    )

    text = (
        f"✅ Спасибо! Данные по заказу <b>#{order_id}</b> переданы модератору.\n"
        "Скоро с вами свяжутся."
    )
    if needs_code:
        text += (
            "\n\n📨 Когда модератор будет заходить на аккаунт — вам "
            "может прийти код подтверждения. Пришлите его кнопкой "
            "<b>«Отправить код для входа»</b> ниже."
        )
    await message.answer(
        text,
        reply_markup=kb_after_purchase(
            order_id, needs_login=False, needs_code=needs_code
        ),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("send_code:"))
async def cb_send_code(call: CallbackQuery, state: FSMContext) -> None:
    order_id = int(call.data.split(":", 1)[1])
    await state.set_state(ShopStates.waiting_login_code)
    text = (
        f"📨 Пришлите код для входа по заказу <b>#{order_id}</b> "
        "одним сообщением.\n\n"
        "Это код, который пришёл вам на почту, когда модератор "
        "заходил на аккаунт."
    )
    sent = await send_or_edit(call, text, kb_back_main(f"order_actions:{order_id}"))
    await state.update_data(code_order_id=order_id,
                            _prompt_chat_id=sent.chat.id, _prompt_msg_id=sent.message_id)
    await call.answer()


@dp.message(ShopStates.waiting_login_code)
async def msg_login_code(message: Message, state: FSMContext) -> None:
    await _try_delete(message)
    code = (message.text or "").strip()
    data = await state.get_data()
    order_id = int(data.get("code_order_id", 0))
    if not code:
        await _edit_prompt(state, "⚠️ Пустое сообщение. Пришлите код текстом.",
                           kb_back_main(f"order_actions:{order_id}"))
        return
    await state.clear()

    if order_id:
        await db_set_order_login_code(order_id, code)

    user = message.from_user
    username = f"@{user.username}" if user.username else "—"
    await notify_moderator(
        f"📨 Код для входа по заказу <b>#{order_id}</b>\n\n"
        f"<pre>{escape(code)}</pre>\n"
        f"Покупатель: {escape(user.first_name or '')} ({escape(username)})\n"
        f"Telegram ID: <code>{user.id}</code>"
    )

    await message.answer(
        f"✅ Спасибо! Код по заказу <b>#{order_id}</b> передан модератору.\n\n"
        "Если придёт ещё один код — пришлите его той же кнопкой "
        "<b>«Отправить код для входа»</b>.",
        reply_markup=kb_after_purchase(order_id, needs_login=False, needs_code=True),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("buy:rbi:"))
async def cb_buy_rbi(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":", 2)[2]
    product = find_product(ROBUX_INSTANT, key)
    if not product:
        await call.answer("Товар не найден.", show_alert=True)
        return
    _, name, price, _ = product
    await perform_purchase(
        call, f"Roblox — {name} (моментально)", price,
        category="roblox_instant", state=state,
    )


@dp.callback_query(F.data.startswith("buy:bs:"))
async def cb_buy_bs(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":", 2)[2]
    product = find_product(BRAWL_PRODUCTS, key)
    if not product:
        await call.answer("Товар не найден.", show_alert=True)
        return
    _, name, price, _ = product
    await perform_purchase(
        call, f"Brawl Stars — {name}", price, category="brawl", state=state,
    )


@dp.callback_query(F.data == "buy:robux_gp")
async def cb_buy_robux_gp(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    qty = data.get("robux_qty")
    price = data.get("robux_price")
    gamepass_price = data.get("robux_gamepass_price")

    if not qty or not price or not gamepass_price:
        await call.answer("Сначала введите количество.", show_alert=True)
        return

    await perform_purchase(
        call,
        f"Roblox геймпассом — {qty} робуксов (до 5 дней)",
        int(price),
        category="roblox_gamepass",
        extra={"qty": int(qty), "gamepass_price": int(gamepass_price)},
        state=state,
    )


@dp.callback_query(F.data == "buy:stars")
async def cb_buy_stars(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    qty = data.get("stars_qty")
    price = data.get("stars_price")
    if not qty or not price:
        await call.answer("Сначала введите количество.", show_alert=True)
        return
    await perform_purchase(
        call,
        f"Telegram Stars — {qty} звёзд",
        int(price),
        category="tgstars",
        state=state,
    )


# =====================================================================
# Связь с модератором после покупки
# =====================================================================


@dp.callback_query(F.data.startswith("contact_mod:"))
async def cb_contact_mod(call: CallbackQuery) -> None:
    order_id = call.data.split(":", 1)[1]
    user = call.from_user
    username = f"@{user.username}" if user.username else "—"

    await notify_moderator(
        f"📨 Покупатель просит связь по заказу <b>#{order_id}</b>\n\n"
        f"Имя: {escape(user.first_name or '')}\n"
        f"Username: {escape(username)}\n"
        f"Telegram ID: <code>{user.id}</code>\n"
        "Свяжитесь с клиентом в Telegram."
    )

    handle = SUPPORT_USERNAME.lstrip("@")
    text = (
        f"✅ Модератор уведомлён о вашем заказе <b>#{order_id}</b> "
        "и скоро свяжется с вами.\n\n"
        f"Если хотите написать сами — нажмите кнопку ниже."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Написать модератору", url=f"https://t.me/{handle}"
                )
            ],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
        ]
    )
    await send_or_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("contact_email:"))
async def cb_contact_email(call: CallbackQuery, state: FSMContext) -> None:
    order_id = int(call.data.split(":", 1)[1])
    await state.set_state(ShopStates.waiting_email)
    text = (
        f"Введите вашу почту для связи по заказу <b>#{order_id}</b> "
        "одним сообщением.\n\n"
        "Например: <code>example@mail.ru</code>"
    )
    sent = await send_or_edit(call, text, kb_back_main(f"order_actions:{order_id}"))
    await state.update_data(order_id=order_id,
                            _prompt_chat_id=sent.chat.id, _prompt_msg_id=sent.message_id)
    await call.answer()


@dp.message(ShopStates.waiting_email)
async def msg_email(message: Message, state: FSMContext) -> None:
    await _try_delete(message)
    data = await state.get_data()
    order_id = int(data.get("order_id", 0))
    if not is_valid_email(message.text or ""):
        await _edit_prompt(state,
                           "⚠️ Неверный формат почты. Введите корректный адрес, "
                           "например: <code>example@mail.ru</code>",
                           kb_back_main(f"order_actions:{order_id}"))
        return
    email = message.text.strip()
    await state.clear()

    if order_id:
        await db_set_order_contact(order_id, email)

    user = message.from_user
    username = f"@{user.username}" if user.username else "—"
    await notify_moderator(
        f"📧 Покупатель оставил почту по заказу <b>#{order_id}</b>\n\n"
        f"Почта: <code>{escape(email)}</code>\n"
        f"Имя: {escape(user.first_name or '')}\n"
        f"Username: {escape(username)}\n"
        f"Telegram ID: <code>{user.id}</code>"
    )

    await message.answer(
        f"✅ Спасибо! Модератор свяжется с вами по почте: <b>{escape(email)}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
            ]
        ),
        parse_mode="HTML",
    )


# =====================================================================
# Профиль и история заказов
# =====================================================================


@dp.callback_query(F.data == "profile")
async def cb_profile(call: CallbackQuery) -> None:
    user_row = await db_get_or_create_user(call.from_user)
    orders_cnt = await db_orders_count(call.from_user.id)
    user = call.from_user
    username = f"@{user.username}" if user.username else "не указан"
    created = user_row["created_at"].split("T")[0]

    text = (
        "<b>👤 Ваш профиль</b>\n\n"
        f"Telegram ID: <code>{user.id}</code>\n"
        f"Username: {escape(username)}\n"
        f"Имя: {escape(user.first_name or '—')}\n"
        f"Баланс: <b>{user_row['balance']}₽</b>\n"
        f"Дата регистрации: {created}\n"
        f"Заказов: <b>{orders_cnt}</b>\n"
        "Статус: Обычный пользователь"
    )
    await show_section(call, "profile", text, kb_profile())
    await call.answer()


@dp.callback_query(F.data == "orders")
async def cb_orders(call: CallbackQuery) -> None:
    orders = await db_get_orders(call.from_user.id, limit=10)

    rows = []

    if not orders:
        text = "📦 <b>История заказов</b>\n\nУ вас пока нет заказов."
    else:
        lines = ["📦 <b>История заказов</b>\n"]
        for o in orders:
            date = _fmt_msk(o["created_at"])
            lines.append(
                f"<b>#{o['id']}</b>  •  {escape(o['title'])}\n"
                f"Сумма: {o['price']}₽  •  Статус: {escape(o['status'])}\n"
                f"<i>{date}</i>\n"
            )

            if o["status"] != "Выполнен":
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=f"⚙️ Действия по заказу #{o['id']}",
                            callback_data=f"order_actions:{o['id']}",
                        )
                    ]
                )

        text = "\n".join(lines)

    rows.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="profile"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="main"),
        ]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await show_section(call, "orders", text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("order_actions:"))
async def cb_order_actions(call: CallbackQuery) -> None:
    try:
        order_id = int(call.data.split(":", 1)[1])
    except ValueError:
        await call.answer("Некорректный заказ.", show_alert=True)
        return

    order = await db_get_order(order_id)
    if not order or order["tg_id"] != call.from_user.id:
        await call.answer("Заказ не найден.", show_alert=True)
        return

    if order["status"] == "Выполнен":
        has_review = await db_has_review(order_id)
        review_line = (
            "\n\n⭐ Вы уже оставили отзыв по этому заказу. Спасибо!"
            if has_review
            else "\n\n⭐ Если вам понравилось — оставьте, пожалуйста, отзыв."
        )
        text = (
            f"📦 <b>Заказ #{order_id}</b>\n\n"
            f"Товар: {escape(order['title'])}\n"
            f"Сумма: {order['price']}₽\n"
            f"Статус: <b>{escape(order['status'])}</b>\n\n"
            "Этот заказ уже выполнен."
            f"{review_line}"
        )
        rows = []
        if not has_review:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="⭐ Оставить отзыв",
                        callback_data=f"review:{order_id}",
                    )
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="orders"),
                InlineKeyboardButton(text="🏠 В меню", callback_data="main"),
            ]
        )
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await send_or_edit(call, text, kb)
        await call.answer()
        return

    text = (
        f"📦 <b>Заказ #{order_id}</b>\n\n"
        f"Товар: {escape(order['title'])}\n"
        f"Сумма: {order['price']}₽\n"
        f"Статус: <b>{escape(order['status'])}</b>\n\n"
        "Выберите действие по заказу:"
    )
    await send_or_edit(call, text, kb_order_actions(order))
    await call.answer()


def _format_tx_kind(kind: str) -> str:
    return {
        "topup": "Пополнение",
        "purchase": "Покупка",
        "admin_add": "Начисление администратором",
        "admin_reset": "Обнуление баланса администратором",
    }.get(kind, kind)


@dp.callback_query(F.data == "transactions")
async def cb_transactions(call: CallbackQuery) -> None:
    txs = await db_get_transactions(call.from_user.id, limit=20)
    if not txs:
        text = (
            "📜 <b>История транзакций</b>\n\n"
            "Здесь будут отображаться все начисления и списания по "
            "вашему балансу. Пока операций нет."
        )
    else:
        lines = ["📜 <b>История транзакций</b>\n"]
        for t in txs:
            date = _fmt_msk(t["created_at"])
            sign = "➕" if t["amount"] > 0 else "➖"
            lines.append(
                f"{sign} <b>{abs(t['amount'])}₽</b> — "
                f"{escape(_format_tx_kind(t['kind']))}\n"
                + (f"<i>{escape(t['reason'])}</i>\n" if t["reason"] else "")
                + f"<i>{date}</i>\n"
            )
        text = "\n".join(lines)
        if len(text) > 3800:
            text = text[:3800] + "\n…"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="profile"),
                InlineKeyboardButton(text="🏠 В меню", callback_data="main"),
            ],
        ]
    )
    await show_section(call, "orders", text, kb)
    await call.answer()


# =====================================================================
# Пополнение баланса
# =====================================================================


@dp.callback_query(F.data == "topup")
async def cb_topup(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ShopStates.waiting_topup_amount)
    text = (
        "💳 <b>Пополнение баланса</b>\n\n"
        f"Введите сумму пополнения в рублях (минимум {MIN_TOPUP}₽).\n"
        "Например: 500"
    )
    sent = await show_section(call, "topup", text, kb_back_main("profile"))
    await state.update_data(_prompt_chat_id=sent.chat.id,
                            _prompt_msg_id=sent.message_id)
    await call.answer()


@dp.message(ShopStates.waiting_topup_amount)
async def msg_topup_amount(message: Message, state: FSMContext) -> None:
    await _try_delete(message)
    amount = parse_positive_int(message.text)
    if amount is None:
        await _edit_prompt(state,
                           "⚠️ Введите положительное число рублей, например: 500.",
                           kb_back_main("profile"))
        return
    if amount < MIN_TOPUP:
        await _edit_prompt(state,
                           f"⚠️ Минимальная сумма пополнения — {MIN_TOPUP}₽\n"
                           "Попробуйте ещё раз:",
                           kb_back_main("profile"))
        return
    await state.update_data(topup_amount=amount)
    await state.set_state(ShopStates.waiting_topup_confirm)
    await _edit_prompt(state,
                       f"Вы хотите пополнить баланс на <b>{amount}₽</b>?",
                       kb_topup_confirm())


@dp.callback_query(F.data == "topup_go")
async def cb_topup_go(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    amount = int(data.get("topup_amount", 0))
    await state.clear()
    if amount < MIN_TOPUP:
        await call.answer("Сумма не задана.", show_alert=True)
        return
    code = f"{secrets.randbelow(1_000_000):06d}"
    text = (
        f"💳 <b>Оплатите {amount}₽</b> по реквизитам ниже:\n\n"
        f"{CARD_DETAILS}\n\n"
        f"💰 <b>Сумма к переводу: {amount}₽</b>\n\n"
        f"🔢 <b>Код для комментария к переводу:</b>\n"
        f"<code>{code}</code>\n\n"
        "⚠️ Обязательно укажите этот код в <b>комментарии</b> к переводу — "
        "без него платёж не будет засчитан.\n\n"
        "⚠️ Переведите <b>точную сумму</b>, иначе платёж не будет засчитан.\n\n"
        "После оплаты нажмите «Я оплатил» — заявка отправится модератору "
        "на проверку, и баланс начислится после подтверждения."
    )
    await show_section(call, "topup", text, kb_topup_pay(amount, code))
    await call.answer()


@dp.callback_query(F.data.startswith("paid:"))
async def cb_paid(call: CallbackQuery) -> None:
    await call.answer("Заявка отправлена")
    parts = call.data.split(":")
    try:
        amount = int(parts[1])
    except (ValueError, IndexError):
        return
    code = parts[2] if len(parts) > 2 else ""

    user = call.from_user
    username = f"@{user.username}" if user.username else "—"

    text = (
        "🕒 <b>Заявка на пополнение отправлена</b>\n\n"
        f"Сумма: <b>{amount}₽</b>\n"
        + (f"Код в комментарии: <code>{code}</code>\n\n" if code else "\n")
        + "Мы проверим поступление средств и начислим баланс. "
        "Вы получите уведомление, как только заявка будет обработана."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
        ]
    )
    await send_or_edit(call, text, kb)

    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"tpconf:{user.id}:{amount}:{code}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"tprej:{user.id}:{amount}:{code}",
                ),
            ],
        ]
    )
    await notify_moderator(
        f"💰 <b>Новая заявка на пополнение</b>\n\n"
        f"Покупатель: {escape(user.first_name or '')} ({escape(username)})\n"
        f"Telegram ID: <code>{user.id}</code>\n"
        f"Сумма: <b>{amount}₽</b>\n"
        + (f"Код в комментарии: <code>{code}</code>\n\n" if code else "\n")
        + "Проверьте поступление средств (сумма + код в комментарии) "
        "и нажмите соответствующую кнопку.",
        reply_markup=admin_kb,
    )


def _is_moderator(user_id: int) -> bool:
    return bool(MODERATOR_CHAT_ID) and user_id == MODERATOR_CHAT_ID


@dp.callback_query(F.data.startswith("tpconf:"))
async def cb_topup_admin_confirm(call: CallbackQuery) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer("Только для модератора.", show_alert=True)
        return
    try:
        parts = call.data.split(":")
        target_id = int(parts[1])
        amount = int(parts[2])
        code = parts[3] if len(parts) > 3 else ""
    except (ValueError, IndexError):
        await call.answer("Некорректные данные.", show_alert=True)
        return

    new_balance = await db_add_balance(target_id, amount)
    reason = f"Пополнение баланса (код: {code})" if code else "Пополнение баланса"
    await db_add_transaction(
        target_id,
        amount,
        kind="topup",
        reason=reason,
    )

    try:
        old = call.message.text or call.message.caption or ""
        await call.message.edit_text(
            f"{old}\n\n✅ <b>Подтверждено.</b> Баланс пользователя: {new_balance}₽",
            parse_mode="HTML",
        )
    except Exception:
        pass

    try:
        user_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Купить донат", callback_data="shop")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
            ]
        )
        await bot.send_message(
            target_id,
            f"✅ <b>Баланс пополнен на {amount}₽</b>\n\n"
            f"Текущий баланс: <b>{new_balance}₽</b>",
            parse_mode="HTML",
            reply_markup=user_kb,
        )
    except Exception as e:
        logging.warning(f"Не удалось уведомить пользователя {target_id}: {e}")

    await call.answer("Баланс начислен")


@dp.callback_query(F.data.startswith("tprej:"))
async def cb_topup_admin_reject(call: CallbackQuery) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer("Только для модератора.", show_alert=True)
        return
    try:
        parts = call.data.split(":")
        target_id = int(parts[1])
        amount = int(parts[2])
    except (ValueError, IndexError):
        await call.answer("Некорректные данные.", show_alert=True)
        return

    try:
        old = call.message.text or call.message.caption or ""
        await call.message.edit_text(
            f"{old}\n\n❌ <b>Отклонено.</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass

    try:
        await bot.send_message(
            target_id,
            f"❌ <b>Заявка на пополнение на {amount}₽ отклонена.</b>\n\n"
            "Если вы уверены, что оплата была произведена — свяжитесь с поддержкой.",
            parse_mode="HTML",
            reply_markup=kb_support(),
        )
    except Exception as e:
        logging.warning(f"Не удалось уведомить пользователя {target_id}: {e}")

    await call.answer("Отклонено")


# =====================================================================
# Действия модератора по заказу
# =====================================================================


@dp.callback_query(F.data.startswith("ordone:"))
async def cb_order_done(call: CallbackQuery) -> None:
    """Модератор отмечает заказ как выполненный."""
    if not _is_moderator(call.from_user.id):
        await call.answer("Только для модератора.", show_alert=True)
        return
    try:
        _, oid_s, uid_s = call.data.split(":")
        order_id = int(oid_s)
        target_id = int(uid_s)
    except ValueError:
        await call.answer("Некорректные данные.", show_alert=True)
        return

    await db_set_order_status(order_id, "Выполнен")

    try:
        old = call.message.text or call.message.caption or ""
        await call.message.edit_text(
            f"{old}\n\n✅ <b>Заказ #{order_id} отмечен как выполненный.</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass

    try:
        user_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⭐ Оставить отзыв",
                        callback_data=f"review:{order_id}",
                    )
                ],
                [InlineKeyboardButton(text="📦 Мои заказы", callback_data="orders")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
            ]
        )
        await bot.send_message(
            target_id,
            f"🎉 <b>Ваш заказ #{order_id} выполнен!</b>\n\n"
            "Спасибо за покупку. Будем рады видеть вас снова.\n\n"
            "⭐ Если вам понравилось — оставьте, пожалуйста, отзыв. "
            "Это поможет другим покупателям и нам стать лучше.",
            parse_mode="HTML",
            reply_markup=user_kb,
        )
    except Exception as e:
        logging.warning(f"Не удалось уведомить пользователя {target_id}: {e}")

    await call.answer("Заказ выполнен")


# =====================================================================
# Отзывы покупателей
# =====================================================================


def kb_review_skip_photo(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➡️ Без фото",
                    callback_data=f"review_skip_photo:{order_id}",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="review_cancel")],
        ]
    )


def kb_review_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="review_cancel")],
        ]
    )


def kb_review_mod(order_id: int, buyer_id: int, *msg_ids: int) -> InlineKeyboardMarkup:
    """Клавиатура модератора под управляющим сообщением отзыва.
    buyer_id  — tg_id покупателя для кнопки «Ответить».
    msg_ids   — id всех сообщений в чате модератора (заголовок + пересланные),
                передаются в callback_data для форварда в канал.
    """
    ids_str = ":".join(str(m) for m in msg_ids)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать в канал",
                    callback_data=f"pub_review:{order_id}:{ids_str}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Ответить покупателю",
                    callback_data=f"reply_buyer:{buyer_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"rej_review:{order_id}",
                ),
            ],
        ]
    )


@dp.callback_query(F.data.startswith("review:"))
async def cb_review_start(call: CallbackQuery, state: FSMContext) -> None:
    try:
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("Некорректные данные.", show_alert=True)
        return

    order = await db_get_order(order_id)
    if not order or order["tg_id"] != call.from_user.id:
        await call.answer("Заказ не найден.", show_alert=True)
        return
    if order["status"] != "Выполнен":
        await call.answer(
            "Отзыв можно оставить только после выполнения заказа.",
            show_alert=True,
        )
        return
    if await db_has_review(order_id):
        await call.answer("Вы уже оставили отзыв по этому заказу.", show_alert=True)
        return

    await state.clear()
    await state.set_state(ShopStates.waiting_review_photo)
    text = (
        f"⭐ <b>Отзыв по заказу #{order_id}</b>\n\n"
        "📷 Пришлите <b>фото</b> выполненного заказа одним сообщением "
        "(скриншот зачисления, скриншот игры и т.п.).\n\n"
        "Если фото нет — нажмите «Без фото»."
    )
    sent = await send_or_edit(call, text, kb_review_skip_photo(order_id))
    await state.update_data(review_order_id=order_id,
                            _prompt_chat_id=sent.chat.id, _prompt_msg_id=sent.message_id)
    await call.answer()


@dp.callback_query(F.data.startswith("review_skip_photo:"))
async def cb_review_skip_photo(call: CallbackQuery, state: FSMContext) -> None:
    try:
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("Некорректные данные.", show_alert=True)
        return
    await state.set_state(ShopStates.waiting_review_text)
    await state.update_data(review_order_id=order_id, review_photo_id=None)
    text = (
        f"⭐ <b>Отзыв по заказу #{order_id}</b>\n\n"
        "✍️ Напишите ваш комментарий к отзыву одним сообщением."
    )
    await send_or_edit(call, text, kb_review_cancel())
    await call.answer()


@dp.callback_query(F.data == "review_cancel")
async def cb_review_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send_or_edit(
        call,
        "❌ Отправка отзыва отменена.",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📦 Мои заказы", callback_data="orders")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
            ]
        ),
    )
    await call.answer()


@dp.message(ShopStates.waiting_review_photo)
async def msg_review_photo(message: Message, state: FSMContext) -> None:
    # Фото НЕ удаляем здесь — оно нужно для copy_message модератору.
    # Удалим его позже, в msg_review_text, после пересылки.
    file_id: str | None = None
    is_document = False
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        file_id = message.document.file_id
        is_document = True

    data = await state.get_data()
    order_id = int(data.get("review_order_id", 0))

    if not file_id:
        await _try_delete(message)
        await _edit_prompt(state,
                           "⚠️ Пришлите изображение (фото или картинку файлом). "
                           "Если фото нет — нажмите «Без фото».",
                           kb_review_skip_photo(order_id))
        return

    await state.update_data(
        review_photo_id=file_id,
        review_photo_is_document=is_document,
        # Сохраняем координаты фото для copy_message
        review_photo_msg_id=message.message_id,
        review_photo_chat_id=message.chat.id,
    )
    await state.set_state(ShopStates.waiting_review_text)
    sent = await message.answer(
        f"✅ Фото получено.\n\n"
        f"✍️ Теперь напишите комментарий к отзыву по заказу <b>#{order_id}</b> "
        "одним сообщением.",
        parse_mode="HTML",
        reply_markup=kb_review_cancel(),
    )
    await state.update_data(_prompt_chat_id=sent.chat.id, _prompt_msg_id=sent.message_id)


@dp.message(ShopStates.waiting_review_text)
async def msg_review_text(message: Message, state: FSMContext) -> None:
    # НЕ удаляем сообщение здесь — оно нужно для forward_message модератору.
    # Для ошибочных случаев удаляем вручную перед возвратом.
    comment = (message.text or "").strip()
    if not comment:
        await _try_delete(message)
        await _edit_prompt(state, "⚠️ Пустое сообщение. Напишите текст отзыва.",
                           kb_review_cancel())
        return
    if len(comment) > 2000:
        await _try_delete(message)
        await _edit_prompt(state, "⚠️ Комментарий слишком длинный (макс. 2000 символов).\n"
                           "Напишите покороче:",
                           kb_review_cancel())
        return

    data = await state.get_data()
    order_id = int(data.get("review_order_id", 0))
    photo_id = data.get("review_photo_id")
    photo_msg_id = data.get("review_photo_msg_id")
    photo_chat_id = data.get("review_photo_chat_id")
    await state.clear()

    if not order_id:
        await message.answer("Не удалось определить заказ. Попробуйте ещё раз.")
        return

    await db_add_review(order_id, message.from_user.id, photo_id, comment)

    order = await db_get_order(order_id)
    title = order["title"] if order else "—"

    # ----------------------------------------------------------------
    # Пересылаем отзыв модератору через forward_message ("Forwarded from").
    # forward_message не поддерживает reply_markup, поэтому кнопки
    # публикации отправляем отдельным управляющим сообщением после форварда.
    # ID пересланных сообщений сохраняем в callback_data для последующего
    # форварда в канал при нажатии «Опубликовать».
    # ----------------------------------------------------------------
    try:
        header = (
            f"⭐ <b>Новый отзыв</b>\n"
            f"🎁 Товар: <b>{escape(str(title))}</b>"
        )
        # Заголовок тоже сохраняем — он пересылается в канал вместе с отзывом
        header_msg = await bot.send_message(MODERATOR_CHAT_ID, header, parse_mode="HTML")
        buyer_id = message.from_user.id

        if photo_id and photo_msg_id and photo_chat_id:
            # Сначала форвардим — потом удаляем оригиналы
            photo_fwd = await bot.forward_message(
                chat_id=MODERATOR_CHAT_ID,
                from_chat_id=photo_chat_id,
                message_id=photo_msg_id,
            )
            text_fwd = await bot.forward_message(
                chat_id=MODERATOR_CHAT_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            await bot.delete_message(photo_chat_id, photo_msg_id)
            await _try_delete(message)
            await bot.send_message(
                MODERATOR_CHAT_ID,
                "⬆️ Управление отзывом:",
                reply_markup=kb_review_mod(
                    order_id, buyer_id,
                    header_msg.message_id, photo_fwd.message_id, text_fwd.message_id,
                ),
            )
        else:
            # Текстовый отзыв: форвардим сначала, удаляем после
            text_fwd = await bot.forward_message(
                chat_id=MODERATOR_CHAT_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            await _try_delete(message)
            await bot.send_message(
                MODERATOR_CHAT_ID,
                "⬆️ Управление отзывом:",
                reply_markup=kb_review_mod(
                    order_id, buyer_id,
                    header_msg.message_id, text_fwd.message_id,
                ),
            )
    except Exception as e:
        logging.warning(f"Не удалось переслать отзыв модератору: {e}")

    thanks_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Все отзывы", url=REVIEWS_URL)],
            [InlineKeyboardButton(text="📦 Мои заказы", callback_data="orders")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
        ]
    )
    await message.answer(
        f"✅ <b>Спасибо за отзыв по заказу #{order_id}!</b>\n\n"
        "Ваш отзыв передан модератору и скоро появится в нашем канале.",
        parse_mode="HTML",
        reply_markup=thanks_kb,
    )


@dp.callback_query(F.data.startswith("pub_review:"))
async def cb_publish_review(call: CallbackQuery) -> None:
    """Модератор публикует отзыв в канал — пересылает через forward_message."""
    if not _is_moderator(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    # callback_data: pub_review:{order_id}:{msg_id1}[:{msg_id2}]
    parts = call.data.split(":")
    # parts[0]="pub_review", parts[1]=order_id, parts[2+]=msg_ids
    mod_msg_ids = [int(p) for p in parts[2:] if p]
    try:
        for mid in mod_msg_ids:
            await bot.forward_message(
                chat_id=REVIEWS_CHANNEL,
                from_chat_id=call.message.chat.id,
                message_id=mid,
            )
        published_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Опубликовано в канале",
                    url=REVIEWS_URL,
                )]
            ]
        )
        await call.message.edit_reply_markup(reply_markup=published_kb)
        await call.answer("✅ Отзыв опубликован в канале!", show_alert=True)
    except Exception as e:
        logging.warning(f"Ошибка публикации отзыва: {e}")
        await call.answer(f"Ошибка: {e}", show_alert=True)


@dp.callback_query(F.data.startswith("rej_review:"))
async def cb_reject_review(call: CallbackQuery) -> None:
    """Модератор отклоняет отзыв."""
    if not _is_moderator(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    rejected_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отклонён", callback_data="noop")]
        ]
    )
    await call.message.edit_reply_markup(reply_markup=rejected_kb)
    await call.answer("Отзыв отклонён.", show_alert=True)


@dp.callback_query(F.data.startswith("gpfix:"))
async def cb_gamepass_fix(call: CallbackQuery, state: FSMContext) -> None:
    """Модератор запускает запрос на изменение цены геймпасса."""
    await call.answer()
    if not _is_moderator(call.from_user.id):
        await call.answer("Только для модератора.", show_alert=True)
        return
    try:
        _, oid_s, uid_s, gp_s = call.data.split(":")
        order_id = int(oid_s)
        target_id = int(uid_s)
        suggested_price = int(gp_s)
    except ValueError:
        await call.answer("Некорректные данные.", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_gp_price)
    await state.update_data(
        gp_order_id=order_id,
        gp_target_id=target_id,
        gp_admin_chat_id=call.message.chat.id,
        gp_admin_msg_id=call.message.message_id,
    )

    prompt = await call.message.answer(
        f"🎮 Введите новую цену геймпасса в R$ для заказа #{order_id}.\n"
        f"Расчётная цена: <b>{suggested_price} R$</b>.\n\n"
        "Отправьте число или /cancel для отмены.",
        parse_mode="HTML",
    )
    await state.update_data(gp_prompt_msg_id=prompt.message_id)


@dp.message(AdminStates.waiting_gp_price, Command("cancel"))
async def msg_gp_price_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


@dp.message(AdminStates.waiting_gp_price)
async def msg_gp_price_input(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    raw = (message.text or "").strip().replace(",", ".")
    try:
        gp_price = int(round(float(raw)))
        if gp_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное целое число (R$).")
        return

    data = await state.get_data()
    order_id = data.get("gp_order_id")
    target_id = data.get("gp_target_id")
    admin_chat_id = data.get("gp_admin_chat_id")
    admin_msg_id = data.get("gp_admin_msg_id")
    prompt_msg_id = data.get("gp_prompt_msg_id")
    await state.clear()

    if not (order_id and target_id):
        await message.answer("Контекст потерян. Откройте заявку заново.")
        return

    try:
        user_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⚙️ Действия по заказу",
                        callback_data=f"order_actions:{order_id}",
                    )
                ],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
            ]
        )
        await bot.send_message(
            target_id,
            f"⚠️ <b>Просьба по заказу #{order_id}</b>\n\n"
            f"Пожалуйста, измените цену вашего геймпасса в Roblox на "
            f"<b>{gp_price} R$</b> и пришлите обновлённую ссылку через кнопку "
            "«🔗 Отправить ссылку на геймпасс».",
            parse_mode="HTML",
            reply_markup=user_kb,
        )
    except Exception as e:
        logging.warning(f"Не удалось уведомить пользователя {target_id}: {e}")
        await message.answer("Не удалось отправить запрос покупателю.")
        return

    if admin_chat_id and admin_msg_id:
        keep_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Завершить заказ",
                        callback_data=f"ordone:{order_id}:{target_id}",
                    )
                ]
            ]
        )
        try:
            await bot.edit_message_reply_markup(
                chat_id=admin_chat_id,
                message_id=admin_msg_id,
                reply_markup=keep_kb,
            )
        except Exception:
            pass

    if prompt_msg_id:
        try:
            await bot.delete_message(admin_chat_id, prompt_msg_id)
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass

    await bot.send_message(
        admin_chat_id,
        f"📨 Запрос на изменение цены геймпасса по заказу #{order_id} "
        f"отправлен покупателю: <b>{gp_price} R$</b>.",
        parse_mode="HTML",
    )


# =====================================================================
# Админ-панель
# =====================================================================


USERS_PAGE_SIZE = 8


def kb_admin_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="adm:find")],
            [
                InlineKeyboardButton(
                    text="👥 Список пользователей", callback_data="adm:users:0"
                )
            ],
            [InlineKeyboardButton(text="🎟️ Промокоды", callback_data="adm:promos")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close")],
        ]
    )


def _format_user_row(u: dict) -> str:
    handle = u.get("username")
    name = u.get("first_name") or "—"
    label = f"@{handle}" if handle else (name or f"id{u['tg_id']}")
    if u.get("is_blacklisted"):
        label = f"🚫 {label}"
    return f"{label} · {u['balance']}₽"


def kb_admin_users(users: list[dict], page: int, total: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=_format_user_row(u),
                callback_data=f"adm:user:{u['tg_id']}",
            )
        ]
        for u in users
    ]
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"adm:users:{page - 1}")
        )
    last_page = max(0, (total - 1) // USERS_PAGE_SIZE)
    nav.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{last_page + 1}", callback_data="adm:noop"
        )
    )
    if page < last_page:
        nav.append(
            InlineKeyboardButton(text="➡️", callback_data=f"adm:users:{page + 1}")
        )
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(text="🔍 Найти", callback_data="adm:find"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_admin_user(
    target_id: int, blocked: bool, from_list_page: int | None = None
) -> InlineKeyboardMarkup:
    block_btn = (
        InlineKeyboardButton(
            text="✅ Убрать из ЧС", callback_data=f"adm:unblock:{target_id}"
        )
        if blocked
        else InlineKeyboardButton(
            text="🚫 В чёрный список", callback_data=f"adm:block:{target_id}"
        )
    )
    if from_list_page is not None:
        nav_row = [
            InlineKeyboardButton(
                text="⬅️ К списку", callback_data=f"adm:users:{from_list_page}"
            ),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close"),
        ]
    else:
        nav_row = [
            InlineKeyboardButton(
                text="🔍 Другой пользователь", callback_data="adm:find"
            ),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close"),
        ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Начислить баланс", callback_data=f"adm:credit:{target_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="♻️ Обнулить баланс", callback_data=f"adm:reset:{target_id}"
                )
            ],
            [block_btn],
            [
                InlineKeyboardButton(
                    text="📜 История транзакций",
                    callback_data=f"adm:tx:{target_id}",
                )
            ],
            nav_row,
        ]
    )


async def _get_admin_card_source(state: FSMContext) -> int | None:
    """Возвращает номер страницы списка, если карточка открыта из списка, иначе None."""
    data = await state.get_data()
    page = data.get("admin_user_from_list_page")
    return int(page) if page is not None else None


async def _send_admin_user_card(
    call: CallbackQuery, target_id: int, state: FSMContext
) -> None:
    user_row = await db_find_user(target_id)
    if not user_row:
        await send_or_edit(
            call,
            f"❌ Пользователь с ID <code>{target_id}</code> не найден.",
            kb_admin_main(),
        )
        return
    blocked = bool(user_row.get("is_blacklisted"))
    orders_cnt = await db_orders_count(target_id)
    from_list_page = await _get_admin_card_source(state)
    text = (
        "<b>👤 Карточка пользователя</b>\n\n"
        f"Telegram ID: <code>{user_row['tg_id']}</code>\n"
        f"Username: @{escape(user_row.get('username') or '—')}\n"
        f"Имя: {escape(user_row.get('first_name') or '—')}\n"
        f"Баланс: <b>{user_row['balance']}₽</b>\n"
        f"Заказов: <b>{orders_cnt}</b>\n"
        f"Чёрный список: {'<b>да</b>' if blocked else 'нет'}"
    )
    await send_or_edit(
        call, text, kb_admin_user(target_id, blocked, from_list_page)
    )


@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "<b>🛠️ Админ-панель</b>\n\nВыберите действие:",
        reply_markup=kb_admin_main(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "adm:close")
async def cb_adm_close(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer("Закрыто")


@dp.callback_query(F.data == "adm:noop")
async def cb_adm_noop(call: CallbackQuery) -> None:
    await call.answer()


@dp.callback_query(F.data.startswith("adm:users:"))
async def cb_adm_users(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    try:
        page = max(0, int(call.data.split(":", 2)[2]))
    except (ValueError, IndexError):
        page = 0
    total = await db_users_count()
    users = await db_list_users(USERS_PAGE_SIZE, page * USERS_PAGE_SIZE)
    if not users and page > 0:
        page = 0
        users = await db_list_users(USERS_PAGE_SIZE, 0)
    await state.update_data(admin_users_last_page=page)
    if total == 0:
        await send_or_edit(
            call,
            "<b>👥 Пользователей пока нет.</b>",
            kb_admin_main(),
        )
        await call.answer()
        return
    text = (
        f"<b>👥 Пользователи бота</b>\n"
        f"Всего: <b>{total}</b>\n\n"
        "Нажмите на пользователя, чтобы открыть карточку."
    )
    await send_or_edit(call, text, kb_admin_users(users, page, total))
    await call.answer()


@dp.callback_query(F.data.startswith("adm:user:"))
async def cb_adm_user_open(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer()
        return
    try:
        target_id = int(call.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await call.answer("Некорректные данные.", show_alert=True)
        return
    data = await state.get_data()
    page = int(data.get("admin_users_last_page", 0) or 0)
    await state.clear()
    await state.update_data(admin_user_from_list_page=page)
    await _send_admin_user_card(call, target_id, state)
    await call.answer()


@dp.callback_query(F.data == "adm:find")
async def cb_adm_find(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    await state.set_state(AdminStates.waiting_user_id)
    kb_find = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:close")]
    ])
    sent = await send_or_edit(
        call, "🔍 Отправьте Telegram ID пользователя одним сообщением.", kb_find,
    )
    await state.update_data(_prompt_chat_id=sent.chat.id, _prompt_msg_id=sent.message_id)
    await call.answer()


@dp.message(AdminStates.waiting_user_id)
async def msg_adm_user_id(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    await _try_delete(message)
    target_id = parse_positive_int(message.text)
    if target_id is None:
        await _edit_prompt(state, "⚠️ Введите корректный числовой Telegram ID.",
                           InlineKeyboardMarkup(inline_keyboard=[[
                               InlineKeyboardButton(text="❌ Отмена", callback_data="adm:close")
                           ]]))
        return
    await state.clear()
    user_row = await db_find_user(target_id)
    if not user_row:
        await message.answer(
            f"❌ Пользователь с ID <code>{target_id}</code> не найден.",
            reply_markup=kb_admin_main(),
            parse_mode="HTML",
        )
        return
    blocked = bool(user_row.get("is_blacklisted"))
    orders_cnt = await db_orders_count(target_id)
    text = (
        "<b>👤 Карточка пользователя</b>\n\n"
        f"Telegram ID: <code>{user_row['tg_id']}</code>\n"
        f"Username: @{escape(user_row.get('username') or '—')}\n"
        f"Имя: {escape(user_row.get('first_name') or '—')}\n"
        f"Баланс: <b>{user_row['balance']}₽</b>\n"
        f"Заказов: <b>{orders_cnt}</b>\n"
        f"Чёрный список: {'<b>да</b>' if blocked else 'нет'}"
    )
    await message.answer(
        text,
        reply_markup=kb_admin_user(target_id, blocked, from_list_page=None),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("adm:credit:"))
async def cb_adm_credit(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer()
        return
    target_id = int(call.data.split(":")[2])
    prev = await state.get_data()
    saved_source = prev.get("admin_user_from_list_page")
    await state.set_state(AdminStates.waiting_credit_amount)
    kb_cancel = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:close")]
    ])
    sent = await send_or_edit(
        call,
        f"➕ Сколько рублей начислить пользователю <code>{target_id}</code>?\n"
        "Отправьте число одним сообщением.",
        kb_cancel,
    )
    await state.update_data(
        adm_target_id=target_id, admin_user_from_list_page=saved_source,
        _prompt_chat_id=sent.chat.id, _prompt_msg_id=sent.message_id,
    )
    await call.answer()


@dp.message(AdminStates.waiting_credit_amount)
async def msg_adm_credit(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    await _try_delete(message)
    amount = parse_positive_int(message.text)
    if amount is None:
        await _edit_prompt(state, "⚠️ Введите положительное число рублей.",
                           InlineKeyboardMarkup(inline_keyboard=[[
                               InlineKeyboardButton(text="❌ Отмена", callback_data="adm:close")
                           ]]))
        return
    data = await state.get_data()
    target_id = int(data.get("adm_target_id", 0))
    saved_source = data.get("admin_user_from_list_page")
    await state.clear()
    if saved_source is not None:
        await state.update_data(admin_user_from_list_page=saved_source)
    if not target_id:
        await message.answer("Не указан пользователь.", reply_markup=kb_admin_main())
        return
    new_balance = await db_add_balance(target_id, amount)
    await db_add_transaction(
        target_id, amount, kind="admin_add", reason="Начисление администратором"
    )
    try:
        await bot.send_message(
            target_id,
            f"✅ <b>Администратор начислил вам {amount}₽</b>\n"
            f"Текущий баланс: <b>{new_balance}₽</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    from_list_page = saved_source if saved_source is not None else None
    from_list_page = int(from_list_page) if from_list_page is not None else None
    await message.answer(
        f"✅ Начислено {amount}₽. Новый баланс: <b>{new_balance}₽</b>",
        parse_mode="HTML",
        reply_markup=kb_admin_user(
            target_id,
            await db_is_blacklisted(target_id),
            from_list_page=from_list_page,
        ),
    )


@dp.callback_query(F.data.startswith("adm:reset:"))
async def cb_adm_reset(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer()
        return
    target_id = int(call.data.split(":")[2])
    old_balance = await db_get_balance(target_id)
    await db_set_balance(target_id, 0)
    if old_balance:
        await db_add_transaction(
            target_id,
            -old_balance,
            kind="admin_reset",
            reason="Обнуление администратором",
        )
    try:
        await bot.send_message(
            target_id,
            "♻️ <b>Ваш баланс был обнулён администратором.</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await _send_admin_user_card(call, target_id, state)
    await call.answer("Баланс обнулён")


@dp.callback_query(F.data.startswith("adm:block:"))
async def cb_adm_block(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer()
        return
    target_id = int(call.data.split(":")[2])
    await db_set_blacklist(target_id, True)
    try:
        await bot.send_message(
            target_id,
            "🚫 <b>Вы добавлены в чёрный список магазина.</b>\n"
            "Доступ к боту ограничен.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await _send_admin_user_card(call, target_id, state)
    await call.answer("В чёрном списке")


@dp.callback_query(F.data.startswith("adm:unblock:"))
async def cb_adm_unblock(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_moderator(call.from_user.id):
        await call.answer()
        return
    target_id = int(call.data.split(":")[2])
    await db_set_blacklist(target_id, False)
    try:
        await bot.send_message(
            target_id,
            "✅ <b>Вы исключены из чёрного списка.</b> Доступ к боту восстановлен.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await _send_admin_user_card(call, target_id, state)
    await call.answer("Убран из ЧС")


@dp.callback_query(F.data.startswith("adm:tx:"))
async def cb_adm_transactions(call: CallbackQuery) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        await call.answer("Только для модератора.", show_alert=True)
        return
    try:
        target_id = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("Некорректные данные.", show_alert=True)
        return

    txs = await db_get_transactions(target_id, limit=30)
    if not txs:
        text = (
            f"📜 <b>История транзакций</b>\n"
            f"Пользователь: <code>{target_id}</code>\n\n"
            "Операций нет."
        )
    else:
        lines = [
            f"📜 <b>История транзакций</b>",
            f"Пользователь: <code>{target_id}</code>\n",
        ]
        for t in txs:
            date = _fmt_msk(t["created_at"])
            sign = "➕" if t["amount"] > 0 else "➖"
            lines.append(
                f"{sign} <b>{abs(t['amount'])}₽</b> — "
                f"{escape(_format_tx_kind(t['kind']))}\n"
                + (f"<i>{escape(t['reason'])}</i>\n" if t["reason"] else "")
                + f"<i>{date}</i>"
            )
        text = "\n".join(lines)
        if len(text) > 3800:
            text = text[:3800] + "\n…"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ К пользователю",
                    callback_data=f"adm:back:{target_id}",
                )
            ],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close")],
        ]
    )
    await send_or_edit(call, text, kb)


@dp.callback_query(F.data.startswith("adm:back:"))
async def cb_adm_back(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    try:
        target_id = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        return
    await _send_admin_user_card(call, target_id, state)


# =====================================================================
# Промокоды — вспомогательные функции
# =====================================================================


def _promo_is_valid_now(promo: dict) -> bool:
    """Проверяет, активен ли промокод в данный момент."""
    if not promo.get("is_active"):
        return False
    now = datetime.now(timezone.utc)
    starts = promo.get("starts_at")
    expires = promo.get("expires_at")
    if starts:
        try:
            if now < datetime.fromisoformat(starts):
                return False
        except ValueError:
            pass
    if expires:
        try:
            if now > datetime.fromisoformat(expires):
                return False
        except ValueError:
            pass
    return True


def _fmt_promo_dates(promo: dict) -> str:
    starts = promo.get("starts_at")
    expires = promo.get("expires_at")
    if not starts and not expires:
        return "Бессрочно"
    parts = []
    if starts:
        try:
            dt = datetime.fromisoformat(starts)
            parts.append(f"с {dt.strftime('%d.%m.%Y')}")
        except ValueError:
            parts.append(f"с {starts}")
    if expires:
        try:
            dt = datetime.fromisoformat(expires)
            parts.append(f"по {dt.strftime('%d.%m.%Y')}")
        except ValueError:
            parts.append(f"по {expires}")
    return " ".join(parts)


def _parse_date_iso(date_str: str) -> str | None:
    try:
        d = datetime.strptime(date_str.strip(), "%d.%m.%Y")
        return d.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


# =====================================================================
# Промокоды — Административная панель
# =====================================================================


def kb_admin_promos(promos: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for p in promos:
        icon = "✅" if p["is_active"] else "🔴"
        rows.append([
            InlineKeyboardButton(
                text=f"{icon} {p['code']} — {p['product_title']} ({p['promo_price']}₽)",
                callback_data=f"adm:promo:{p['id']}",
            )
        ])
    rows.append([InlineKeyboardButton(text="➕ Создать промокод", callback_data="adm:promo_create")])
    rows.append([InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="adm:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_promo_game_select() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟦 Roblox", callback_data="adm:promo_game:Roblox")],
        [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="adm:promo_game:Brawl Stars")],
        [InlineKeyboardButton(text="✨ Telegram Stars", callback_data="adm:promo_game:Telegram Stars")],
        [InlineKeyboardButton(text="📦 Другое", callback_data="adm:promo_game:Другое")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:promos")],
    ])


@dp.callback_query(F.data == "adm:panel")
async def cb_adm_panel(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    await state.clear()
    await send_or_edit(
        call,
        "<b>🛠️ Админ-панель</b>\n\nВыберите действие:",
        kb_admin_main(),
    )


@dp.callback_query(F.data == "adm:promos")
async def cb_adm_promos(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    await state.clear()
    promos = await db_list_promos()
    text = "<b>🎟️ Промокоды</b>\n\n"
    if promos:
        text += f"Всего промокодов: <b>{len(promos)}</b>\n\nНажмите на промокод для управления."
    else:
        text += "Промокодов пока нет. Создайте первый!"
    await send_or_edit(call, text, kb_admin_promos(promos))


@dp.callback_query(F.data == "adm:promo_create")
async def cb_adm_promo_create(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    await state.set_state(PromoStates.waiting_code_input)
    await send_or_edit(
        call,
        "📝 <b>Создание промокода</b>\n\n"
        "Введите <b>код промокода</b> (только латинские буквы, цифры и знак «_», без пробелов).\n\n"
        "Например: <code>SALE20</code>",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:promos")]
        ])
    )


@dp.message(PromoStates.waiting_code_input)
async def msg_promo_code_input(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    code = (message.text or "").strip().upper()
    if not code or not code.replace("_", "").isalnum():
        await message.answer(
            "⚠️ Код может содержать только латинские буквы, цифры и «_». Попробуйте ещё раз.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:promos")]
            ])
        )
        return
    existing = await db_get_promo_by_code(code)
    if existing:
        await message.answer(
            f"⚠️ Промокод <code>{escape(code)}</code> уже существует. Введите другой.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:promos")]
            ])
        )
        return
    await state.update_data(promo_code=code)
    await state.set_state(None)
    await message.answer(
        f"Код: <code>{escape(code)}</code>\n\n"
        "🎮 Выберите <b>игру</b>, для которой действует промокод:",
        parse_mode="HTML",
        reply_markup=kb_promo_game_select()
    )


@dp.callback_query(F.data.startswith("adm:promo_game:"))
async def cb_adm_promo_game(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    game = call.data.split(":", 2)[2]
    await state.update_data(promo_game=game)
    await state.set_state(PromoStates.waiting_product)
    data = await state.get_data()
    code = data.get("promo_code", "?")
    await send_or_edit(
        call,
        f"Код: <code>{escape(code)}</code>  |  Игра: <b>{escape(game)}</b>\n\n"
        "📦 Введите <b>название товара</b>\n"
        "Например: <code>800 Robux</code> или <code>Brawl Pass Plus</code>",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:promos")]
        ])
    )


@dp.message(PromoStates.waiting_product)
async def msg_promo_product(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    product = (message.text or "").strip()
    if not product:
        await message.answer("⚠️ Название товара не может быть пустым. Введите ещё раз.")
        return
    await state.update_data(promo_product=product)
    await state.set_state(PromoStates.waiting_price)
    data = await state.get_data()
    code = data.get("promo_code", "?")
    game = data.get("promo_game", "?")
    await message.answer(
        f"Код: <code>{escape(code)}</code>  |  Игра: <b>{escape(game)}</b>\n"
        f"Товар: <b>{escape(product)}</b>\n\n"
        "💰 Введите <b>цену по промокоду</b> (целое число в рублях, например: <code>150</code>):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:promos")]
        ])
    )


@dp.message(PromoStates.waiting_price)
async def msg_promo_price_input(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    price = parse_positive_int(message.text)
    if price is None:
        await message.answer("⚠️ Введите корректную сумму (целое число больше 0).")
        return
    await state.update_data(promo_price=price)
    await state.set_state(PromoStates.waiting_dates)
    await message.answer(
        "📅 Введите <b>срок действия</b> промокода:\n\n"
        "• Дата окончания: <code>31.12.2026</code>\n"
        "• Диапазон дат: <code>01.07.2026 - 31.12.2026</code>\n"
        "• Или нажмите кнопку ниже, если промокод бессрочный:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="♾️ Бессрочно", callback_data="adm:promo_dates:forever")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:promos")],
        ])
    )


@dp.callback_query(F.data == "adm:promo_dates:forever")
async def cb_adm_promo_dates_forever(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    data = await state.get_data()
    await state.clear()
    await _save_promo_and_confirm(call, data, starts_at=None, expires_at=None)


@dp.message(PromoStates.waiting_dates)
async def msg_promo_dates(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    text = (message.text or "").strip()
    starts_at = None
    expires_at = None
    separators = [" - ", "–", "—", " — "]
    sep_found = next((s for s in separators if s in text), None)
    if sep_found:
        parts = text.split(sep_found, 1)
        starts_at = _parse_date_iso(parts[0])
        expires_at = _parse_date_iso(parts[1])
        if not starts_at or not expires_at:
            await message.answer(
                "⚠️ Не удалось распознать даты. Используйте формат:\n"
                "<code>01.07.2026 - 31.12.2026</code>",
                parse_mode="HTML"
            )
            return
    else:
        expires_at = _parse_date_iso(text)
        if not expires_at:
            await message.answer(
                "⚠️ Не удалось распознать дату. Введите в формате <code>31.12.2026</code>.",
                parse_mode="HTML"
            )
            return
    data = await state.get_data()
    await state.clear()
    await _save_promo_and_confirm_msg(message, data, starts_at=starts_at, expires_at=expires_at)


async def _save_promo_and_confirm(
    call: CallbackQuery,
    data: dict,
    starts_at: str | None,
    expires_at: str | None,
) -> None:
    code = data.get("promo_code")
    game = data.get("promo_game")
    product = data.get("promo_product")
    price = data.get("promo_price")
    if not all([code, game, product, price]):
        await send_or_edit(call, "❌ Ошибка: данные утеряны. Начните заново.", kb_admin_promos([]))
        return
    promo_id = await db_create_promo(code, game, product, int(price), starts_at, expires_at)
    dates_str = _fmt_promo_dates({"starts_at": starts_at, "expires_at": expires_at})
    text = (
        "✅ <b>Промокод создан!</b>\n\n"
        f"🎟️ Код: <code>{escape(code)}</code>\n"
        f"🎮 Игра: {escape(game)}\n"
        f"📦 Товар: {escape(product)}\n"
        f"💰 Цена: <b>{price}₽</b>\n"
        f"📅 Срок: {dates_str}\n"
        f"🆔 ID: {promo_id}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ Все промокоды", callback_data="adm:promos")],
        [InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="adm:panel")],
    ])
    await send_or_edit(call, text, kb)


async def _save_promo_and_confirm_msg(
    message: Message,
    data: dict,
    starts_at: str | None,
    expires_at: str | None,
) -> None:
    code = data.get("promo_code")
    game = data.get("promo_game")
    product = data.get("promo_product")
    price = data.get("promo_price")
    if not all([code, game, product, price]):
        await message.answer("❌ Ошибка: данные утеряны. Начните заново.")
        return
    promo_id = await db_create_promo(code, game, product, int(price), starts_at, expires_at)
    dates_str = _fmt_promo_dates({"starts_at": starts_at, "expires_at": expires_at})
    text = (
        "✅ <b>Промокод создан!</b>\n\n"
        f"🎟️ Код: <code>{escape(code)}</code>\n"
        f"🎮 Игра: {escape(game)}\n"
        f"📦 Товар: {escape(product)}\n"
        f"💰 Цена: <b>{price}₽</b>\n"
        f"📅 Срок: {dates_str}\n"
        f"🆔 ID: {promo_id}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ Все промокоды", callback_data="adm:promos")],
        [InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="adm:panel")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("adm:promo:"))
async def cb_adm_promo_detail(call: CallbackQuery) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    parts = call.data.split(":")
    if len(parts) < 3:
        return
    try:
        promo_id = int(parts[2])
    except ValueError:
        return
    promo = await db_get_promo_by_id(promo_id)
    if not promo:
        await call.answer("Промокод не найден.", show_alert=True)
        return
    usage_cnt = await db_promo_usage_count(promo_id)
    status_text = "✅ Активен" if promo["is_active"] else "🔴 Отключён"
    toggle_text = "🔴 Отключить" if promo["is_active"] else "✅ Включить"
    dates_str = _fmt_promo_dates(promo)
    valid_now = _promo_is_valid_now(promo)
    text = (
        f"<b>🎟️ Промокод: <code>{escape(promo['code'])}</code></b>\n\n"
        f"🎮 Игра: {escape(promo['game'])}\n"
        f"📦 Товар: {escape(promo['product_title'])}\n"
        f"💰 Цена: <b>{promo['promo_price']}₽</b>\n"
        f"📅 Срок: {dates_str}\n"
        f"📊 Статус: {status_text}  |  Сейчас: {'🟢 работает' if valid_now else '🔴 не работает'}\n"
        f"🛒 Использовано: <b>{usage_cnt}</b> раз"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"adm:promo_toggle:{promo_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"adm:promo_del:{promo_id}")],
        [InlineKeyboardButton(text="⬅️ К промокодам", callback_data="adm:promos")],
    ])
    await send_or_edit(call, text, kb)


@dp.callback_query(F.data.startswith("adm:promo_toggle:"))
async def cb_adm_promo_toggle(call: CallbackQuery) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    try:
        promo_id = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        return
    promo = await db_get_promo_by_id(promo_id)
    if not promo:
        await call.answer("Промокод не найден.", show_alert=True)
        return
    new_state = not bool(promo["is_active"])
    await db_toggle_promo(promo_id, new_state)
    status_word = "включён" if new_state else "отключён"
    await call.answer(f"Промокод {status_word}.", show_alert=True)
    promo["is_active"] = int(new_state)
    usage_cnt = await db_promo_usage_count(promo_id)
    toggle_text = "🔴 Отключить" if new_state else "✅ Включить"
    dates_str = _fmt_promo_dates(promo)
    valid_now = _promo_is_valid_now(promo)
    status_text = "✅ Активен" if new_state else "🔴 Отключён"
    text = (
        f"<b>🎟️ Промокод: <code>{escape(promo['code'])}</code></b>\n\n"
        f"🎮 Игра: {escape(promo['game'])}\n"
        f"📦 Товар: {escape(promo['product_title'])}\n"
        f"💰 Цена: <b>{promo['promo_price']}₽</b>\n"
        f"📅 Срок: {dates_str}\n"
        f"📊 Статус: {status_text}  |  Сейчас: {'🟢 работает' if valid_now else '🔴 не работает'}\n"
        f"🛒 Использовано: <b>{usage_cnt}</b> раз"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"adm:promo_toggle:{promo_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"adm:promo_del:{promo_id}")],
        [InlineKeyboardButton(text="⬅️ К промокодам", callback_data="adm:promos")],
    ])
    await send_or_edit(call, text, kb)


@dp.callback_query(F.data.startswith("adm:promo_del:"))
async def cb_adm_promo_del(call: CallbackQuery) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    try:
        promo_id = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        return
    promo = await db_get_promo_by_id(promo_id)
    if not promo:
        await call.answer("Промокод не найден.", show_alert=True)
        return
    text = (
        f"❓ Удалить промокод <code>{escape(promo['code'])}</code>?\n\n"
        "Все данные об использовании тоже будут удалены."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Да, удалить", callback_data=f"adm:promo_del_yes:{promo_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm:promo:{promo_id}")],
    ])
    await send_or_edit(call, text, kb)


@dp.callback_query(F.data.startswith("adm:promo_del_yes:"))
async def cb_adm_promo_del_yes(call: CallbackQuery) -> None:
    await call.answer()
    if not _is_moderator(call.from_user.id):
        return
    try:
        promo_id = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        return
    await db_delete_promo(promo_id)
    await call.answer("Промокод удалён.", show_alert=True)
    promos = await db_list_promos()
    text = "<b>🎟️ Промокоды</b>\n\n"
    text += f"Всего промокодов: <b>{len(promos)}</b>\n\nНажмите на промокод для управления." if promos else "Промокодов пока нет."
    await send_or_edit(call, text, kb_admin_promos(promos))


# =====================================================================
# Промокоды — Покупатель
# =====================================================================


@dp.callback_query(F.data == "enter_promo")
async def cb_enter_promo(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(ShopStates.waiting_promo_input)
    await send_or_edit(
        call,
        "✏️ <b>Ввести промокод</b>\n\n"
        "Отправьте код промокода одним сообщением.\n"
        "Промокод появится в разделе «Мои промокоды».",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile")]
        ])
    )


@dp.message(ShopStates.waiting_promo_input)
async def msg_promo_input(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip()
    if not code:
        await message.answer("Введите код промокода.")
        return

    promo = await db_get_promo_by_code(code)
    kb_back = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile")]
    ])

    if not promo:
        await message.answer(
            "❌ Промокод не найден. Проверьте правильность написания.",
            reply_markup=kb_back
        )
        return

    if not _promo_is_valid_now(promo):
        await message.answer(
            "❌ Этот промокод недействителен или истёк.",
            reply_markup=kb_back
        )
        return

    claimed = await db_claim_promo(message.from_user.id, promo["id"])
    await state.clear()

    if not claimed:
        await message.answer(
            f"ℹ️ Промокод <code>{escape(promo['code'])}</code> уже есть в вашем профиле.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎟️ Мои промокоды", callback_data="my_promos")],
                [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile")],
            ])
        )
        return

    await message.answer(
        f"✅ Промокод <code>{escape(promo['code'])}</code> добавлен!\n\n"
        f"🎮 Игра: {escape(promo['game'])}\n"
        f"📦 Товар: {escape(promo['product_title'])}\n"
        f"💰 Цена по промокоду: <b>{promo['promo_price']}₽</b>\n"
        f"📅 Срок: {_fmt_promo_dates(promo)}\n\n"
        "Найдите его в разделе <b>«Мои промокоды»</b> и воспользуйтесь предложением!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎟️ Мои промокоды", callback_data="my_promos")],
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile")],
        ])
    )


@dp.callback_query(F.data == "my_promos")
async def cb_my_promos(call: CallbackQuery) -> None:
    await call.answer()
    user_promos = await db_get_user_promos(call.from_user.id)

    if not user_promos:
        await send_or_edit(
            call,
            "🎟️ <b>Мои промокоды</b>\n\n"
            "У вас пока нет промокодов.\n"
            "Нажмите «Ввести промокод», чтобы добавить.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Ввести промокод", callback_data="enter_promo")],
                [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile")],
            ])
        )
        return

    rows: list[list[InlineKeyboardButton]] = []
    for up in user_promos:
        used = up.get("used_at") is not None
        valid = _promo_is_valid_now(up) and not used
        if used:
            icon = "✔️"
        elif valid:
            icon = "✅"
        else:
            icon = "🔴"
        label = f"{icon} {up['code']} — {up['product_title']} ({up['promo_price']}₽)"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"promo_detail:{up['promo_id']}")])

    rows.append([InlineKeyboardButton(text="✏️ Ввести промокод", callback_data="enter_promo")])
    rows.append([InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile")])

    await send_or_edit(
        call,
        "🎟️ <b>Мои промокоды</b>\n\n"
        "✅ — доступен  |  ✔️ — использован  |  🔴 — недействителен\n\n"
        "Нажмите на промокод, чтобы посмотреть детали.",
        InlineKeyboardMarkup(inline_keyboard=rows)
    )


@dp.callback_query(F.data.startswith("promo_detail:"))
async def cb_promo_detail(call: CallbackQuery) -> None:
    await call.answer()
    try:
        promo_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        return

    promo = await db_get_promo_by_id(promo_id)
    if not promo:
        await call.answer("Промокод не найден.", show_alert=True)
        return

    user_promos = await db_get_user_promos(call.from_user.id)
    user_promo = next((up for up in user_promos if up["promo_id"] == promo_id), None)

    if not user_promo:
        await call.answer("Этот промокод не принадлежит вам.", show_alert=True)
        return

    used = user_promo.get("used_at") is not None
    valid_now = _promo_is_valid_now(promo)
    dates_str = _fmt_promo_dates(promo)

    text = (
        f"<b>🎟️ Промокод: <code>{escape(promo['code'])}</code></b>\n\n"
        f"🎮 Игра: {escape(promo['game'])}\n"
        f"📦 Товар: {escape(promo['product_title'])}\n"
        f"💰 Цена по промокоду: <b>{promo['promo_price']}₽</b>\n"
        f"📅 Срок: {dates_str}\n\n"
    )

    if used:
        text += "✔️ <b>Промокод уже использован.</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Мои промокоды", callback_data="my_promos")],
        ])
    elif not valid_now:
        text += "🔴 <b>Промокод недействителен или истёк.</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Мои промокоды", callback_data="my_promos")],
        ])
    else:
        text += "✅ <b>Промокод активен!</b> Воспользуйтесь предложением ниже."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Воспользоваться предложением", callback_data=f"use_promo_confirm:{promo_id}")],
            [InlineKeyboardButton(text="⬅️ Мои промокоды", callback_data="my_promos")],
        ])

    await send_or_edit(call, text, kb)


@dp.callback_query(F.data.startswith("use_promo_confirm:"))
async def cb_use_promo_confirm(call: CallbackQuery) -> None:
    await call.answer()
    try:
        promo_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        return

    promo = await db_get_promo_by_id(promo_id)
    if not promo:
        await call.answer("Промокод не найден.", show_alert=True)
        return

    user_promos = await db_get_user_promos(call.from_user.id)
    user_promo = next((up for up in user_promos if up["promo_id"] == promo_id), None)

    if not user_promo or user_promo.get("used_at") is not None:
        await call.answer("Промокод уже использован или недоступен.", show_alert=True)
        return

    if not _promo_is_valid_now(promo):
        await call.answer("Промокод недействителен или истёк.", show_alert=True)
        return

    balance = await db_get_balance(call.from_user.id)
    price = promo["promo_price"]

    text = (
        "<b>🛒 Подтверждение покупки по промокоду</b>\n\n"
        f"🎟️ Промокод: <code>{escape(promo['code'])}</code>\n"
        f"🎮 Игра: {escape(promo['game'])}\n"
        f"📦 Товар: {escape(promo['product_title'])}\n"
        f"💰 Сумма: <b>{price}₽</b>\n"
        f"💼 Ваш баланс: <b>{balance}₽</b>\n\n"
        "Оплата спишется с внутреннего баланса бота.\n"
        "Подтвердите покупку:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", callback_data=f"use_promo_go:{promo_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"promo_detail:{promo_id}")],
    ])
    await send_or_edit(call, text, kb)


@dp.callback_query(F.data.startswith("use_promo_go:"))
async def cb_use_promo_go(call: CallbackQuery) -> None:
    await call.answer()
    try:
        promo_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        return

    promo = await db_get_promo_by_id(promo_id)
    if not promo:
        await call.answer("Промокод не найден.", show_alert=True)
        return

    user_promos = await db_get_user_promos(call.from_user.id)
    user_promo = next((up for up in user_promos if up["promo_id"] == promo_id), None)

    if not user_promo or user_promo.get("used_at") is not None:
        await call.answer("Промокод уже использован или недоступен.", show_alert=True)
        return

    if not _promo_is_valid_now(promo):
        await call.answer("Промокод недействителен или истёк.", show_alert=True)
        return

    user = call.from_user
    price = promo["promo_price"]
    title = f"[Промокод {promo['code']}] {promo['game']} — {promo['product_title']}"

    ok = await db_try_charge(user.id, price)
    if not ok:
        balance = await db_get_balance(user.id)
        text = (
            "❌ <b>Недостаточно средств на балансе.</b>\n\n"
            f"Сумма заказа: {price}₽\n"
            f"Ваш баланс: {balance}₽\n\n"
            "Пополните баланс и повторите попытку."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
        ])
        await send_or_edit(call, text, kb)
        return

    order_id = await db_create_order(user.id, title, price, status="Оплачен", category="promo")
    await db_add_transaction(user.id, -price, kind="purchase", reason=f"Заказ #{order_id}: {title}")
    await db_use_promo(user.id, promo_id)
    new_balance = await db_get_balance(user.id)

    text = (
        "✅ <b>Оплата прошла успешно. Заказ принят в обработку.</b>\n\n"
        f"🧾 Номер заказа: <code>#{order_id}</code>\n"
        f"🎟️ Промокод: <code>{escape(promo['code'])}</code>\n"
        f"🎮 Игра: {escape(promo['game'])}\n"
        f"📦 Товар: {escape(promo['product_title'])}\n"
        f"💰 Сумма: <b>{price}₽</b>\n"
        f"💼 Остаток на балансе: <b>{new_balance}₽</b>\n\n"
        "С вами свяжется модератор. Вы также можете написать первым."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Связаться с модератором", callback_data=f"contact_mod:{order_id}")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="main")],
    ])
    await send_or_edit(call, text, kb)

    username = f"@{user.username}" if user.username else "—"
    admin_text = (
        f"🎟️ <b>Новый заказ по промокоду!</b>\n\n"
        f"👤 {escape(user.first_name or '?')} ({username})\n"
        f"🆔 TG ID: <code>{user.id}</code>\n"
        f"🧾 Заказ: <code>#{order_id}</code>\n"
        f"🎟️ Промокод: <code>{escape(promo['code'])}</code>\n"
        f"🎮 Игра: {escape(promo['game'])}\n"
        f"📦 Товар: {escape(promo['product_title'])}\n"
        f"💰 Сумма: <b>{price}₽</b>"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Выполнен #{order_id}", callback_data=f"mod:done:{order_id}")],
    ])
    await notify_moderator(admin_text, reply_markup=admin_kb)


# =====================================================================
# Запуск
# =====================================================================


def _acquire_single_instance_lock() -> None:
    """Не даём запустить больше одной копии бота на хосте."""
    import fcntl
    lock_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".bot.lock"
    )
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        logging.error(
            "Другая копия бота уже запущена. Завершаю текущий процесс."
        )
        raise SystemExit(0)
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    globals()["_bot_lock_file"] = lock_file


# =====================================================================
# Ответ покупателю из чата модератора
# =====================================================================


@dp.callback_query(F.data.startswith("reply_buyer:"))
async def cb_reply_buyer(call: CallbackQuery, state: FSMContext) -> None:
    """Модератор нажимает «Ответить покупателю» — бот просит написать текст."""
    if not _is_moderator(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    buyer_id = int(call.data.split(":")[1])
    await state.set_state(AdminStates.waiting_mod_reply)
    await state.update_data(mod_reply_buyer_id=buyer_id)
    await call.message.answer(
        f"✍️ Напишите сообщение покупателю (поддерживается текст и фото).\n\n"
        f"Для отмены нажмите кнопку ниже.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="mod_reply_cancel"),
        ]]),
    )
    await call.answer()


@dp.callback_query(F.data == "mod_reply_cancel")
async def cb_mod_reply_cancel(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_moderator(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text("❌ Ответ покупателю отменён.")
    await call.answer()


@dp.message(AdminStates.waiting_mod_reply)
async def msg_mod_reply(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    data = await state.get_data()
    buyer_id = int(data.get("mod_reply_buyer_id", 0))
    await state.clear()
    try:
        await bot.copy_message(
            chat_id=buyer_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.answer("✅ Сообщение отправлено покупателю.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")


# =====================================================================
# Рассылка всем пользователям (только модератор)
# =====================================================================


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    """Команда /broadcast — начать рассылку всем пользователям."""
    if not _is_moderator(message.from_user.id):
        return
    await state.set_state(AdminStates.waiting_broadcast)
    user_count = await db_users_count()
    await message.answer(
        f"📢 <b>Рассылка</b>\n\n"
        f"Всего получателей: <b>{user_count}</b> чел.\n\n"
        f"Пришлите сообщение (текст, фото, видео — любой формат).\n"
        f"Оно будет отправлено каждому пользователю бота.\n\n"
        f"Для отмены: /cancel",
        parse_mode="HTML",
    )


@dp.message(Command("cancel"), AdminStates.waiting_broadcast)
async def cmd_broadcast_cancel(message: Message, state: FSMContext) -> None:
    if not _is_moderator(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ Рассылка отменена.")


@dp.message(AdminStates.waiting_broadcast)
async def msg_broadcast(message: Message, state: FSMContext) -> None:
    """Получает сообщение от модератора и рассылает всем пользователям."""
    if not _is_moderator(message.from_user.id):
        return
    await state.clear()
    user_ids = await db_get_all_user_ids()
    sent = 0
    failed = 0
    status_msg = await message.answer(
        f"⏳ Рассылка запущена — {len(user_ids)} получателей..."
    )
    for uid in user_ids:
        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # не превышаем лимиты Telegram (20 msg/s)
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"📨 Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
    )


async def _health_server() -> None:
    """Маленький HTTP-сервер для health-check на Render Web Service."""
    from aiohttp import web

    async def handle(request: web.Request) -> web.Response:
        return web.Response(text="ok")

    port = int(os.environ.get("PORT", 8000))
    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("Health-check сервер запущен на порту %s", port)
    await asyncio.Event().wait()


async def main() -> None:
    _acquire_single_instance_lock()
    await db_init()
    logging.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.gather(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
        _health_server(),
    )


if __name__ == "__main__":
    asyncio.run(main())
