"""Тренування churn-моделі.

Запускається один раз при сетапі (make train) і кладе ml/model.pkl.
Модель у git не комітиться — вона відтворюється з даних за кілька секунд.

Два рішення тут важливіші за вибір алгоритму, і на воркшопі варто назвати
обидва вголос.

1. Навчальна вибірка — це НАБІР ІСТОРИЧНИХ ЗРІЗІВ, а не одна таблиця «учні».
   Ми беремо десятки дат у минулому, на кожну рахуємо ознаки станом на той
   момент і дивимось, що сталось протягом наступних 30 днів. Так модель
   вчиться на динаміці, а не на статичному портреті.

2. Розбиття train/test — ЗА ЧАСОМ, а не випадкове. Випадкове розбиття дало б
   красиві метрики й нікчемну модель: у навчальну вибірку потрапило б
   майбутнє. Це найпоширеніша помилка в задачах відтоку.
"""

from __future__ import annotations

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

# Зрізи беремо не частіше ніж раз на три тижні: сусідні дати дають майже
# ідентичні рядки, і модель просто вчить одне й те саме кілька разів.
SNAPSHOT_STEP_DAYS = 21
# Перші 120 днів історії пропускаємо: ознаки за 90 днів там ще не наповнені.
WARMUP_DAYS = 120
# Останній зріз має бути не пізніше ніж за 31 день до кінця даних —
# інакше мітку «пішов протягом 30 днів» просто немає з чого порахувати.
LABEL_HORIZON_DAYS = 31
HISTORY_DAYS = 18 * 30


def snapshots(today: date) -> list[date]:
    start = today - timedelta(days=HISTORY_DAYS - WARMUP_DAYS)
    end = today - timedelta(days=LABEL_HORIZON_DAYS)
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=SNAPSHOT_STEP_DAYS)
    return out


def collect(conn: psycopg.Connection, as_of: date) -> tuple[np.ndarray, np.ndarray]:
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


def main() -> int:
    load_dotenv()
    dsn = os.getenv("ADMIN_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        print("Немає DSN. Скопіюй .env.example у .env.", file=sys.stderr)
        return 1

    today = date.today()
    dates = snapshots(today)
    print(f"==> Історичних зрізів: {len(dates)} "
          f"({dates[0]} … {dates[-1]}, крок {SNAPSHOT_STEP_DAYS} дн.)")

    try:
        conn = psycopg.connect(dsn, prepare_threshold=None)
    except psycopg.OperationalError as exc:
        print(f"Немає з'єднання з базою: {exc}", file=sys.stderr)
        print("Підніми контейнер: docker compose up -d", file=sys.stderr)
        return 1

    blocks: list[tuple[date, np.ndarray, np.ndarray]] = []
    with conn:
        for d in dates:
            X, y = collect(conn, d)
            if len(y):
                blocks.append((d, X, y))

    if not blocks:
        print("Немає даних для тренування. Спершу: make seed", file=sys.stderr)
        return 1

    # Розбиття за часом: останні 25% зрізів — тест. Модель ніколи не бачить
    # майбутнього відносно того, на чому вчилась.
    split = int(len(blocks) * 0.75)
    X_train = np.vstack([b[1] for b in blocks[:split]])
    y_train = np.concatenate([b[2] for b in blocks[:split]])
    X_test = np.vstack([b[1] for b in blocks[split:]])
    y_test = np.concatenate([b[2] for b in blocks[split:]])

    print(f"    train {len(y_train):,} рядків (до {blocks[split - 1][0]}), "
          f"частка відтоку {y_train.mean():.1%}")
    print(f"    test  {len(y_test):,} рядків (з {blocks[split][0]}), "
          f"частка відтоку {y_test.mean():.1%}")

    model = GradientBoostingClassifier(
        n_estimators=180, learning_rate=0.06, max_depth=3,
        subsample=0.85, random_state=42,
    )
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, proba))
    print(f"\n    ROC AUC на тесті: {auc:.3f}")
    if auc > 0.97:
        print("    ! Підозріло високо — схоже, у ознаки протекло майбутнє.")
    elif auc < 0.65:
        print("    ! Низько — сигналу в даних замало, перевір генератор.")

    # Метадані для пояснення «чому саме цей учень у ризику».
    X_all = np.vstack([b[1] for b in blocks])
    y_all = np.concatenate([b[2] for b in blocks])
    medians, spread, direction = {}, {}, {}
    for i, name in enumerate(FEATURE_COLUMNS):
        col = X_all[:, i]
        medians[name] = round(float(np.median(col)), 2)
        q1, q3 = np.percentile(col, [25, 75])
        spread[name] = float(q3 - q1) or float(col.std()) or 1.0
        # У який бік відхилення означає ризик — визначаємо з даних,
        # а не з власних уявлень про предметну область.
        if col.std() == 0:
            direction[name] = 1.0
        else:
            corr = float(np.corrcoef(col, y_all)[0, 1])
            direction[name] = 1.0 if corr >= 0 else -1.0

    importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_.tolist()))
    top = sorted(importances.items(), key=lambda kv: kv[1], reverse=True)[:5]
    print("\n    Найвпливовіші ознаки:")
    for name, w in top:
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
