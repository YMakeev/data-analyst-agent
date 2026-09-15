"""Тести SQL-guard.

Дві однаково важливі половини. Перша — що guard мусить відбити. Друга, про
яку зазвичай забувають, — що він НЕ мусить чіпати. Хибне спрацювання на
живому воркшопі виглядає як зламаний сервер і коштує дорожче за пропущений
небезпечний запит: справжній захист усе одно в правах ролі.
"""

from __future__ import annotations

import pytest

from server.db import SqlGuardError, check_query

MUST_REJECT = [
    "DROP TABLE students",
    "drop table students",
    "DELETE FROM lessons",
    "UPDATE students SET grade = 1",
    "INSERT INTO students VALUES (1)",
    "TRUNCATE lessons",
    "ALTER TABLE students ADD COLUMN x int",
    "GRANT ALL ON students TO analyst_ro",
    "CREATE TABLE hack (id int)",
    # Дві інструкції в одному виклику — класичний спосіб протягнути зайве.
    "SELECT 1; DROP TABLE students",
    "SELECT 1;DROP TABLE students",
    # Спроба сховати небезпечне слово за коментарем.
    "SELECT 1 /* nice */ ; DELETE FROM lessons",
    "",
    "   ",
    "-- лише коментар",
]

MUST_ALLOW = [
    "SELECT 1",
    "select * from students limit 5",
    "WITH x AS (SELECT 1 AS a) SELECT * FROM x",
    "SELECT COUNT(*) FROM lessons WHERE status = 'completed'",
    # Заборонені слова всередині рядкових літералів — не привід відмовляти.
    "SELECT * FROM subscriptions WHERE cancel_reason = 'delete account'",
    "SELECT * FROM subscriptions WHERE cancel_reason = 'drop out'",
    # Колонки, що починаються з заборонених слів.
    "SELECT created_at, updated_reason FROM students",
    # Коментарі всередині осмисленого запиту.
    "-- скільки уроків\nSELECT COUNT(*) FROM lessons",
    "SELECT COUNT(*) FROM lessons /* усі статуси */",
    # Крапка з комою в кінці — нормальна річ, її просто прибираємо.
    "SELECT 1;",
    "SELECT 1;  \n",
]


@pytest.mark.parametrize("query", MUST_REJECT)
def test_rejects_dangerous(query: str) -> None:
    with pytest.raises(SqlGuardError):
        check_query(query)


@pytest.mark.parametrize("query", MUST_ALLOW)
def test_allows_reads(query: str) -> None:
    assert check_query(query)


def test_error_message_tells_model_what_to_do() -> None:
    """Повідомлення про помилку — інтерфейс для моделі, а не для логів."""
    with pytest.raises(SqlGuardError) as exc:
        check_query("DELETE FROM lessons")
    text = str(exc.value).lower()
    assert "select" in text, "модель має зрозуміти, що робити натомість"


def test_trailing_semicolon_is_stripped() -> None:
    assert check_query("SELECT 1;") == "SELECT 1"
