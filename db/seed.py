"""Генератор синтетичних даних для воркшопу.

Дані в git не комітяться — комітиться цей скрипт. Random seed зафіксований,
тому в усіх учасників база збігається до останнього рядка: однакові дані
означають однакові відповіді Claude, а отже передбачуване демо.

Часові рамки рахуються відносно --as-of (дефолт: сьогодні), тож дані
завжди виглядають свіжими, коли б воркшоп не повторювали.

Головна вимога до реалістичності: відтік має бути ПЕРЕДБАЧУВАНИМ з поведінки.
Учень не зникає раптово — за 4-6 тижнів до відходу в нього росте частка
пропусків, падає рейтинг уроків, з'являються звернення в підтримку й невдалі
списання. Без цієї динаміки churn-модель не мала б чого вчити, і ROC AUC
вийшов би близько 0.5.

Запуск:
    python db/seed.py
    python db/seed.py --dsn postgresql://... --students 2000
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import psycopg
from dotenv import load_dotenv

SEED = 42
HISTORY_MONTHS = 18

COUNTRIES = ["US", "UK", "CA", "AU", "DE", "PL", "UA", "ES"]
COUNTRY_W = [40, 16, 10, 8, 8, 7, 6, 5]
TIMEZONES = {
    "US": "America/New_York", "UK": "Europe/London", "CA": "America/Toronto",
    "AU": "Australia/Sydney", "DE": "Europe/Berlin", "PL": "Europe/Warsaw",
    "UA": "Europe/Kyiv", "ES": "Europe/Madrid",
}
CHANNELS = ["organic", "paid_search", "social", "referral", "partner"]
CHANNEL_W = [30, 34, 18, 12, 6]
SUBJECTS = ["math", "algebra", "geometry", "physics", "chemistry", "english"]
PLANS = [("monthly", 1.0), ("quarterly", 0.92), ("annual", 0.8)]
PLAN_W = [62, 26, 12]
BASE_PRICE_PER_LESSON = 22.0
TICKET_CATEGORIES = ["billing", "technical", "tutor_complaint", "scheduling", "other"]
CANCEL_REASONS = [
    "too_expensive", "no_time", "tutor_mismatch", "goal_achieved",
    "switched_competitor", "technical_issues", None,
]

# Канал залучення впливає на якість когорти: платний трафік відтікає помітно
# гірше за рекомендації. Це дає моделі й аналітику осмислений зріз.
CHANNEL_RETENTION = {
    "organic": 1.00, "paid_search": 0.78, "social": 0.82,
    "referral": 1.18, "partner": 0.95,
}


def month_seasonality(d: date) -> float:
    """Літній провал і просідання на новорічні свята."""
    m = d.month
    if m in (7, 8):
        return 0.55
    if m == 6:
        return 0.75
    if m == 12:
        return 0.7
    if m in (9, 10):
        return 1.25
    return 1.0


@dataclass
class Sub:
    subscription_id: int
    student_id: int
    plan: str
    lessons_per_week: int
    started_at: datetime
    ended_at: datetime | None
    status: str
    mrr_usd: float
    cancel_reason: str | None
    will_churn: bool
    churn_at: datetime | None


class Generator:
    def __init__(self, as_of: date, n_students: int) -> None:
        self.rng = random.Random(SEED)
        self.as_of = datetime.combine(as_of, datetime.min.time())
        self.start = self.as_of - timedelta(days=HISTORY_MONTHS * 30)
        self.n_students = n_students

        self.students: list[tuple] = []
        self.tutors: list[tuple] = []
        self.subs: list[Sub] = []
        self.lessons: list[tuple] = []
        self.payments: list[tuple] = []
        self.tickets: list[tuple] = []

        self._tutor_ids: list[int] = []
        self._tutor_quality: dict[int, float] = {}
        self._lesson_id = 0
        self._payment_id = 0
        self._ticket_id = 0

    # ------------------------------------------------------------ helpers --

    def rand_dt(self, lo: datetime, hi: datetime) -> datetime:
        span = max(int((hi - lo).total_seconds()), 1)
        return lo + timedelta(seconds=self.rng.randrange(span))

    # ------------------------------------------------------------- tutors --

    def gen_tutors(self, n: int = 250) -> None:
        for tid in range(1, n + 1):
            hired = self.rand_dt(self.start - timedelta(days=400), self.as_of - timedelta(days=20))
            status = self.rng.choices(["active", "paused", "left"], [78, 10, 12])[0]
            k = self.rng.randint(1, 3)
            subjects = self.rng.sample(SUBJECTS, k)
            # Якість репетитора — прихована змінна: впливає і на rating_avg,
            # і на те, як довго тримаються його учні.
            quality = min(1.0, max(0.0, self.rng.gauss(0.62, 0.18)))
            self._tutor_quality[tid] = quality
            rating = round(3.2 + quality * 1.75 + self.rng.gauss(0, 0.12), 2)
            rating = max(2.5, min(5.0, rating))
            self.tutors.append((
                tid, hired, self.rng.choices(COUNTRIES, COUNTRY_W)[0], status,
                "{" + ",".join(subjects) + "}",
                round(self.rng.uniform(14, 42), 2),
                rating,
            ))
            self._tutor_ids.append(tid)

    # ----------------------------------------------------------- students --

    def gen_students(self) -> None:
        total_days = (self.as_of - self.start).days
        for sid in range(1, self.n_students + 1):
            is_test = self.rng.random() < 0.02

            if is_test:
                # Тестові акаунти QA заводять, коли будують систему, і вони
                # відтоді безперервно ганяють розклад. Саме тому в них
                # непропорційно багато уроків, і саме тому їх треба
                # виключати з бізнес-метрик.
                created = self.start + timedelta(days=self.rng.randint(0, 25))
            else:
                # Реєстрації ростуть у часі (молодший бізнес — менше клієнтів)
                # і підпорядковані сезонності.
                while True:
                    offset = int(total_days * (self.rng.random() ** 0.72))
                    created = self.start + timedelta(days=offset, seconds=self.rng.randrange(86400))
                    if self.rng.random() < month_seasonality(created.date()) / 1.25:
                        break

            country = self.rng.choices(COUNTRIES, COUNTRY_W)[0]
            channel = self.rng.choices(CHANNELS, CHANNEL_W)[0]

            self.students.append((
                sid, created, country, self.rng.randint(1, 11),
                f"parent{sid}@example.com", channel, TIMEZONES[country], is_test,
            ))

    # ------------------------------------------------------- subscriptions --

    def gen_subscriptions(self) -> None:
        sub_id = 0
        for sid, created, _country, _grade, _email, channel, _tz, is_test in self.students:
            retention = CHANNEL_RETENTION[channel]
            cursor = created + timedelta(days=self.rng.randint(1, 10))
            # Тестові акаунти живуть довго й займаються неприродно багато —
            # саме тому їх треба виключати з бізнес-метрик.
            n_subs = 1 if is_test else self.rng.choices([1, 2, 3], [74, 21, 5])[0]

            for _ in range(n_subs):
                if cursor >= self.as_of:
                    break
                sub_id += 1
                plan, discount = self.rng.choices(PLANS, PLAN_W)[0]
                lpw = 3 if is_test else self.rng.choices([1, 2, 3], [42, 44, 14])[0]
                mrr = round(lpw * 4.33 * BASE_PRICE_PER_LESSON * discount, 2)

                # Скільки місяців протримається. Довгі плани тримаються довше,
                # бо оплачені наперед.
                base_life = self.rng.expovariate(1 / 5.0) + 0.7
                base_life *= retention
                base_life *= {"monthly": 1.0, "quarterly": 1.5, "annual": 2.4}[plan]
                if is_test:
                    base_life = 30.0
                life_days = int(min(base_life, 20) * 30.4)

                planned_end = cursor + timedelta(days=life_days)
                if planned_end >= self.as_of:
                    # Підписка ще триває на дату зрізу.
                    ended_at, status, reason = None, "active", None
                    # Частина активних уже котиться до виходу — саме їх
                    # predict_churn має підсвітити на демо.
                    will_churn = (not is_test) and self.rng.random() < 0.14
                    churn_at = self.as_of + timedelta(days=self.rng.randint(3, 30)) if will_churn else None
                else:
                    ended_at = planned_end
                    # expired — доїхав до кінця строку; cancelled — пішов достроково.
                    status = self.rng.choices(["cancelled", "expired"], [68, 32])[0]
                    reason = self.rng.choice(CANCEL_REASONS) if status == "cancelled" else None
                    will_churn, churn_at = True, planned_end

                self.subs.append(Sub(
                    sub_id, sid, plan, lpw, cursor, ended_at, status, mrr,
                    reason, will_churn, churn_at,
                ))

                if ended_at is None:
                    break
                # Пауза перед поверненням (якщо учень повернеться).
                cursor = ended_at + timedelta(days=self.rng.randint(20, 200))

    # ------------------------------------------------------------- lessons --

    def _health(self, sub: Sub, when: datetime) -> float:
        """Наскільки учень 'живий' у цей момент: 1.0 — норма, 0 — на виході.

        Для тих, хто піде, здоров'я плавно осідає протягом останніх 4-6 тижнів.
        Це і є сигнал, який згодом ловить churn-модель.
        """
        if not sub.will_churn or sub.churn_at is None:
            return 1.0
        decay_window = timedelta(days=self.rng_stable_window(sub))
        days_left = (sub.churn_at - when).total_seconds() / 86400
        w = decay_window.total_seconds() / 86400
        if days_left >= w:
            return 1.0
        return max(0.05, days_left / w)

    def rng_stable_window(self, sub: Sub) -> int:
        """Довжина вікна згасання, стабільна для конкретної підписки."""
        return 28 + (sub.subscription_id * 7919) % 15  # 28..42 дні

    def gen_lessons(self) -> None:
        for sub in self.subs:
            is_test = self.students[sub.student_id - 1][7]
            # Постійні репетитори учня; зміна репетитора — теж сигнал.
            pool = [self.rng.choice(self._tutor_ids)]
            end = sub.ended_at or self.as_of
            slot = sub.started_at + timedelta(days=self.rng.randint(0, 3))
            gap = 7.0 / sub.lessons_per_week

            while slot < end and slot < self.as_of:
                health = 1.0 if is_test else self._health(sub, slot)
                season = month_seasonality(slot.date())

                # Влітку й на свята родини ставлять заняття на паузу: слот
                # просто не з'являється в розкладі. Без цього графік уроків
                # по місяцях виходить рівною лінією без жодної історії.
                if not is_test and self.rng.random() < max(0.0, 1 - season) * 0.45:
                    slot += timedelta(days=gap, seconds=self.rng.randrange(-7200, 7200))
                    continue

                # Незадоволений учень міняє репетитора — і це видно в даних.
                if health < 0.6 and self.rng.random() < 0.04 and len(pool) < 4:
                    pool.append(self.rng.choice(self._tutor_ids))
                tutor = pool[-1] if self.rng.random() < 0.85 else self.rng.choice(pool)
                quality = self._tutor_quality[tutor]

                # Ймовірності статусів: що нижче health, то більше зривів.
                p_no_show = 0.03 + (1 - health) * 0.28
                p_cancel_parent = 0.05 + (1 - health) * 0.18 + (1 - season) * 0.1
                p_cancel_tutor = 0.025 + (1 - quality) * 0.03
                r = self.rng.random()
                if r < p_no_show:
                    status = "no_show"
                elif r < p_no_show + p_cancel_parent:
                    status = "cancelled_by_parent"
                elif r < p_no_show + p_cancel_parent + p_cancel_tutor:
                    status = "cancelled_by_tutor"
                else:
                    status = "completed"

                rating = None
                homework = False
                if status == "completed":
                    # Оцінюють меншість уроків, і що гірші справи — то рідше.
                    if self.rng.random() < 0.28 * (0.5 + health / 2):
                        mean = 3.0 + quality * 1.6 + (health - 1) * 1.2
                        rating = max(1, min(5, int(round(self.rng.gauss(mean, 0.7)))))
                    homework = self.rng.random() < 0.3 + health * 0.45

                self._lesson_id += 1
                self.lessons.append((
                    self._lesson_id, sub.student_id, tutor, sub.subscription_id,
                    slot, status, self.rng.choice([30, 45, 60]), rating, homework,
                ))

                slot += timedelta(days=gap, seconds=self.rng.randrange(-7200, 7200))

    # ------------------------------------------------------------ payments --

    def gen_payments(self) -> None:
        period = {"monthly": 30, "quarterly": 91, "annual": 365}
        for sub in self.subs:
            step = period[sub.plan]
            amount = round(sub.mrr_usd * (step / 30.4), 2)
            when = sub.started_at
            end = sub.ended_at or self.as_of
            while when <= end and when <= self.as_of:
                health = self._health(sub, when)
                # Невдале списання і частіша причина, і частіший супутник відтоку.
                r = self.rng.random()
                if r < 0.03 + (1 - health) * 0.12:
                    status = "failed"
                elif r < 0.045 + (1 - health) * 0.14:
                    status = "refunded"
                else:
                    status = "succeeded"

                self._payment_id += 1
                self.payments.append((
                    self._payment_id, sub.subscription_id, sub.student_id, when,
                    amount, status,
                    self.rng.choices(["card", "paypal", "apple_pay"], [78, 14, 8])[0],
                ))
                when += timedelta(days=step)

    # ------------------------------------------------------------- tickets --

    def gen_tickets(self) -> None:
        for sub in self.subs:
            end = sub.ended_at or self.as_of
            when = sub.started_at
            while when < end and when < self.as_of:
                health = self._health(sub, when)
                # Базова інтенсивність низька, але перед виходом росте втричі.
                weekly_p = 0.02 + (1 - health) * 0.11
                if self.rng.random() < weekly_p:
                    self._ticket_id += 1
                    created = when
                    resolved = None
                    csat = None
                    if self.rng.random() < 0.88:
                        resolved = created + timedelta(hours=self.rng.randint(1, 96))
                        if self.rng.random() < 0.45:
                            mean = 2.6 + health * 1.8
                            csat = max(1, min(5, int(round(self.rng.gauss(mean, 0.9)))))
                    category = self.rng.choices(
                        TICKET_CATEGORIES,
                        [22, 26, 18 + int((1 - health) * 25), 20, 14],
                    )[0]
                    self.tickets.append((
                        self._ticket_id, sub.student_id, created, category, resolved, csat,
                    ))
                when += timedelta(days=7)

    def run(self) -> None:
        self.gen_tutors()
        self.gen_students()
        self.gen_subscriptions()
        self.gen_lessons()
        self.gen_payments()
        self.gen_tickets()


# ------------------------------------------------------------------ запис --

TABLES = ["audit_log", "support_tickets", "payments", "lessons", "subscriptions", "tutors", "students"]

COPY_SPECS = [
    ("students", "student_id, created_at, country, grade, parent_email, "
                 "acquisition_channel, timezone, is_test_account"),
    ("tutors", "tutor_id, hired_at, country, status, subjects, hourly_rate_usd, rating_avg"),
    ("subscriptions", "subscription_id, student_id, plan, lessons_per_week, started_at, "
                      "ended_at, status, mrr_usd, cancel_reason"),
    ("lessons", "lesson_id, student_id, tutor_id, subscription_id, scheduled_at, "
                "status, duration_min, rating, homework_done"),
    ("payments", "payment_id, subscription_id, student_id, paid_at, amount_usd, status, method"),
    ("support_tickets", "ticket_id, student_id, created_at, category, resolved_at, csat"),
]


def write(conn: psycopg.Connection, gen: Generator) -> None:
    sub_rows = [
        (s.subscription_id, s.student_id, s.plan, s.lessons_per_week, s.started_at,
         s.ended_at, s.status, s.mrr_usd, s.cancel_reason)
        for s in gen.subs
    ]
    data = {
        "students": gen.students,
        "tutors": gen.tutors,
        "subscriptions": sub_rows,
        "lessons": gen.lessons,
        "payments": gen.payments,
        "support_tickets": gen.tickets,
    }

    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
        for table, cols in COPY_SPECS:
            rows = data[table]
            with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as cp:
                for row in rows:
                    cp.write_row(row)
            print(f"    {table:<16} {len(rows):>8,}")
        cur.execute("ANALYZE")
    conn.commit()


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="Згенерувати демо-базу для воркшопу")
    p.add_argument("--dsn", default=os.getenv("ADMIN_DATABASE_URL"),
                   help="Куди заливати. Дефолт — ADMIN_DATABASE_URL з .env")
    p.add_argument("--as-of", default=date.today().isoformat(),
                   help="Дата зрізу, YYYY-MM-DD. Історія — 18 місяців до неї")
    p.add_argument("--students", type=int, default=5000)
    args = p.parse_args()

    if not args.dsn:
        print("Немає DSN. Скопіюй .env.example у .env або передай --dsn.", file=sys.stderr)
        return 1

    as_of = date.fromisoformat(args.as_of)
    print(f"==> Генерую історію за {HISTORY_MONTHS} міс. до {as_of}, учнів: {args.students:,}")

    gen = Generator(as_of, args.students)
    gen.run()

    try:
        with psycopg.connect(args.dsn) as conn:
            write(conn, gen)
    except psycopg.OperationalError as e:
        print(f"\nНе вдалось під'єднатись до бази: {e}", file=sys.stderr)
        print("Перевір, що контейнер піднятий: docker compose up -d", file=sys.stderr)
        return 1

    active = sum(1 for s in gen.subs if s.ended_at is None)
    at_risk = sum(1 for s in gen.subs if s.ended_at is None and s.will_churn)
    print(f"\n    активних підписок {active:,}, з них у зоні ризику {at_risk:,}")
    print("    готово")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
