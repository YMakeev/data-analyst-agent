"""Смоук-тести інструментів на живій базі.

Мета вузька: кожен інструмент викликається і повертає ту форму, на яку
розраховує модель. Плюс окремо перевіряємо те, що на воркшопі показується
як головний аргумент — права бази не дають нічого зіпсувати.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from server.db import fetch, get_pool
from server.tools.report import save_report
from server.tools.schema import describe_table, list_tables
from server.tools.sql import run_sql
from tests.conftest import requires_db


@requires_db
def test_list_tables_returns_descriptions() -> None:
    result = list_tables()
    assert "error" not in result
    names = {t["table"] for t in result["tables"]}
    assert {"students", "lessons", "payments"} <= names
    # Опис таблиці — це те, з чого модель розуміє предметну область.
    described = [t for t in result["tables"] if t["description"]]
    assert len(described) >= 6, "майже всі таблиці мають мати COMMENT ON TABLE"


@requires_db
def test_describe_table_exposes_the_traps() -> None:
    """Пастки зі схеми мають доїжджати до моделі текстом, а не фольклором."""
    lessons = describe_table("lessons")
    status = next(c for c in lessons["columns"] if c["name"] == "status")
    assert "completed" in status["description"]

    students = describe_table("students")
    flag = next(c for c in students["columns"] if c["name"] == "is_test_account")
    assert flag["description"], "пастка з тестовими акаунтами не описана"

    assert lessons["foreign_keys"], "звʼязки не показані — модель не збере JOIN"
    assert len(lessons["sample_rows"]) == 3


@requires_db
def test_describe_unknown_table_suggests_alternatives() -> None:
    result = describe_table("lesson")
    assert "error" in result
    assert "lessons" in result["error"], "помилка має підказувати правильну назву"


@requires_db
def test_run_sql_returns_rows() -> None:
    result = run_sql("SELECT status, COUNT(*) AS n FROM lessons GROUP BY status")
    assert "error" not in result
    assert set(result["columns"]) == {"status", "n"}
    assert result["row_count"] == 4


@requires_db
def test_run_sql_limit_is_enforced_and_reported() -> None:
    result = run_sql("SELECT lesson_id FROM lessons", limit=10)
    assert result["row_count"] == 10
    assert result["truncated"] is True
    assert "note" in result, "модель має дізнатись, що результат обрізано"


@requires_db
def test_run_sql_limit_survives_inner_limit() -> None:
    """Обгортка має працювати і тоді, коли запит уже має власний LIMIT."""
    result = run_sql("SELECT lesson_id FROM lessons ORDER BY lesson_id LIMIT 3", limit=100)
    assert result["row_count"] == 3
    assert result["truncated"] is False


@requires_db
@pytest.mark.parametrize("query", ["DROP TABLE students", "DELETE FROM lessons"])
def test_destructive_queries_are_refused(query: str) -> None:
    assert "error" in run_sql(query)


@requires_db
def test_database_role_itself_refuses_writes() -> None:
    """Головний аргумент воркшопу, перевірений без участі guard.

    Йдемо в базу напряму під роллю агента. Захист має триматись на правах
    Postgres, а не на регулярних виразах у server/db.py.
    """
    with get_pool().connection() as conn:
        for sql in ("DELETE FROM lessons", "UPDATE students SET grade = 1",
                    "CREATE TABLE hack (id int)", "DELETE FROM audit_log"):
            with pytest.raises(psycopg.Error):
                with conn.transaction():
                    conn.execute(sql)


@requires_db
def test_audit_log_records_both_success_and_failure() -> None:
    before = fetch("SELECT COUNT(*) AS n FROM audit_log")[0]["n"]
    run_sql("SELECT 1 AS ok")
    run_sql("DROP TABLE students")
    after = fetch("SELECT COUNT(*) AS n FROM audit_log")[0]["n"]
    assert after == before + 2, "невдалі спроби теж мусять потрапляти в журнал"

    last = fetch("SELECT status FROM audit_log ORDER BY id DESC LIMIT 2")
    assert {r["status"] for r in last} == {"ok", "error"}


def test_save_report_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    result = save_report("<html><body><h1>Звіт</h1></body></html>", "Виручка по каналах")
    assert "error" not in result
    path = Path(result["path"])
    assert path.exists() and path.suffix == ".html"
    # Назва не латиницею не має перетворювати файл на безликий report.html,
    # інакше другий звіт затре перший.
    assert path.stem != "report"


def test_save_report_rejects_non_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    assert "error" in save_report("просто текст", "щось")


@requires_db
def test_predict_churn_scores_active_students() -> None:
    from server.tools.ml import MODEL_PATH, predict_churn

    if not MODEL_PATH.exists():
        pytest.skip("Модель не натренована: make train")

    result = predict_churn(top_n=5)
    assert "error" not in result
    assert len(result["students"]) == 5
    probs = [s["churn_probability"] for s in result["students"]]
    assert probs == sorted(probs, reverse=True), "найризикованіші мають бути першими"
    assert all(0.0 <= p <= 1.0 for p in probs)
    assert result["students"][0]["top_factors"], "без пояснення скор марний для людини"
