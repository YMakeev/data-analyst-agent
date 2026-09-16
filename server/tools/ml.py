"""Скоринг ризику відтоку — інструмент, який показує, навіщо MCP взагалі потрібен.

SQL модель напише сама, графік намалює сама. А от порахувати градієнтний бустинг
у голові не може. Саме тут тул перестає бути обгорткою над очевидним і стає
мостом до того, чого LLM не вміє принципово.

Пояснення «чому саме цей учень у ризику» будуємо без SHAP: беремо ознаки, де
учень найсильніше відхилився від медіани в бік ризику, зважені на важливість
ознаки в моделі. Це чесно, зрозуміло бізнесу й не тягне зайвих залежностей.
"""

from __future__ import annotations

import os
import pickle
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from server import audit
from server.db import fetch, friendly_db_error
from server.features import FEATURE_COLUMNS, FEATURE_LABELS

MODEL_PATH = Path(os.getenv("MODEL_PATH", "ml/model.pkl"))

_bundle: dict[str, Any] | None = None


def _train_now() -> bool:
    """Тренує модель на вимогу, якщо файлу немає.

    Тренування при старті контейнера — крихке місце: воно затримує відкриття
    порту, і хостинг може визнати деплой невдалим ще до того, як модель
    з'явиться. Тоді сервер піднімається, чотири інструменти працюють, а
    п'ятий мертвий — найгірший з можливих станів, бо виглядає як робочий.

    Тому тренування живе тут: перший виклик коштує кілька секунд, усі
    наступні беруть готовий файл.
    """
    script = MODEL_PATH.parent / "train.py"
    if not script.exists():
        return False
    print(f"[ml] моделі немає, тренуюсь ({script})", file=sys.stderr)
    try:
        done = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("[ml] тренування не вклалось у 5 хвилин", file=sys.stderr)
        return False
    if done.returncode != 0:
        print(f"[ml] тренування впало:\n{done.stderr[-2000:]}", file=sys.stderr)
        return False
    return MODEL_PATH.exists()


def _load() -> dict[str, Any]:
    global _bundle
    if _bundle is None:
        if not MODEL_PATH.exists():
            _train_now()
        if not MODEL_PATH.exists():
            # Локально й у хмарі лікується по-різному, тому кажемо обидва
            # варіанти: порада «зроби make train» усередині контейнера,
            # куди ніхто не зайде терміналом, марна.
            local = os.getenv("MCP_TRANSPORT", "stdio") == "stdio"
            fix = ("Спроба натренувати її щойно не вдалась. Запусти вручну "
                   "й подивись помилку: make train"
                   if local else
                   "Спроба натренувати її щойно не вдалась. Причина — у логах "
                   "сервісу, шукай рядок «[ml] тренування впало».")
            raise FileNotFoundError(f"Модель не знайдено ({MODEL_PATH}). {fix}")
        with MODEL_PATH.open("rb") as fh:
            _bundle = pickle.load(fh)
    return _bundle


def _explain(row: dict[str, Any], bundle: dict[str, Any], top_n: int = 3) -> list[str]:
    """Ознаки, що найсильніше тягнуть конкретного учня в ризик."""
    medians = bundle["medians"]
    weights = bundle["importances"]
    directions = bundle["risk_direction"]
    spread = bundle["spread"]

    scored = []
    for name in FEATURE_COLUMNS:
        value = float(row[name])
        deviation = (value - medians[name]) * directions[name]
        if deviation <= 0:
            continue  # ознака тягне в безпечний бік — не згадуємо
        norm = deviation / (spread[name] or 1.0)
        scored.append((norm * weights[name], name, value))

    scored.sort(reverse=True)
    out = []
    for _weight, name, value in scored[:top_n]:
        pretty = int(value) if float(value).is_integer() else round(value, 2)
        out.append(f"{FEATURE_LABELS[name]}: {pretty} (медіана {medians[name]})")
    return out


def predict_churn(student_ids: list[int] | None = None, top_n: int = 20) -> dict[str, Any]:
    """Оцінює ризик відтоку для учнів з активною підпискою.

    Повертає ймовірність того, що учень припинить займатись протягом
    найближчих 30 днів, і причини, які найбільше тягнуть його в ризик.
    Модель натренована на історії цієї ж бази.

    Без аргументів повертає найризикованіших учнів — це і є звичайний
    сценарій «кого нам зараз рятувати».

    Ймовірність — це підказка для людини, а не вирок: рішення, що робити
    з учнем, лишається за командою.

    Args:
        student_ids: конкретні учні. Порожньо — усі активні.
        top_n: скільки найризикованіших повернути, якщо список не заданий.
    """
    from server.features import FEATURE_SQL  # локально: sklearn тягнеться довго

    try:
        bundle = _load()
    except FileNotFoundError as exc:
        audit.log("predict_churn", status="error", error=str(exc))
        return {"error": str(exc)}

    as_of = date.today().isoformat()
    sql = FEATURE_SQL
    params: dict[str, Any] = {"as_of": as_of}
    if student_ids:
        sql = f"SELECT * FROM (\n{FEATURE_SQL}\n) f WHERE f.student_id = ANY(%(ids)s)"
        params["ids"] = list(student_ids)

    try:
        rows = _fetch_features(sql, params)
    except Exception as exc:  # noqa: BLE001
        msg = friendly_db_error(exc)
        audit.log("predict_churn", status="error", error=msg)
        return {"error": msg}

    if not rows:
        audit.log("predict_churn", rows=0)
        return {
            "as_of": as_of,
            "students": [],
            "note": "Активних підписок під ці умови не знайдено.",
        }

    model = bundle["model"]
    matrix = [[float(r[c]) for c in FEATURE_COLUMNS] for r in rows]
    probs = model.predict_proba(matrix)[:, 1]

    scored = [
        {
            "student_id": r["student_id"],
            "churn_probability": round(float(p), 3),
            "top_factors": _explain(r, bundle),
        }
        for r, p in zip(rows, probs)
    ]
    scored.sort(key=lambda x: x["churn_probability"], reverse=True)
    if not student_ids:
        scored = scored[:top_n]

    audit.log("predict_churn", rows=len(scored))
    return {
        "as_of": as_of,
        "model_roc_auc": bundle["roc_auc"],
        "scored_total": len(rows),
        "students": scored,
        "note": "Ймовірність відтоку протягом 30 днів від as_of. "
                "Це підказка для людини, а не автоматичне рішення.",
    }


def _fetch_features(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    from server.db import get_pool
    from psycopg.rows import dict_row

    from server.db import jsonable

    with get_pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return [jsonable(r) for r in cur.fetchall()]
