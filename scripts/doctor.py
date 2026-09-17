"""Перевіряє, чи все готове до роботи, і пояснює, що робити, якщо ні.

    make doctor

Перевірки йдуть у тому ж порядку, у якому речі ламаються: спершу оточення,
потім база, потім модель. Перша ж червона позначка зазвичай і є причиною.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK, BAD, WARN = "  [ок]  ", "  [!!]  ", "  [..]  "

problems: list[str] = []


def check(label: str, ok: bool, detail: str = "", fix: str = "") -> bool:
    print(f"{OK if ok else BAD}{label}" + (f" — {detail}" if detail else ""))
    if not ok and fix:
        problems.append(f"{label}: {fix}")
    return ok


def main() -> int:
    print("\nПеревірка оточення\n")

    v = sys.version_info
    check("Python 3.10+", v >= (3, 10), f"зараз {v.major}.{v.minor}",
          "постав новішу версію, див. docs/SETUP.md")

    in_venv = sys.prefix != sys.base_prefix
    check("Ізольоване оточення активне", in_venv, "" if in_venv else "не активоване",
          "виконай: source .venv/bin/activate")

    try:
        import mcp, psycopg, sklearn  # noqa: F401
        check("Бібліотеки встановлені", True)
    except ImportError as exc:
        check("Бібліотеки встановлені", False, str(exc),
              'виконай: pip install -e ".[dev]"')

    # Claude Desktop запускає сервер з іншої теки, тому важливо, щоб код
    # знаходився не лише «зсередини проєкту». Найчастіше це ламається після
    # перенесення теки проєкту в інше місце.
    import subprocess
    found = subprocess.run(
        [sys.executable, "-c", "import server, sys; print(server.__file__)"],
        cwd=str(ROOT.parent), capture_output=True, text=True,
    )
    here = found.stdout.strip().startswith(str(ROOT))
    check("Код видно ззовні теки проєкту", found.returncode == 0 and here,
          "" if here else "проєкт, схоже, переносили в інше місце",
          'перевстанови пакет: pip install -e ".[dev]"')

    env = ROOT / ".env"
    if not check("Файл .env існує", env.exists(), "",
                 "виконай: cp .env.example .env"):
        _report()
        return 1

    from dotenv import load_dotenv
    load_dotenv(env)
    dsn = os.getenv("DATABASE_URL")
    check("DATABASE_URL заданий", bool(dsn), "",
          "відкрий .env і встав рядок підключення до бази")
    if not dsn:
        _report()
        return 1

    where = "хмарна база" if "localhost" not in dsn and "127.0.0.1" not in dsn \
        else "локальна база в Docker"
    print(f"{WARN}Підключення: {where}")

    print("\nПеревірка бази\n")
    try:
        from server.db import fetch
        tables = fetch("""SELECT table_name FROM information_schema.tables
                          WHERE table_schema = 'public' ORDER BY table_name""")
        names = [t["table_name"] for t in tables]
        check("База відповідає", True, f"таблиць: {len(names)}")

        missing = {"students", "lessons", "payments", "subscriptions",
                   "tutors", "support_tickets", "audit_log"} - set(names)
        check("Усі потрібні таблиці на місці", not missing,
              f"немає: {', '.join(sorted(missing))}" if missing else "",
              "заповни базу: make seed")

        if not missing:
            n = fetch("SELECT COUNT(*) AS n FROM lessons")[0]["n"]
            check("У базі є дані", n > 0, f"уроків: {n:,}", "заповни базу: make seed")
    except NotImplementedError:
        # Нормальний стан гілки workshop-start: функції доступу до бази ще
        # не написані. Це не поломка оточення, і лікується вона інакше.
        print(f"{WARN}Функції доступу до бази ще не написані")
        if problems:
            return _report()
        print("\nОточення в порядку. Саму базу перевірити поки не можна:")
        print("функції доступу до неї ми допишемо разом на воркшопі.")
        print("Побачити робочий варіант: git checkout main\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        from server.db import friendly_db_error
        check("База відповідає", False, friendly_db_error(exc),
              "перевір DATABASE_URL у .env; для локальної бази — docker compose up -d")
        _report()
        return 1

    print("\nПеревірка моделі\n")
    model = ROOT / "ml" / "model.pkl"
    if check("Модель натренована", model.exists(), "", "натренуй її: make train"):
        import pickle
        with model.open("rb") as fh:
            bundle = pickle.load(fh)
        print(f"{WARN}Якість моделі (ROC AUC): {bundle['roc_auc']}, "
              f"натреновано {bundle['trained_at']}")

    return _report()


def _report() -> int:
    print()
    if not problems:
        print("Усе готове. Далі: make config\n")
        return 0
    print("Що треба виправити:\n")
    for p in problems:
        print(f"  - {p}")
    print("\nЯкщо незрозуміло — docs/TROUBLESHOOTING.md\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
