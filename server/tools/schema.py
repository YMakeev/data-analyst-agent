"""Інструменти, які показують моделі, що взагалі є в базі.

Тут живе головна ідея блоку про дані: Claude не треба вчити SQL — його треба
навчити ВАШОЇ схеми. Коментарі до колонок з db/init/01_schema.sql віддаються
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
    """
    try:
        tables = fetch(_TABLES_SQL)
    except Exception as exc:  # noqa: BLE001
        audit.log("list_tables", status="error", error=str(exc))
        return {"error": friendly_db_error(exc)}

    out = []
    for t in tables:
        # reltuples — оцінка планувальника; для рядків беремо точне число,
        # бо різниця в кілька відсотків плутає і модель, і людину.
        exact = fetch(f'SELECT COUNT(*) AS n FROM "{t["table_name"]}"')[0]["n"]
        out.append({
            "table": t["table_name"],
            "rows": exact,
            "description": t["description"] or "",
        })

    audit.log("list_tables", rows=len(out))
    return {
        "tables": out,
        "hint": "Далі виклич describe_table для тих таблиць, які потрібні "
                "для відповіді — там описані особливості колонок.",
    }


def describe_table(table: str) -> dict[str, Any]:
    """Показує колонки таблиці: типи, зв'язки, приклади рядків і — найголовніше —
    коментарі, де описані особливості даних.

    Читай коментарі уважно: у них зафіксовані правила, без яких запит дасть
    правдоподібну, але неправильну цифру (які значення статусу означають
    успіх, які рядки треба виключати, що означає NULL у конкретній колонці).

    Args:
        table: назва таблиці зі списку list_tables.
    """
    known = _known_tables()
    if table not in known:
        msg = f"Таблиці '{table}' не існує. Доступні: {', '.join(known)}."
        audit.log("describe_table", query=table, status="error", error=msg)
        return {"error": msg}

    try:
        columns = fetch(_COLUMNS_SQL, (table,))
        fks = fetch(_FK_SQL, (table,))
        sample = fetch(f'SELECT * FROM "{table}" LIMIT 3')
        table_desc = next(
            (t["description"] for t in fetch(_TABLES_SQL) if t["table_name"] == table),
            None,
        )
    except Exception as exc:  # noqa: BLE001
        audit.log("describe_table", query=table, status="error", error=str(exc))
        return {"error": friendly_db_error(exc)}

    audit.log("describe_table", query=table, rows=len(columns))
    return {
        "table": table,
        "description": table_desc or "",
        "columns": [
            {
                "name": c["column_name"],
                "type": c["data_type"],
                "nullable": c["nullable"],
                "description": c["description"] or "",
            }
            for c in columns
        ],
        "foreign_keys": [f["definition"] for f in fks],
        "sample_rows": sample,
    }
