"""Доступ до бази і захист SQL.

Два рівні захисту, і важливо розуміти, що вони різні за призначенням.

1. Guard у цьому файлі — ЗРУЧНІСТЬ. Він ловить очевидно шкідливий запит
   і повертає моделі зрозумілу помилку замість сирого винятку Postgres.
   Будь-який такий парсер у принципі обходиться.

2. Права ролі analyst_ro у db/init/02_roles.sql — ЗАХИСТ. Права на запис
   просто немає, тому навіть запит, що проліз повз guard, нічого не зробить.

Плюс кожен запит виконується в READ ONLY транзакції з таймаутом — третій
шар, який діє, навіть якщо перші два переписали.
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

    Налаштування розраховані на те, що база може бути не локальною.
    Хмарні бази (Neon, Supabase, Aurora Serverless) вимикають обчислення
    після кількох хвилин без запитів і закривають невикористовувані
    з'єднання. Без перевірки перед видачею пул віддав би вже мертве
    з'єднання, і перший запит після паузи впав би з
    'connection already closed'.
    """
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError(
                "Не задано DATABASE_URL. Скопіюй .env.example у .env "
                "(cp .env.example .env) і перезапусти Claude Desktop."
            )
        _pool = ConnectionPool(
            dsn,
            min_size=1,
            max_size=4,
            open=True,
            timeout=15,
            # Перевіряти з'єднання перед видачею. Коштує один SELECT 1,
            # рятує від падіння після простою.
            check=ConnectionPool.check_connection,
            # Не тримати ідлові з'єднання довше, ніж їх терпить хмара.
            max_idle=120.0,
            kwargs={
                # Прокинути мережеву проблему за 10 с, а не висіти хвилину.
                "connect_timeout": 10,
                # Вимкнути автоматичні prepared statements. Вони ламаються
                # об pgbouncer у transaction mode, а саме він стоїть за
                # pooler-ендпоінтами хмарних баз. Пул у нас свій, тож
                # виграшу від них майже немає, а сюрприз був би дорогий.
                "prepare_threshold": None,
                # Помітити обрив каналу, а не чекати вічно на відповідь.
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
            },
        )
    return _pool


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
    """Перевіряє запит і повертає його очищений від хвостової крапки з комою.

    Кидає SqlGuardError з текстом, написаним для моделі: помилка має
    пояснювати, ЩО зробити інакше, а не просто констатувати відмову.
    """
    if not sql or not sql.strip():
        raise SqlGuardError("Порожній запит.")

    probe = _strip_noise(sql).strip().rstrip(";").strip()
    if not probe:
        raise SqlGuardError("У запиті немає нічого, крім коментарів.")

    if ";" in probe:
        raise SqlGuardError(
            "Кілька SQL-інструкцій в одному виклику заборонено. "
            "Виконай їх окремими викликами run_sql."
        )

    head = probe.split(None, 1)[0].lower()
    if head not in ("select", "with"):
        raise SqlGuardError(
            f"Дозволені лише запити на читання: SELECT або WITH. "
            f"Отримано '{head.upper()}'. Ця база підключена в режимі "
            f"тільки для читання."
        )

    lowered = probe.lower()
    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", lowered):
            raise SqlGuardError(
                f"У запиті є заборонене слово '{word.upper()}'. "
                f"Доступ до бази — тільки на читання: змінювати дані, "
                f"схему або права не можна. Перепиши запит як SELECT."
            )

    return sql.strip().rstrip(";").strip()


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

    Ліміт накладається обгорткою, а не дописуванням LIMIT у кінець: так він
    працює і для запитів, які вже мають власний LIMIT чи ORDER BY.
    Запитуємо на один рядок більше, ніж треба, — щоб чесно сказати моделі,
    що результат обрізано.
    """
    clean = check_query(sql)
    timeout = int(os.getenv("SQL_TIMEOUT_SECONDS", "15"))
    wrapped = f"SELECT * FROM (\n{clean}\n) AS _q LIMIT {limit + 1}"

    started = time.perf_counter()
    with get_pool().connection() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute(f"SET LOCAL statement_timeout = '{timeout}s'")
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(wrapped)
                rows = cur.fetchall()
                columns = [d.name for d in cur.description] if cur.description else []

    duration_ms = int((time.perf_counter() - started) * 1000)
    truncated = len(rows) > limit
    rows = rows[:limit]

    return {
        "columns": columns,
        "rows": [jsonable(r) for r in rows],
        "row_count": len(rows),
        "truncated": truncated,
        "duration_ms": duration_ms,
    }


def fetch(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Службовий запит самого сервера (схема, метадані). Guard не потрібен."""
    with get_pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return [jsonable(r) for r in cur.fetchall()]


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
        # Причини різні, і поради до них теж різні. Порада «підніми контейнер»
        # у відповідь на невірний пароль веде діагностику зовсім не туди —
        # особливо в хмарі, де ніякого контейнера з базою немає взагалі.
        text = str(exc).strip()
        low = text.lower()
        if "password" in low or "authentication" in low or "role" in low:
            hint = (
                "База відповіла, але не пустила: невірний користувач або пароль. "
                "Перевір DATABASE_URL — там має бути рядок ролі analyst_ro, "
                "а не той, що хмара видала за замовчуванням."
            )
        elif "does not exist" in low and "database" in low:
            hint = "Такої бази не існує. Перевір назву бази в кінці DATABASE_URL."
        elif "ssl" in low:
            hint = "Хмарні бази вимагають SSL. Додай ?sslmode=require в кінець DATABASE_URL."
        elif "timeout" in low or "could not translate" in low or "could not connect" in low:
            hint = (
                "Сервер бази недосяжний: невірний хост або мережа не пускає. "
                "Локально перевір, що контейнер піднятий: docker compose up -d"
            )
        else:
            hint = "Не вдалось під'єднатись до бази."
        # Оригінальний текст лишаємо: без нього діагностика перетворюється
        # на вгадування, і це стосується і людини, і моделі.
        return f"{hint} Відповідь бази: {text.splitlines()[0]}"
    return f"Помилка бази: {exc}"
