"""Тренування моделі, яка оцінює ризик відтоку учня.

Запусти один раз перед роботою:

    make train

Скрипт читає історію з бази, навчає модель, перевіряє її якість і, якщо
якість прийнятна, зберігає у файл `ml/model.pkl`. Сервер цей файл лише
завантажує — сам він нічого не навчає.

Такий поділ називають «тренування офлайн, передбачення онлайн», і він тут не
випадковий. Якби модель навчалась у момент запиту, ти щоразу отримувала б трохи
іншу модель, ніхто не встиг би перевірити її якість, а перший користувач чекав
би кілька секунд. Тому навчання — окремий крок з окремим результатом-файлом,
який можна перевірити, покласти в поставку й у разі чого відкотити.

Два рішення в цьому файлі важливіші за вибір алгоритму.

**Навчальні приклади — це історичні зрізи, а не список учнів.** Ми беремо
кілька десятків дат у минулому. На кожну дату рахуємо, як учень поводився
до неї, і дивимось, чи пішов він протягом наступних 30 днів. Один учень дає
стільки прикладів, на скількох зрізах він був активний. Так модель вчиться
на поведінці в динаміці, а не на статичному портреті.

**Розбиття на навчання і перевірку — за часом, а не випадкове.** Модель
вчиться на ранніх зрізах, а перевіряється на пізніх — тобто на майбутньому,
якого вона не бачила. Якби ми розбивали випадково, у навчальні дані
потрапили б пізніші події, метрики вийшли б чудові, а в реальній роботі
модель не працювала б. Це найпоширеніша помилка в задачах відтоку.
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server.features import FEATURE_COLUMNS, FEATURE_SQL, LABEL_SQL  # noqa: E402

MODEL_PATH = Path(__file__).resolve().parent / "model.pkl"

# Зрізи беремо раз на три тижні. Частіше немає сенсу: сусідні дати дають
# майже однакові рядки, і модель просто кілька разів вчить одне й те саме.
SNAPSHOT_STEP_DAYS = 21
# Перші місяці історії пропускаємо: ознаки, що дивляться на 90 днів назад,
# там ще не наповнені, і приклади вийшли б неповноцінні.
WARMUP_DAYS = 120
# Останній зріз має бути щонайменше за 31 день до кінця даних — інакше
# відповідь «чи пішов протягом 30 днів» ще невідома.
LABEL_HORIZON_DAYS = 31
HISTORY_DAYS = 18 * 30

# Нижче цього порогу модель не зберігається. ROC AUC 0.5 — це рівень
# підкидання монетки, 1.0 — ідеальне вгадування. Для задачі відтоку
# реалістичний діапазон 0.7-0.85; якщо вийшло менше, у даних забракло
# сигналу, і викладати таку модель у роботу не можна.
MIN_ROC_AUC = 0.70


def snapshots(today: date) -> list[date]:
    """Дати, станом на які рахуємо поведінку учнів."""
    start = today - timedelta(days=HISTORY_DAYS - WARMUP_DAYS)
    end = today - timedelta(days=LABEL_HORIZON_DAYS)
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=SNAPSHOT_STEP_DAYS)
    return out


def collect(conn: psycopg.Connection, as_of: date) -> tuple[np.ndarray, np.ndarray]:
    """Ознаки й відповіді для одного зрізу.

    X — таблиця «рядок на учня, колонка на ознаку».
    y — 1, якщо учень пішов протягом наступних 30 днів, інакше 0.
    """
    params = {"as_of": as_of.isoformat()}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(FEATURE_SQL, params)
        feats = {r["subscription_id"]: r for r in cur.fetchall()}
        cur.execute(LABEL_SQL, params)
        labels = {r["subscription_id"]: r["churned"] for r in cur.fetchall()}

    ids = [i for i in feats if i in labels]
    if not ids:
        return np.empty((0, len(FEATURE_COLUMNS))), np.empty(0)

    X = np.array([[float(feats[i][c]) for c in FEATURE_COLUMNS] for i in ids])
    y = np.array([labels[i] for i in ids])
    return X, y


def connect() -> psycopg.Connection | None:
    """Підключення до бази. Для навчання достатньо прав на читання.

    Джерела перебираємо по черзі, а не беремо перше-ліпше: у змінних оточення
    легко лишається старе значення, яке вказує в нікуди, і тоді помилка
    виглядає як «бази немає», хоча поруч лежить робоче підключення.
    """
    sources = [(n, os.getenv(n)) for n in ("ADMIN_DATABASE_URL", "DATABASE_URL")]
    for name, dsn in [(n, v) for n, v in sources if v]:
        try:
            conn = psycopg.connect(dsn, connect_timeout=15, prepare_threshold=None)
            print(f"    підключення через {name}")
            return conn
        except psycopg.OperationalError as exc:
            print(f"    {name}: не вдалось — {str(exc).strip().splitlines()[0]}",
                  file=sys.stderr)
    return None


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="Натренувати модель ризику відтоку")
    p.add_argument("--min-auc", type=float, default=MIN_ROC_AUC,
                   help="нижче цієї якості модель не зберігається")
    args = p.parse_args()

    today = date.today()
    dates = snapshots(today)
    print(f"==> Історичних зрізів: {len(dates)} "
          f"({dates[0]} … {dates[-1]}, крок {SNAPSHOT_STEP_DAYS} дн.)")

    conn = connect()
    if conn is None:
        print("\nНе вдалось під'єднатись до бази.", file=sys.stderr)
        print("Якщо база локальна — підніми її: docker compose up -d", file=sys.stderr)
        print("Якщо база в хмарі — перевір DATABASE_URL у файлі .env", file=sys.stderr)
        return 1

    blocks: list[tuple[date, np.ndarray, np.ndarray]] = []
    with conn:
        for d in dates:
            X, y = collect(conn, d)
            if len(y):
                blocks.append((d, X, y))

    if not blocks:
        print("У базі немає даних для навчання. Спершу заповни її: make seed",
              file=sys.stderr)
        return 1

    # Ранні зрізи — навчання, пізні — перевірка. Модель ніколи не бачить
    # майбутнього відносно того, на чому вчилась.
    split = int(len(blocks) * 0.75)
    X_train = np.vstack([b[1] for b in blocks[:split]])
    y_train = np.concatenate([b[2] for b in blocks[:split]])
    X_test = np.vstack([b[1] for b in blocks[split:]])
    y_test = np.concatenate([b[2] for b in blocks[split:]])

    print(f"    навчання  {len(y_train):,} прикладів (до {blocks[split - 1][0]}), "
          f"пішли {y_train.mean():.1%}")
    print(f"    перевірка {len(y_test):,} прикладів (з {blocks[split][0]}), "
          f"пішли {y_test.mean():.1%}")

    model = GradientBoostingClassifier(
        n_estimators=180, learning_rate=0.06, max_depth=3,
        subsample=0.85, random_state=42,
    )
    model.fit(X_train, y_train)

    auc = float(roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]))
    print(f"\n    ROC AUC на перевірці: {auc:.3f}")

    # Ворота якості. Саме заради них навчання винесене в окремий крок:
    # у робочу поставку не має потрапити модель, яку ніхто не перевірив.
    if auc < args.min_auc:
        print(f"\n!! Якість нижча за поріг {args.min_auc}. Модель НЕ збережена —"
              f"\n   попередня версія (якщо була) лишилась недоторканою.", file=sys.stderr)
        print("   Найімовірніша причина: у базі замало або надто мало "
              "різноманітних даних.", file=sys.stderr)
        return 1
    if auc > 0.97:
        print("    ! Підозріло високо. Зазвичай це означає, що в ознаки "
              "просочилась інформація з майбутнього.")

    # Дані для пояснення «чому саме цей учень у ризику». Порівнюватимемо
    # значення ознак конкретного учня з типовими по базі.
    X_all = np.vstack([b[1] for b in blocks])
    y_all = np.concatenate([b[2] for b in blocks])
    medians, spread, direction = {}, {}, {}
    for i, name in enumerate(FEATURE_COLUMNS):
        col = X_all[:, i]
        medians[name] = round(float(np.median(col)), 2)
        q1, q3 = np.percentile(col, [25, 75])
        spread[name] = float(q3 - q1) or float(col.std()) or 1.0
        # У який бік відхилення означає ризик — з'ясовуємо з даних, а не з
        # власних уявлень про предметну область.
        if col.std() == 0:
            direction[name] = 1.0
        else:
            corr = float(np.corrcoef(col, y_all)[0, 1])
            direction[name] = 1.0 if corr >= 0 else -1.0

    importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_.tolist()))
    print("\n    На що модель спирається найбільше:")
    for name, w in sorted(importances.items(), key=lambda kv: kv[1], reverse=True)[:5]:
        print(f"      {w:>6.1%}  {name}")

    bundle = {
        "model": model,
        "features": FEATURE_COLUMNS,
        "roc_auc": round(auc, 3),
        "trained_at": today.isoformat(),
        "importances": importances,
        "medians": medians,
        "spread": spread,
        "risk_direction": direction,
        "base_rate": round(float(y_all.mean()), 4),
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MODEL_PATH.open("wb") as fh:
        pickle.dump(bundle, fh)
    print(f"\n    Модель збережено: {MODEL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
