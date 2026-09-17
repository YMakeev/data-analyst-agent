"""Перевірка інструментів на живій базі.

Кожен інструмент викликається по-справжньому й має повернути ту форму даних,
на яку розраховує модель. Якщо форма зміниться, Claude не впаде — він просто
почне відповідати гірше, і причину буде непросто знайти.

Окремо перевіряється головне твердження всього проєкту: права бази не дають
агенту нічого зіпсувати.
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
    """Список таблиць приходить разом з описами.

    Назва таблиці сама по собі мало що каже: `subscriptions` — це підписки
    на що і в якому вигляді? Опис поруч із назвою — це те, з чого Claude
    розуміє, про який бізнес ідеться, ще до першого запиту.
    """
    result = list_tables()
    assert "error" not in result
    names = {t["table"] for t in result["tables"]}
    assert {"students", "lessons", "payments"} <= names
    # Майже в кожної таблиці має бути опис: без нього модель бачить
    # лише голі назви.
    described = [t for t in result["tables"] if t["description"]]
    assert len(described) >= 6, "майже всі таблиці мають мати COMMENT ON TABLE"


@requires_db
def test_describe_table_exposes_the_traps() -> None:
    """Особливості даних доїжджають до моделі текстом.

    Знання на кшталт «тестові акаунти треба виключати» зазвичай живе в
    голові аналітика й передається усно. Тут воно записане в описі колонки
    в самій базі, і цей тест стежить, щоб опис справді доходив до моделі.

    Якщо опис загубиться, помилки не буде — Claude просто почне відповідати
    гірше, і причину знайти буде складно.
    """
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
    """Помилка підказує, як виправитись.

    Claude може звернутись до таблиці `lesson` замість `lessons`. Відповідь
    «такої таблиці немає» заганяє його в глухий кут, а «такої немає, ось
    наявні» дозволяє виправитись самому, без участі людини.

    Текст помилки — це теж інтерфейс, просто для моделі, а не для очей.
    """
    result = describe_table("lesson")
    assert "error" in result
    assert "lessons" in result["error"], "помилка має підказувати правильну назву"


@requires_db
def test_run_sql_returns_rows() -> None:
    """Звичайний запит на читання відпрацьовує й повертає дані."""
    result = run_sql("SELECT status, COUNT(*) AS n FROM lessons GROUP BY status")
    assert "error" not in result
    assert set(result["columns"]) == {"status", "n"}
    assert result["row_count"] == 4


@requires_db
def test_run_sql_limit_is_enforced_and_reported() -> None:
    """Завеликий результат обрізається, і про це сказано вголос.

    Без обмеження один необережний запит витягнув би сотні тисяч рядків.
    Але просто обрізати мало: якщо не попередити, модель вважатиме частину
    даних усіма даними й зробить висновок по шматку.
    """
    result = run_sql("SELECT lesson_id FROM lessons", limit=10)
    assert result["row_count"] == 10
    assert result["truncated"] is True
    assert "note" in result, "модель має дізнатись, що результат обрізано"


@requires_db
def test_run_sql_limit_survives_inner_limit() -> None:
    """Обмеження не ламає запит, у якому вже є своє обмеження.

    Якщо Claude сам попросив три рядки, він має отримати три, а не
    зіткнутись із помилкою через те, що обмеження наклали двічі.
    """
    result = run_sql("SELECT lesson_id FROM lessons ORDER BY lesson_id LIMIT 3", limit=100)
    assert result["row_count"] == 3
    assert result["truncated"] is False


@requires_db
@pytest.mark.parametrize("query", ["DROP TABLE students", "DELETE FROM lessons"])
def test_destructive_queries_are_refused(query: str) -> None:
    """Запити, що нищать дані, не виконуються."""
    assert "error" in run_sql(query)


@requires_db
def test_database_role_itself_refuses_writes() -> None:
    """Захист перевірений без участі перевірок у коді.

    Запити йдуть у базу напряму під тим самим користувачем, під яким працює
    агент. Якщо цей тест колись почне падати, це означатиме, що захист
    тримався на перевірках у Python, а не на правах у базі — тобто його
    насправді не було.
    """
    with get_pool().connection() as conn:
        for sql in ("DELETE FROM lessons", "UPDATE students SET grade = 1",
                    "CREATE TABLE hack (id int)", "DELETE FROM audit_log"):
            with pytest.raises(psycopg.Error):
                with conn.transaction():
                    conn.execute(sql)


@requires_db
def test_audit_log_records_both_success_and_failure() -> None:
    """У журнал потрапляють і вдалі запити, і відхилені.

    Журнал, у якому видно лише успішні звернення, майже марний: найцікавіше
    зазвичай саме те, що відхилили. Тому записуються обидва випадки.
    """
    before = fetch("SELECT COUNT(*) AS n FROM audit_log")[0]["n"]
    run_sql("SELECT 1 AS ok")
    run_sql("DROP TABLE students")
    after = fetch("SELECT COUNT(*) AS n FROM audit_log")[0]["n"]
    assert after == before + 2, "невдалі спроби теж мусять потрапляти в журнал"

    last = fetch("SELECT status FROM audit_log ORDER BY id DESC LIMIT 2")
    assert {r["status"] for r in last} == {"ok", "error"}


def test_save_report_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Звіт зберігається у файл з осмисленою назвою.

    Назва важлива більше, ніж здається: якщо всі звіти називати однаково,
    кожен наступний мовчки затре попередній.
    """
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    result = save_report("<html><body><h1>Звіт</h1></body></html>", "Виручка по каналах")
    assert "error" not in result
    path = Path(result["path"])
    assert path.exists() and path.suffix == ".html"
    # Назва українською теж має зберігатись у назві файлу, а не
    # перетворюватись на безликий report.html.
    assert path.stem != "report"


def test_save_report_rejects_non_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Замість звіту не можна підсунути звичайний текст."""
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    assert "error" in save_report("просто текст", "щось")


@requires_db
def test_predict_churn_scores_active_students() -> None:
    """Модель повертає впорядкований список з поясненнями.

    Найризикованіші мають бути зверху — інакше списком незручно
    користуватись. І біля кожного учня має стояти причина: саме число
    «ризик 0.87» людині нічого не дає, з ним неможливо нічого зробити.
    """
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
