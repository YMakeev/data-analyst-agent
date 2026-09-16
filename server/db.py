"""Доступ до бази і захист SQL.

Каркас. Дві функції пишемо разом на воркшопі.

Про захист варто розуміти головне ще до того, як почнемо писати код.
Тут буде ДВА рівні, і вони різні за призначенням:

1. Guard у цьому файлі — ЗРУЧНІСТЬ. Він ловить очевидно шкідливий запит
   і повертає моделі зрозумілу помилку замість сирого винятку Postgres.
   Будь-який такий парсер у принципі обходиться.

2. Права ролі analyst_ro у db/init/02_roles.sql — ЗАХИСТ. Права на запис
   просто немає, тому навіть запит, що проліз повз guard, нічого не зробить.

Побачити другий рівень на власні очі:  python scripts/prove_readonly.py
"""

from __future__ import annotations

import os
import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Конфіг читаємо тут, а не лише в main.py: тести й скрипти імпортують db
# напряму, і їм теж потрібен .env.
load_dotenv()

_pool: ConnectionPool | None = None


class SqlGuardError(Exception):
    """Запит відхилено до того, як він дійшов до бази."""


def get_pool() -> ConnectionPool:
    """Пул з'єднань із базою.

    TODO (8-12 хв): взяти DSN зі змінної DATABASE_URL і створити
    ConnectionPool. Якщо змінної немає — кинути зрозумілу помилку:
    учасник має дізнатись, що треба зробити `cp .env.example .env`,
    а не побачити KeyError.
    """
    raise NotImplementedError("Пишемо на воркшопі, 8-12 хв")


# ------------------------------------------------------------------ guard --

# Все, що змінює дані або схему. Перевіряється як ціле слово, тому колонка
# created_at не тригерить CREATE.
FORBIDDEN = [
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "comment", "copy", "vacuum", "analyze", "reindex",
    "cluster", "call", "do", "execute", "prepare", "listen", "notify",
    "lock", "refresh", "import", "merge",
]

_COMMENT_LINE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_LIT = re.compile(r"'(?:[^']|'')*'")
_DOLLAR_QUOTED = re.compile(r"\$\$.*?\$\$", re.DOTALL)


def _strip_noise(sql: str) -> str:
    """Прибирає коментарі й рядкові літерали перед перевіркою ключових слів.

    Без цього запит `WHERE cancel_reason = 'delete account'` був би хибно
    відхилений: слово DELETE усередині тексту — це дані, а не команда.
    """
    sql = _COMMENT_BLOCK.sub(" ", sql)
    sql = _COMMENT_LINE.sub(" ", sql)
    sql = _DOLLAR_QUOTED.sub(" '' ", sql)
    sql = _STRING_LIT.sub(" '' ", sql)
    return sql


def check_query(sql: str) -> str:
    """Перевіряє запит і повертає його без хвостової крапки з комою.

    TODO (20-24 хв). Що має відбутись:
      1. порожній запит — відмова;
      2. після _strip_noise у запиті не лишилось ";" (одна інструкція);
      3. запит починається з SELECT або WITH;
      4. немає жодного слова зі списку FORBIDDEN (як ЦІЛОГО слова).

    Текст помилки пиши для моделі, а не для логів: він має пояснювати,
    ЩО зробити інакше. Модель уміє виправлятись — якщо їй сказати, як.

    Що саме має відбиватись і що точно НЕ має — у tests/test_sql_guard.py.
    Це найзручніша специфікація: запусти `make test` і дивись, що червоне.
    """
    raise NotImplementedError("Пишемо на воркшопі, 20-24 хв")


# ----------------------------------------------------------- серіалізація --

def jsonable(value: Any) -> Any:
    """Приводить типи Postgres до того, що Claude побачить як текст."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    return value


# ------------------------------------------------------------- виконання --

def run_select(sql: str, limit: int) -> dict[str, Any]:
    """Виконує перевірений SELECT у READ ONLY транзакції з таймаутом.

    TODO (15-19 хв). Порядок дій:
      1. check_query(sql)  — поки не написаний, на цьому кроці впаде;
      2. обгорнути запит:  SELECT * FROM ( <запит> ) AS _q LIMIT n+1
         Чому обгортка, а не дописування LIMIT у кінець: так ліміт працює
         і для запитів, які вже мають власний LIMIT або ORDER BY.
         Чому n+1: щоб чесно сказати моделі, що результат обрізано.
      3. виконати в транзакції з SET TRANSACTION READ ONLY
         і SET LOCAL statement_timeout;
      4. повернути columns, rows, row_count, truncated, duration_ms.
    """
    raise NotImplementedError("Пишемо на воркшопі, 15-19 хв")


def fetch(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Службовий запит самого сервера (схема, метадані). Guard не потрібен.

    TODO (8-12 хв): взяти з'єднання з пулу, виконати запит із
    row_factory=dict_row і повернути список словників, пропущений
    через jsonable().
    """
    raise NotImplementedError("Пишемо на воркшопі, 8-12 хв")


def friendly_db_error(exc: Exception) -> str:
    """Перетворює виняток Postgres на підказку, з якої модель може виправитись.

    Повідомлення про помилку — це теж інтерфейс для моделі. Трейсбек їй
    не допоможе, а речення 'такої таблиці немає, ось наявні' — допоможе.
    """
    if isinstance(exc, psycopg.errors.InsufficientPrivilege):
        return (
            "Відмовлено в доступі: користувач бази має право лише читати. "
            "Змінити дані, схему або права неможливо — і це зроблено навмисно."
        )
    if isinstance(exc, psycopg.errors.UndefinedTable):
        try:
            names = [r["table_name"] for r in fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )]
            return f"Такої таблиці немає. Доступні: {', '.join(names)}."
        except Exception:
            return "Такої таблиці немає. Виклич list_tables, щоб побачити наявні."
    if isinstance(exc, psycopg.errors.UndefinedColumn):
        return (
            f"{exc}. Виклич describe_table для цієї таблиці, щоб побачити "
            f"справжні назви колонок."
        )
    if isinstance(exc, psycopg.errors.QueryCanceled):
        return (
            f"Запит перевищив ліміт часу "
            f"({os.getenv('SQL_TIMEOUT_SECONDS', '15')} с). Додай фільтр за "
            f"датою або агрегацію, щоб він обробляв менше рядків."
        )
    if isinstance(exc, psycopg.OperationalError):
        return (
            "Немає з'єднання з базою. Перевір, що контейнер запущений: "
            "docker compose up -d"
        )
    return f"Помилка бази: {exc}"
