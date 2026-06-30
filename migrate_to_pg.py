"""
Одноразовый скрипт: переносит все данные из SQLite → Neon PostgreSQL.
Запускать ОДИН РАЗ: python telegram_shop_bot/migrate_to_pg.py
"""
import asyncio
import os

import aiosqlite
import asyncpg

SQLITE_PATH = "/home/runner/shop_data/shop.db"


async def migrate() -> None:
    pg_url = os.environ["CONNECTION_STRING"]
    print("Подключаемся к Neon...")
    pg = await asyncpg.connect(pg_url)
    sq = await aiosqlite.connect(SQLITE_PATH)
    sq.row_factory = aiosqlite.Row

    print("Создаём таблицы в PostgreSQL...")
    await pg.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id          BIGINT PRIMARY KEY,
            username       TEXT,
            first_name     TEXT,
            balance        INTEGER NOT NULL DEFAULT 0,
            is_blacklisted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at     TEXT NOT NULL
        )
    """)
    await pg.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id         SERIAL PRIMARY KEY,
            tg_id      BIGINT NOT NULL,
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
    await pg.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id         SERIAL PRIMARY KEY,
            tg_id      BIGINT NOT NULL,
            amount     INTEGER NOT NULL,
            kind       TEXT NOT NULL,
            reason     TEXT,
            created_at TEXT NOT NULL
        )
    """)
    await pg.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id            SERIAL PRIMARY KEY,
            order_id      INTEGER NOT NULL UNIQUE,
            tg_id         BIGINT NOT NULL,
            photo_file_id TEXT,
            comment       TEXT,
            created_at    TEXT NOT NULL
        )
    """)
    await pg.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            id            SERIAL PRIMARY KEY,
            code          TEXT UNIQUE NOT NULL,
            game          TEXT NOT NULL,
            product_title TEXT NOT NULL,
            promo_price   INTEGER NOT NULL,
            starts_at     TEXT,
            expires_at    TEXT,
            is_active     BOOLEAN NOT NULL DEFAULT TRUE,
            created_at    TEXT NOT NULL
        )
    """)
    await pg.execute("""
        CREATE TABLE IF NOT EXISTS user_promos (
            id         SERIAL PRIMARY KEY,
            tg_id      BIGINT NOT NULL,
            promo_id   INTEGER NOT NULL,
            claimed_at TEXT NOT NULL,
            used_at    TEXT,
            UNIQUE(tg_id, promo_id)
        )
    """)

    async def copy_table(table: str, cols: list[str], pg_query: str) -> int:
        cur = await sq.execute(f"SELECT {', '.join(cols)} FROM {table}")
        rows = await cur.fetchall()
        count = 0
        for row in rows:
            try:
                await pg.execute(pg_query, *[row[c] for c in cols])
                count += 1
            except Exception as e:
                print(f"  Пропуск строки в {table}: {e}")
        return count

    print("Переносим users...")
    n = await copy_table(
        "users",
        ["tg_id", "username", "first_name", "balance", "is_blacklisted", "created_at"],
        "INSERT INTO users (tg_id, username, first_name, balance, is_blacklisted, created_at)"
        " VALUES ($1,$2,$3,$4,$5::boolean,$6) ON CONFLICT DO NOTHING",
    )
    print(f"  {n} пользователей")

    print("Переносим orders...")
    n = await copy_table(
        "orders",
        ["id", "tg_id", "title", "price", "status", "category", "contact",
         "login_data", "login_code", "created_at"],
        "INSERT INTO orders (id, tg_id, title, price, status, category, contact,"
        " login_data, login_code, created_at)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT DO NOTHING",
    )
    print(f"  {n} заказов")

    print("Переносим transactions...")
    n = await copy_table(
        "transactions",
        ["id", "tg_id", "amount", "kind", "reason", "created_at"],
        "INSERT INTO transactions (id, tg_id, amount, kind, reason, created_at)"
        " VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
    )
    print(f"  {n} транзакций")

    print("Переносим reviews...")
    n = await copy_table(
        "reviews",
        ["id", "order_id", "tg_id", "photo_file_id", "comment", "created_at"],
        "INSERT INTO reviews (id, order_id, tg_id, photo_file_id, comment, created_at)"
        " VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
    )
    print(f"  {n} отзывов")

    print("Переносим promo_codes...")
    cur = await sq.execute("SELECT * FROM promo_codes")
    promos = await cur.fetchall()
    pcount = 0
    for p in promos:
        try:
            await pg.execute(
                "INSERT INTO promo_codes (id, code, game, product_title, promo_price,"
                " starts_at, expires_at, is_active, created_at)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::boolean,$9) ON CONFLICT DO NOTHING",
                p["id"], p["code"], p["game"], p["product_title"], p["promo_price"],
                p["starts_at"], p["expires_at"], bool(p["is_active"]), p["created_at"],
            )
            pcount += 1
        except Exception as e:
            print(f"  Пропуск promo_codes: {e}")
    print(f"  {pcount} промокодов")

    print("Переносим user_promos...")
    n = await copy_table(
        "user_promos",
        ["id", "tg_id", "promo_id", "claimed_at", "used_at"],
        "INSERT INTO user_promos (id, tg_id, promo_id, claimed_at, used_at)"
        " VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
    )
    print(f"  {n} записей user_promos")

    print("Сбрасываем sequences для SERIAL-полей...")
    for tbl, seq_col in [("orders","id"),("transactions","id"),
                          ("reviews","id"),("promo_codes","id"),("user_promos","id")]:
        await pg.execute(
            f"SELECT setval(pg_get_serial_sequence('{tbl}','{seq_col}'),"
            f" COALESCE((SELECT MAX({seq_col}) FROM {tbl}), 1))"
        )

    await pg.close()
    await sq.close()
    print("\n✅ Миграция завершена успешно!")


if __name__ == "__main__":
    asyncio.run(migrate())
