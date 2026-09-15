"""Спільна підготовка тестів.

Тести, яким потрібна жива база, пропускаються з поясненням, а не падають:
учасник, який запустив pytest до `make setup`, має отримати підказку,
а не червону стіну трейсбеків.

Окремо розрізняємо дві зовсім різні причини «не працює»:
бази немає — це проблема оточення; функція ще не написана — це нормальний
стан гілки workshop-start посеред воркшопу. Підказка має бути різна.
"""

from __future__ import annotations

import pytest

from server.db import fetch


def _db_state() -> tuple[bool, str]:
    try:
        fetch("SELECT 1 AS ok")
        return True, ""
    except NotImplementedError:
        return False, (
            "Функції доступу до бази ще не написані — це очікувано на гілці "
            "workshop-start. Тест почне проходити, коли допишемо get_pool і fetch."
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Немає з'єднання з базою ({type(exc).__name__}). Підніми її: make setup"


DB_UP, _REASON = _db_state()

requires_db = pytest.mark.skipif(not DB_UP, reason=_REASON)
