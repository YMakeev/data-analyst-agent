"""Журнал звернень агента до бази.

Пишеться на кожен виклик інструмента — і успішний, і невдалий. Локально це
здається зайвим, але саме з цієї таблиці все набуває сенсу, коли сервер
задеплоєний на команду: видно, хто і що дивився, і чому о 19:40 база
раптом просіла.

Права дозволяють агенту лише INSERT — без UPDATE і DELETE. Журнал, який
можна підчистити, журналом не є.

Збій запису в журнал ніколи не валить сам інструмент: користувач не має
втратити відповідь через те, що не записався лог.
"""

from __future__ import annotations

import sys

from server.db import get_pool

_INSERT = """
INSERT INTO audit_log (tool, query, rows_returned, duration_ms, status, error)
VALUES (%s, %s, %s, %s, %s, %s)
"""


def log(
    tool: str,
    *,
    query: str | None = None,
    rows: int | None = None,
    duration_ms: int | None = None,
    status: str = "ok",
    error: str | None = None,
) -> None:
    try:
        with get_pool().connection() as conn:
            conn.execute(_INSERT, (tool, query, rows, duration_ms, status, error))
    except Exception as exc:  # noqa: BLE001 — лог не має права зламати інструмент
        print(f"[audit] не вдалось записати: {exc}", file=sys.stderr)
