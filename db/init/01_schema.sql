-- Схема синтетичного онлайн-сервісу репетиторства.
--
-- Коментарі до таблиць і колонок — не документація для людей, а вхідні дані
-- для моделі: інструмент describe_table віддає їх Claude дослівно. Саме тут
-- описані пастки, через які наївний запит дає правдоподібну, але неправильну
-- цифру. Кожен COMMENT нижче — це те, що інакше довелось би пояснювати голосом.

-- ---------------------------------------------------------------- students --

CREATE TABLE students (
    student_id          integer PRIMARY KEY,
    created_at          timestamp   NOT NULL,
    country             text        NOT NULL,
    grade               smallint    NOT NULL,
    parent_email        text        NOT NULL,
    acquisition_channel text        NOT NULL,
    timezone            text        NOT NULL,
    is_test_account     boolean     NOT NULL DEFAULT false
);

COMMENT ON TABLE students IS
    'Учні (по одному рядку на дитину). Реєструє акаунт батько, тому контактна '
    'пошта належить батькам, а не учневі.';

COMMENT ON COLUMN students.created_at IS
    'Момент реєстрації. Не збігається з початком занять: між реєстрацією та '
    'першим уроком зазвичай кілька днів.';
COMMENT ON COLUMN students.grade IS
    'Клас школи на момент реєстрації, 1-11. З часом не оновлюється.';
COMMENT ON COLUMN students.acquisition_channel IS
    'Канал залучення: organic, paid_search, social, referral, partner.';
COMMENT ON COLUMN students.is_test_account IS
    'ВАЖЛИВО: true — це внутрішній тестовий акаунт команди QA, а не реальний '
    'учень. Таких близько 2% від бази, і в них аномально багато уроків. '
    'Виключай is_test_account = false у БУДЬ-ЯКОМУ бізнес-запиті: у підрахунках '
    'учнів, уроків, виручки та відтоку. Якщо цього не зробити, цифри будуть '
    'завищені й виглядатимуть правдоподібно.';

-- ------------------------------------------------------------------ tutors --

CREATE TABLE tutors (
    tutor_id        integer PRIMARY KEY,
    hired_at        timestamp NOT NULL,
    country         text      NOT NULL,
    status          text      NOT NULL,
    subjects        text[]    NOT NULL,
    hourly_rate_usd numeric(6, 2) NOT NULL,
    rating_avg      numeric(3, 2)
);

COMMENT ON TABLE tutors IS 'Репетитори.';

COMMENT ON COLUMN tutors.status IS
    'active — працює зараз; paused — тимчасова перерва; left — звільнився. '
    'Уроки звільнених репетиторів лишаються в історії, тому для історичних '
    'звітів фільтрувати за status не треба.';
COMMENT ON COLUMN tutors.subjects IS
    'Масив предметів. Для фільтра за предметом використовуй оператор @> '
    'або ANY(subjects), а не порівняння через =.';
COMMENT ON COLUMN tutors.rating_avg IS
    'Середній рейтинг за всю історію, перерахунок раз на добу. NULL — якщо '
    'уроків ще не було. Це знімок, а не агрегат по lessons.rating на льоту.';

-- ----------------------------------------------------------- subscriptions --

CREATE TABLE subscriptions (
    subscription_id integer PRIMARY KEY,
    student_id      integer NOT NULL REFERENCES students (student_id),
    plan            text    NOT NULL,
    lessons_per_week smallint NOT NULL,
    started_at      timestamp NOT NULL,
    ended_at        timestamp,
    status          text    NOT NULL,
    mrr_usd         numeric(8, 2) NOT NULL,
    cancel_reason   text
);

COMMENT ON TABLE subscriptions IS
    'Підписки. УВАГА: один учень може мати кілька підписок послідовно — '
    'пішов і повернувся. Тому COUNT(subscription_id) НЕ дорівнює кількості '
    'учнів; для кількості учнів бери COUNT(DISTINCT student_id).';

COMMENT ON COLUMN subscriptions.plan IS 'monthly, quarterly або annual.';
COMMENT ON COLUMN subscriptions.lessons_per_week IS
    'Скільки уроків на тиждень оплачено планом, 1-3. Фактична кількість '
    'проведених уроків зазвичай менша — саме цей розрив є раннім сигналом '
    'відтоку.';
COMMENT ON COLUMN subscriptions.ended_at IS
    'NULL означає, що підписка ЗАРАЗ АКТИВНА, а не що дані відсутні. '
    'Умова активності на дату: started_at <= дата AND (ended_at IS NULL OR '
    'ended_at > дата).';
COMMENT ON COLUMN subscriptions.status IS
    'active — триває; cancelled — скасована користувачем достроково; '
    'expired — доїхала до кінця строку й не продовжилась. Для відтоку '
    'враховуй обидва: cancelled і expired.';
COMMENT ON COLUMN subscriptions.mrr_usd IS
    'Місячна виручка з підписки, приведена до місяця (для quarterly й annual '
    'вже поділена). Це планова величина; фактичні гроші — у таблиці payments.';

-- ----------------------------------------------------------------- lessons --

CREATE TABLE lessons (
    lesson_id       integer PRIMARY KEY,
    student_id      integer NOT NULL REFERENCES students (student_id),
    tutor_id        integer NOT NULL REFERENCES tutors (tutor_id),
    subscription_id integer NOT NULL REFERENCES subscriptions (subscription_id),
    scheduled_at    timestamp NOT NULL,
    status          text    NOT NULL,
    duration_min    smallint NOT NULL,
    rating          smallint,
    homework_done   boolean NOT NULL DEFAULT false
);

COMMENT ON TABLE lessons IS
    'Заплановані уроки. Рядок створюється в момент планування, тому в таблиці '
    'є і ті уроки, які так і не відбулися.';

COMMENT ON COLUMN lessons.scheduled_at IS
    'Час, на який урок був запланований (UTC). Для проведених уроків він же '
    'фактичний час проведення.';
COMMENT ON COLUMN lessons.status IS
    'ПАСТКА: чотири значення, і лише одне означає проведений урок. '
    'completed — урок відбувся; cancelled_by_parent — скасував батько; '
    'cancelled_by_tutor — скасував репетитор; no_show — учень не прийшов '
    'без попередження. COUNT(*) по таблиці рахує ВСІ чотири й завищує '
    'кількість уроків приблизно на чверть. Для «скільки уроків провели» '
    'завжди став status = ''completed''.';
COMMENT ON COLUMN lessons.rating IS
    'Оцінка уроку батьком, 1-5. NULL — не оцінили, і таких більшість. '
    'AVG(rating) ігнорує NULL автоматично, але частка оцінених уроків сама '
    'по собі є сигналом залученості.';
COMMENT ON COLUMN lessons.homework_done IS
    'Чи здав учень домашнє завдання після уроку. Для не проведених уроків '
    'завжди false.';

-- ---------------------------------------------------------------- payments --

CREATE TABLE payments (
    payment_id      integer PRIMARY KEY,
    subscription_id integer NOT NULL REFERENCES subscriptions (subscription_id),
    student_id      integer NOT NULL REFERENCES students (student_id),
    paid_at         timestamp NOT NULL,
    amount_usd      numeric(8, 2) NOT NULL,
    status          text    NOT NULL,
    method          text    NOT NULL
);

COMMENT ON TABLE payments IS
    'Списання по підписках. Джерело правди щодо фактичної виручки.';

COMMENT ON COLUMN payments.status IS
    'ПАСТКА: succeeded — гроші отримані; failed — списання не пройшло '
    '(грошей немає, але рядок є); refunded — гроші повернули клієнту. '
    'SUM(amount_usd) без фільтра завищує виручку, бо додає невдалі й '
    'повернуті платежі. Для виручки бери status = ''succeeded''. '
    'Для чистої виручки віднімай refunded окремо.';
COMMENT ON COLUMN payments.amount_usd IS
    'Сума транзакції в доларах. Для refunded зберігається ДОДАТНОЮ — знак '
    'не інвертований, тож віднімати треба явно.';
COMMENT ON COLUMN payments.method IS 'card, paypal або apple_pay.';

-- --------------------------------------------------------- support_tickets --

CREATE TABLE support_tickets (
    ticket_id   integer PRIMARY KEY,
    student_id  integer NOT NULL REFERENCES students (student_id),
    created_at  timestamp NOT NULL,
    category    text      NOT NULL,
    resolved_at timestamp,
    csat        smallint
);

COMMENT ON TABLE support_tickets IS
    'Звернення в підтримку. Сплеск звернень у конкретного учня — ранній '
    'сигнал того, що він скоро піде.';

COMMENT ON COLUMN support_tickets.category IS
    'billing, technical, tutor_complaint, scheduling або other.';
COMMENT ON COLUMN support_tickets.resolved_at IS
    'NULL — звернення ще відкрите.';
COMMENT ON COLUMN support_tickets.csat IS
    'Оцінка підтримки 1-5, NULL якщо не оцінили.';

-- --------------------------------------------------------------- audit_log --

CREATE TABLE audit_log (
    id            bigserial PRIMARY KEY,
    ts            timestamptz NOT NULL DEFAULT now(),
    tool          text        NOT NULL,
    query         text,
    rows_returned integer,
    duration_ms   integer,
    status        text        NOT NULL,
    error         text
);

COMMENT ON TABLE audit_log IS
    'Лог звернень AI-агента до бази: що саме питали, скільки рядків повернули '
    'і скільки це тривало. Пишеться самим MCP-сервером на кожен виклик — і '
    'успішний, і невдалий. Це єдина таблиця, куди агент має право писати.';

COMMENT ON COLUMN audit_log.status IS 'ok або error.';
COMMENT ON COLUMN audit_log.query IS
    'Текст SQL-запиту дослівно. Для інструментів, що не виконують SQL, NULL.';

-- ----------------------------------------------------------------- індекси --

CREATE INDEX idx_lessons_student_time  ON lessons (student_id, scheduled_at);
CREATE INDEX idx_lessons_time_status   ON lessons (scheduled_at, status);
CREATE INDEX idx_lessons_tutor         ON lessons (tutor_id);
CREATE INDEX idx_subs_student          ON subscriptions (student_id);
CREATE INDEX idx_subs_window           ON subscriptions (started_at, ended_at);
CREATE INDEX idx_payments_student_time ON payments (student_id, paid_at);
CREATE INDEX idx_payments_time_status  ON payments (paid_at, status);
CREATE INDEX idx_tickets_student_time  ON support_tickets (student_id, created_at);
