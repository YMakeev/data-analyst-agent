"""Інструменти, які показують моделі, що взагалі є в базі.

Каркас. SQL до системних таблиць уже написаний — набирати його в кадрі
було б марною тратою хвилин. Пишемо самі інструменти.

Головна ідея цього блоку: Claude не треба вчити SQL — його треба навчити
ВАШОЇ схеми. Коментарі до колонок з db/init/01_schema.sql віддаються моделі
дослівно, і саме вони перетворюють правдоподібну відповідь на правильну.
"""

from __future__ import annotations

from typing import Any

from server import audit
from server.db import fetch, friendly_db_error

_TABLES_SQL = """
SELECT c.relname                                   AS table_name,
       obj_description(c.oid, 'pg_class')          AS description,
       c.reltuples::bigint                         AS approx_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname
"""

_COLUMNS_SQL = """
SELECT a.attname                                             AS column_name,
       format_type(a.atttypid, a.atttypmod)                  AS data_type,
       NOT a.attnotnull                                      AS nullable,
       col_description(a.attrelid, a.attnum)                 AS description
FROM pg_attribute a
WHERE a.attrelid = %s::regclass
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY a.attnum
"""

_FK_SQL = """
SELECT con.conname                                    AS name,
       pg_get_constraintdef(con.oid)                  AS definition
FROM pg_constraint con
WHERE con.conrelid = %s::regclass AND con.contype = 'f'
ORDER BY con.conname
"""


def _known_tables() -> list[str]:
    return [r["table_name"] for r in fetch(_TABLES_SQL)]


def list_tables() -> dict[str, Any]:
    """Показує всі таблиці бази з коротким описом і кількістю рядків.

    Виклич це першим, коли питання стосується даних: без назв таблиць
    будь-який SQL буде вгадуванням. Опис таблиці пояснює, що в ній лежить.
    Точну структуру колонок дає describe_table.

    TODO (8-12 хв):
      1. виконати _TABLES_SQL;
      2. для кожної таблиці взяти точну кількість рядків через COUNT(*)
         (reltuples — лише оцінка планувальника, різниця у відсотках
         плутає і модель, і людину);
      3. повернути список {table, rows, description};
      4. записати виклик у журнал: audit.log("list_tables", rows=...).

    Спробуй спершу написати докстрінг так: '''Список таблиць.''' — і
    подивись, як зміниться поведінка Claude. Докстрінг і є промпт.
    """
    raise NotImplementedError("Пишемо на воркшопі, 8-12 хв")


def describe_table(table: str) -> dict[str, Any]:
    """Показує колонки таблиці: типи, зв'язки, приклади рядків і — найголовніше —
    коментарі, де описані особливості даних.

    Читай коментарі уважно: у них зафіксовані правила, без яких запит дасть
    правдоподібну, але неправильну цифру (які значення статусу означають
    успіх, які рядки треба виключати, що означає NULL у конкретній колонці).

    Args:
        table: назва таблиці зі списку list_tables.

    TODO (15-19 хв):
      1. перевірити, що така таблиця існує (_known_tables). Якщо ні —
         повернути помилку зі СПИСКОМ наявних: модель тоді виправиться
         сама, без участі людини;
      2. зібрати _COLUMNS_SQL, _FK_SQL і три приклади рядків;
      3. повернути table, description, columns, foreign_keys, sample_rows.
    """
    raise NotImplementedError("Пишемо на воркшопі, 15-19 хв")
