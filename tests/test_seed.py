"""Інваріанти згенерованих даних.

Це не тести коду — це тести ДАНИХ. Якщо генератор зіпсується, воркшоп
розсиплеться не на етапі імпорту, а посеред демо, коли Claude видасть
беззмістовну відповідь. Дешевше спіймати тут.

Окремо перевіряємо, що пастки зі схеми реально працюють: якщо наївний і
правильний підрахунок дають однакову цифру, кульмінаційний момент уроку
просто не відбудеться.
"""

from __future__ import annotations

from server.db import fetch
from tests.conftest import requires_db


def one(sql: str):
    return list(fetch(sql)[0].values())[0]


@requires_db
def test_tables_are_not_empty() -> None:
    for table in ("students", "tutors", "subscriptions", "lessons", "payments"):
        assert one(f"SELECT COUNT(*) FROM {table}") > 0, f"{table} порожня — запусти make seed"


@requires_db
def test_no_orphans() -> None:
    """Жодних посилань у нікуди — інакше JOIN-и в демо тихо з'їдять рядки."""
    checks = {
        "lessons -> students": """
            SELECT COUNT(*) FROM lessons l
            LEFT JOIN students s USING (student_id) WHERE s.student_id IS NULL""",
        "lessons -> subscriptions": """
            SELECT COUNT(*) FROM lessons l
            LEFT JOIN subscriptions sub USING (subscription_id)
            WHERE sub.subscription_id IS NULL""",
        "payments -> subscriptions": """
            SELECT COUNT(*) FROM payments p
            LEFT JOIN subscriptions sub USING (subscription_id)
            WHERE sub.subscription_id IS NULL""",
    }
    for name, sql in checks.items():
        assert one(sql) == 0, f"є сироти: {name}"


@requires_db
def test_all_four_lesson_statuses_present() -> None:
    """Пастка з чотирма статусами працює, лише якщо всі чотири є в даних."""
    rows = fetch("SELECT DISTINCT status FROM lessons")
    statuses = {r["status"] for r in rows}
    assert statuses == {
        "completed", "cancelled_by_parent", "cancelled_by_tutor", "no_show"
    }


@requires_db
def test_completed_share_is_realistic() -> None:
    share = float(one("""
        SELECT COUNT(*) FILTER (WHERE status = 'completed')::numeric / COUNT(*)
        FROM lessons"""))
    assert 0.7 < share < 0.92, f"частка проведених уроків неправдоподібна: {share:.2f}"


@requires_db
def test_lesson_count_trap_is_material() -> None:
    """Наївний підрахунок має помилятись помітно, інакше демо не спрацює."""
    naive = one("""
        SELECT COUNT(*) FROM lessons
        WHERE scheduled_at > now() - interval '30 days'""")
    correct = one("""
        SELECT COUNT(*) FROM lessons l JOIN students s USING (student_id)
        WHERE l.scheduled_at > now() - interval '30 days'
          AND l.status = 'completed' AND s.is_test_account = false""")
    assert correct > 0
    overstatement = naive / correct - 1
    assert overstatement > 0.15, (
        f"наївний підрахунок завищує лише на {overstatement:.1%} — "
        f"пастка непомітна, демо не спрацює"
    )


@requires_db
def test_revenue_trap_is_material() -> None:
    naive = float(one("""
        SELECT SUM(amount_usd) FROM payments
        WHERE paid_at > now() - interval '90 days'"""))
    correct = float(one("""
        SELECT SUM(p.amount_usd) FROM payments p JOIN students s USING (student_id)
        WHERE p.paid_at > now() - interval '90 days'
          AND p.status = 'succeeded' AND s.is_test_account = false"""))
    assert naive / correct - 1 > 0.05


@requires_db
def test_test_accounts_are_anomalous() -> None:
    """Коментар до колонки обіцяє аномалію — дані мусять її підтверджувати."""
    row = fetch("""
        SELECT s.is_test_account,
               COUNT(l.lesson_id)::numeric / COUNT(DISTINCT s.student_id) AS per_student
        FROM students s LEFT JOIN lessons l USING (student_id)
        GROUP BY 1 ORDER BY 1""")
    normal = float(row[0]["per_student"])
    test = float(row[1]["per_student"])
    assert test > normal * 2, "тестові акаунти мають бути помітно активнішими"


@requires_db
def test_active_subscriptions_exist() -> None:
    """Без активних підписок predict_churn нічого не покаже."""
    active = one("""
        SELECT COUNT(*) FROM subscriptions sub JOIN students s USING (student_id)
        WHERE sub.ended_at IS NULL AND s.is_test_account = false""")
    assert active > 500, f"активних підписок замало: {active}"


@requires_db
def test_churn_signal_exists() -> None:
    """Ті, хто скоро піде, мусять поводитись інакше — інакше моделі нічого вчити."""
    row = fetch("""
        WITH last28 AS (
            SELECT sub.subscription_id,
                   sub.ended_at IS NOT NULL AS churned,
                   COUNT(*) FILTER (WHERE l.status = 'no_show')::numeric
                       / NULLIF(COUNT(*), 0) AS no_show_rate
            FROM subscriptions sub
            JOIN students s USING (student_id)
            LEFT JOIN lessons l ON l.subscription_id = sub.subscription_id
                 AND l.scheduled_at > COALESCE(sub.ended_at, now()) - interval '28 days'
            WHERE s.is_test_account = false
            GROUP BY 1, 2
        )
        SELECT churned, AVG(no_show_rate) AS rate FROM last28
        WHERE no_show_rate IS NOT NULL GROUP BY 1 ORDER BY 1""")
    stayed = float(row[0]["rate"])
    left = float(row[1]["rate"])
    assert left > stayed * 1.3, (
        f"пропуски в тих, хто пішов ({left:.3f}), майже як у тих, хто лишився "
        f"({stayed:.3f}) — сигналу для моделі немає"
    )
