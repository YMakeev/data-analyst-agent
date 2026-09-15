"""Виконання SQL — єдиний інструмент, який реально дістає дані."""

from __future__ import annotations

import os
from typing import Any

from server import audit
from server.db import SqlGuardError, friendly_db_error, run_select


def run_sql(query: str, limit: int = 0) -> dict[str, Any]:
    """Виконує SELECT-запит до бази і повертає рядки.

    Перед першим запитом до незнайомої таблиці виклич describe_table — у
    коментарях до колонок описані особливості, без яких результат буде
    неправильним (наприклад, які рядки треба виключати і які значення
    статусу означають успішну подію).

    Доступ до бази — тільки на читання. Дозволені SELECT і WITH; одна
    інструкція на виклик. Запити, що змінюють дані, схему чи права,
    не виконуються.

    Якщо результат обрізано (truncated=true), не збільшуй ліміт наосліп —
    краще додай агрегацію або фільтр, щоб рядків стало менше.

    Args:
        query: SQL-запит. Одна інструкція, без крапки з комою в середині.
        limit: максимум рядків у відповіді. 0 — взяти значення за
            замовчуванням із налаштувань сервера.
    """
    max_rows = int(os.getenv("SQL_MAX_ROWS", "1000"))
    limit = max_rows if limit <= 0 else min(limit, max_rows)

    try:
        result = run_select(query, limit)
    except SqlGuardError as exc:
        audit.log("run_sql", query=query, status="error", error=str(exc))
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        msg = friendly_db_error(exc)
        audit.log("run_sql", query=query, status="error", error=msg)
        return {"error": msg}

    audit.log(
        "run_sql",
        query=query,
        rows=result["row_count"],
        duration_ms=result["duration_ms"],
    )

    if result["truncated"]:
        result["note"] = (
            f"Показано перші {limit} рядків, у результаті їх більше. "
            f"Для точної відповіді порахуй агрегат у самому SQL."
        )
    return result
