"""Перевірки самих даних, а не коду.

Зіпсовані дані не ламають програму — вона працює, просто відповіді стають
беззмістовними. Помітити це важко: цифра виглядає правдоподібно, і довіряти
їй перестаєш надто пізно. Тому інваріанти даних перевіряються так само, як
поведінка коду.

Це корисно перенести до себе. Коли агент ходить у вашу базу, найдорожчі
помилки виглядають не як падіння, а як тихо неправильна відповідь.
"""

from __future__ import annotations

from server.db import fetch
from tests.conftest import requires_db


def one(sql: str):
    return list(fetch(sql)[0].values())[0]


@requires_db
def test_tables_are_not_empty() -> None:
    """У кожній таблиці є хоч щось.

    Найдурніша й найчастіша ситуація: база створена, підключення працює,
    а всередині порожньо. Агент тоді відповідає «даних немає», і людина
    півгодини шукає помилку в налаштуваннях замість того, щоб просто
    заповнити базу.
    """
    for table in ("students", "tutors", "subscriptions", "lessons", "payments"):
        assert one(f"SELECT COUNT(*) FROM {table}") > 0, f"{table} порожня — запусти make seed"


@requires_db
def test_no_orphans() -> None:
    """Кожен запис посилається на когось існуючого.

    Урок належить учневі, платіж належить підписці. Якщо в уроці записано
    учня, якого в базі немає, — це «посилання в нікуди».

    Чим це небезпечно: коли рахують «уроки по учнях», такі уроки зникають
    із підрахунку **мовчки**. Ніякої помилки не буде, просто цифра вийде
    меншою за правду, і зрозуміти це з самої відповіді неможливо.
    """
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
    """Усі чотири статуси уроку справді трапляються в даних.

    Урок може бути проведений, скасований батьком, скасований репетитором
    або пропущений без попередження. Якщо якогось із варіантів у даних
    немає, зникає й привід розбиратись, чим вони відрізняються — а саме на
    цьому найлегше помилитись, рахуючи «скільки уроків ми провели».
    """
    rows = fetch("SELECT DISTINCT status FROM lessons")
    statuses = {r["status"] for r in rows}
    assert statuses == {
        "completed", "cancelled_by_parent", "cancelled_by_tutor", "no_show"
    }


@requires_db
def test_completed_share_is_realistic() -> None:
    """Проведених уроків більшість, але не всі.

    Якщо проведено 100% — зривів у даних немає, і вчитись розрізняти
    статуси ні на чому. Якщо менше 70% — сервіс виглядає непрацездатним,
    і будь-які висновки з таких даних будуть дивними.
    """
    share = float(one("""
        SELECT COUNT(*) FILTER (WHERE status = 'completed')::numeric / COUNT(*)
        FROM lessons"""))
    assert 0.7 < share < 0.92, f"частка проведених уроків неправдоподібна: {share:.2f}"


@requires_db
def test_lesson_count_trap_is_material() -> None:
    """Наївний підрахунок має помилятись помітно.

    У даних навмисно закладені пастки: якщо не виключити тестові акаунти й
    не відфільтрувати статус уроку, цифра виходить завищеною. Сенс має лише
    відчутна різниця — інакше ніхто не помітить власної помилки.
    """
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
        f"пастка стала непомітною"
    )


@requires_db
def test_revenue_trap_is_material() -> None:
    """Порахувати виручку «в лоб» помітно дорожче за правду.

    У платежах є не лише успішні списання, а й невдалі та повернення
    грошей. Якщо скласти всі суми підряд, виручка вийде завищеною.
    Різниця має бути достатньою, щоб її було видно неозброєним оком.
    """
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
    """Тестові акаунти справді поводяться неприродно.

    В описі таблиці написано, що внутрішні тестові акаунти треба виключати
    з підрахунків, бо в них аномально багато уроків. Опис має відповідати
    дійсності: якщо насправді вони такі самі, як звичайні учні, попередження
    в описі перетворюється на шум, який усі ігнорують.
    """
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
    """Є достатньо учнів, які займаються прямо зараз.

    Модель оцінює ризик піти для тих, хто ще з нами. Якщо таких у базі
    майже немає, оцінювати нікого, і інструмент поверне порожній список.
    """
    active = one("""
        SELECT COUNT(*) FROM subscriptions sub JOIN students s USING (student_id)
        WHERE sub.ended_at IS NULL AND s.is_test_account = false""")
    assert active > 500, f"активних підписок замало: {active}"


@requires_db
def test_churn_signal_exists() -> None:
    """Ті, хто зрештою пішов, поводились інакше, ніж ті, хто лишився.

    Модель не вміє передбачати нізвідки: вона шукає різницю в поведінці.
    Тут перевіряється найпростіший її прояв — учні, які згодом пішли,
    пропускали уроки частіше за тих, хто лишився.

    Якщо цієї різниці немає, модель нічого корисного не вивчить, скільки її
    не тренуй: у даних просто немає сигналу.
    """
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
