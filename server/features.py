"""Ознаки churn-моделі — одне джерело правди для тренування і для передбачення.

Той самий SQL використовують і ml/train.py, і інструмент predict_churn.
Якщо ознаки рахувати у двох місцях, вони рано чи пізно розійдуться, і модель
у проді почне бачити не те, на чому вчилась. Це найпоширеніша помилка
в ML-сервісах, тому в навчальному проєкті вона винесена в окремий файл явно.

Усі ознаки рахуються станом на дату зрізу :as_of і дивляться ТІЛЬКИ в минуле.
Жодна не може зазирнути вперед — інакше модель показала б чудові метрики
на тесті й нічого не варта була б у житті.
"""

from __future__ import annotations

FEATURE_COLUMNS = [
    "tenure_days",
    "lessons_completed_28d",
    "no_show_rate_28d",
    "cancel_rate_28d",
    "avg_rating_28d",
    "rated_share_28d",
    "homework_rate_28d",
    "days_since_last_lesson",
    "tutor_changes_90d",
    "failed_payments_90d",
    "support_tickets_90d",
    "plan_gap_28d",
    "plan_code",
    "lessons_per_week",
]

# Людські назви — щоб пояснення моделі читалось бізнесом, а не дата-сайєнтистом.
FEATURE_LABELS = {
    "tenure_days": "днів з початку підписки",
    "lessons_completed_28d": "проведено уроків за 28 днів",
    "no_show_rate_28d": "частка пропусків без попередження за 28 днів",
    "cancel_rate_28d": "частка скасувань батьками за 28 днів",
    "avg_rating_28d": "середня оцінка уроків за 28 днів",
    "rated_share_28d": "частка оцінених уроків за 28 днів",
    "homework_rate_28d": "частка виконаних домашніх завдань за 28 днів",
    "days_since_last_lesson": "днів з останнього проведеного уроку",
    "tutor_changes_90d": "різних репетиторів за 90 днів",
    "failed_payments_90d": "невдалих списань за 90 днів",
    "support_tickets_90d": "звернень у підтримку за 90 днів",
    "plan_gap_28d": "розрив між планом і фактом за уроками",
    "plan_code": "тип плану",
    "lessons_per_week": "уроків на тиждень за планом",
}

# Активні підписки на дату зрізу, без тестових акаунтів.
_BASE = """
    SELECT sub.subscription_id,
           sub.student_id,
           sub.plan,
           sub.lessons_per_week,
           sub.started_at,
           EXTRACT(EPOCH FROM (%(as_of)s::timestamp - sub.started_at)) / 86400.0
               AS tenure_days
    FROM subscriptions sub
    JOIN students s ON s.student_id = sub.student_id
    WHERE s.is_test_account = false
      AND sub.started_at <= %(as_of)s::timestamp
      AND (sub.ended_at IS NULL OR sub.ended_at > %(as_of)s::timestamp)
"""

FEATURE_SQL = f"""
WITH base AS ({_BASE}),

win28 AS (
    SELECT b.subscription_id,
           COUNT(l.lesson_id) FILTER (WHERE l.status = 'completed')           AS done,
           COUNT(l.lesson_id) FILTER (WHERE l.status = 'no_show')             AS no_show,
           COUNT(l.lesson_id) FILTER (WHERE l.status = 'cancelled_by_parent') AS cancelled,
           COUNT(l.lesson_id)                                                 AS scheduled,
           AVG(l.rating)                                                      AS avg_rating,
           COUNT(l.rating)                                                    AS rated,
           AVG(CASE WHEN l.homework_done THEN 1.0 ELSE 0.0 END)
               FILTER (WHERE l.status = 'completed')                          AS homework_rate
    FROM base b
    LEFT JOIN lessons l
           ON l.subscription_id = b.subscription_id
          AND l.scheduled_at >  %(as_of)s::timestamp - interval '28 days'
          AND l.scheduled_at <= %(as_of)s::timestamp
    GROUP BY b.subscription_id
),

last_lesson AS (
    SELECT b.subscription_id, MAX(l.scheduled_at) AS last_done
    FROM base b
    LEFT JOIN lessons l
           ON l.subscription_id = b.subscription_id
          AND l.status = 'completed'
          AND l.scheduled_at <= %(as_of)s::timestamp
    GROUP BY b.subscription_id
),

win90 AS (
    SELECT b.subscription_id,
           COUNT(DISTINCT l.tutor_id) AS tutors_90d
    FROM base b
    LEFT JOIN lessons l
           ON l.subscription_id = b.subscription_id
          AND l.scheduled_at >  %(as_of)s::timestamp - interval '90 days'
          AND l.scheduled_at <= %(as_of)s::timestamp
    GROUP BY b.subscription_id
),

pay90 AS (
    SELECT b.subscription_id,
           COUNT(p.payment_id) FILTER (WHERE p.status = 'failed') AS failed_90d
    FROM base b
    LEFT JOIN payments p
           ON p.subscription_id = b.subscription_id
          AND p.paid_at >  %(as_of)s::timestamp - interval '90 days'
          AND p.paid_at <= %(as_of)s::timestamp
    GROUP BY b.subscription_id
),

tick90 AS (
    SELECT b.subscription_id,
           COUNT(t.ticket_id) AS tickets_90d
    FROM base b
    LEFT JOIN support_tickets t
           ON t.student_id = b.student_id
          AND t.created_at >  %(as_of)s::timestamp - interval '90 days'
          AND t.created_at <= %(as_of)s::timestamp
    GROUP BY b.subscription_id
)

SELECT b.student_id,
       b.subscription_id,
       ROUND(b.tenure_days::numeric, 1)                      AS tenure_days,
       COALESCE(w.done, 0)                                   AS lessons_completed_28d,
       ROUND(COALESCE(w.no_show::numeric   / NULLIF(w.scheduled, 0), 0), 3)
                                                             AS no_show_rate_28d,
       ROUND(COALESCE(w.cancelled::numeric / NULLIF(w.scheduled, 0), 0), 3)
                                                             AS cancel_rate_28d,
       ROUND(COALESCE(w.avg_rating, 3.5)::numeric, 2)        AS avg_rating_28d,
       ROUND(COALESCE(w.rated::numeric / NULLIF(w.scheduled, 0), 0), 3)
                                                             AS rated_share_28d,
       ROUND(COALESCE(w.homework_rate, 0)::numeric, 3)       AS homework_rate_28d,
       COALESCE(
           EXTRACT(EPOCH FROM (%(as_of)s::timestamp - ll.last_done)) / 86400.0,
           999
       )::numeric(8, 1)                                      AS days_since_last_lesson,
       COALESCE(n.tutors_90d, 0)                             AS tutor_changes_90d,
       COALESCE(p.failed_90d, 0)                             AS failed_payments_90d,
       COALESCE(t.tickets_90d, 0)                            AS support_tickets_90d,
       ROUND(
           (COALESCE(w.done, 0) - b.lessons_per_week * 4.0)::numeric, 2
       )                                                     AS plan_gap_28d,
       CASE b.plan WHEN 'monthly' THEN 0 WHEN 'quarterly' THEN 1 ELSE 2 END
                                                             AS plan_code,
       b.lessons_per_week
FROM base b
LEFT JOIN win28       w  ON w.subscription_id  = b.subscription_id
LEFT JOIN last_lesson ll ON ll.subscription_id = b.subscription_id
LEFT JOIN win90       n  ON n.subscription_id  = b.subscription_id
LEFT JOIN pay90       p  ON p.subscription_id  = b.subscription_id
LEFT JOIN tick90      t  ON t.subscription_id  = b.subscription_id
"""

# Мітка для тренування: підписка, активна на :as_of, протягом наступних
# 30 днів або закінчилась, або в ній не відбулось жодного уроку.
# Рахується ТІЛЬКИ по історичних зрізах, де ці 30 днів уже минули.
LABEL_SQL = f"""
WITH base AS ({_BASE})
SELECT b.subscription_id,
       CASE WHEN EXISTS (
                SELECT 1 FROM subscriptions s2
                WHERE s2.subscription_id = b.subscription_id
                  AND s2.ended_at IS NOT NULL
                  AND s2.ended_at <= %(as_of)s::timestamp + interval '30 days'
            )
            OR NOT EXISTS (
                SELECT 1 FROM lessons l
                WHERE l.subscription_id = b.subscription_id
                  AND l.status = 'completed'
                  AND l.scheduled_at >  %(as_of)s::timestamp
                  AND l.scheduled_at <= %(as_of)s::timestamp + interval '30 days'
            )
       THEN 1 ELSE 0 END AS churned
FROM base b
"""
