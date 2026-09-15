"""Збереження звіту на диск.

Свідомо НЕ інструмент для побудови графіків. Claude і так малює візуалізації
краще, ніж це зробив би наш тул із параметрами «тип, вісь X, вісь Y»: такий
тул лише звужує широкий інтерфейс, який у моделі вже є.

Дірка, яку ми закриваємо, інша: артефакт живе в чаті. Колезі його не кинеш
файлом і завтра не відкриєш. Тому модель малює, а сервер зберігає — і це весь
поділ праці.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from server import audit

# Дозволяємо літери будь-якої абетки: якщо модель назве звіт українською,
# файл має зберегти осмислену назву, а не перетворитись на черговий report.html,
# який затре попередній.
_SAFE_NAME = re.compile(r"[^\w-]+", re.UNICODE)


def _slug(name: str) -> str:
    slug = _SAFE_NAME.sub("-", name.strip().lower()).strip("-_")
    return (slug or "report")[:60]


def save_report(html: str, name: str) -> dict[str, Any]:
    """Зберігає готовий HTML-звіт у файл і повертає шлях до нього.

    Спершу згенеруй повноцінну самодостатню HTML-сторінку зі звітом: усі
    стилі й скрипти мають бути всередині файлу, без посилань на зовнішні
    сервіси, інакше звіт не відкриється без інтернету. Потім передай її сюди.

    Файл можна відкрити в браузері й переслати колегам.

    Args:
        html: повний HTML-документ.
        name: коротка назва латиницею, наприклад revenue-by-channel.
    """
    if not html or "<" not in html:
        msg = "Порожній або не-HTML вміст. Передай повний HTML-документ."
        audit.log("save_report", query=name, status="error", error=msg)
        return {"error": msg}

    reports_dir = Path(os.getenv("REPORTS_DIR", "./reports")).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    path = reports_dir / f"{date.today().isoformat()}-{_slug(name)}.html"
    try:
        path.write_text(html, encoding="utf-8")
    except OSError as exc:
        msg = f"Не вдалось записати файл: {exc}"
        audit.log("save_report", query=name, status="error", error=msg)
        return {"error": msg}

    size_kb = round(path.stat().st_size / 1024, 1)
    audit.log("save_report", query=str(path), rows=1)
    return {
        "path": str(path),
        "size_kb": size_kb,
        "message": f"Звіт збережено: {path}. Відкрий файл у браузері.",
    }
