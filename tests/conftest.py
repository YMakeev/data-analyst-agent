"""Спільна підготовка тестів.

Тести, яким потрібна жива база, пропускаються з поясненням, а не падають:
учасник, який запустив pytest до `make setup`, має отримати підказку,
а не червону стіну трейсбеків.
"""

from __future__ import annotations

import pytest

from server.db import fetch


def _db_available() -> bool:
    try:
        fetch("SELECT 1 AS ok")
        return True
    except Exception:  # noqa: BLE001
        return False


DB_UP = _db_available()

requires_db = pytest.mark.skipif(
    not DB_UP,
    reason="Немає з'єднання з базою. Підніми її: make setup",
)
