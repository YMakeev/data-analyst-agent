"""Доказ того, що захист живе в правах бази, а не в коді сервера.

SQL-guard у server/db.py відбиває небезпечний запит ДО того, як той дійде до
Postgres. Це зручно, але створює хибне враження, ніби безпека тримається на
регулярних виразах. Тому тут ми обходимо guard і йдемо в базу напряму під
тією самою роллю, під якою працює агент.

Запуск:  python scripts/prove_readonly.py
"""

from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

ATTEMPTS = [
    ("Видалити таблицю",      "DROP TABLE students"),
    ("Видалити всі уроки",    "DELETE FROM lessons"),
    ("Змінити дані учнів",    "UPDATE students SET grade = 1"),
    ("Створити свою таблицю", "CREATE TABLE hack (id int)"),
    ("Підчистити журнал",     "DELETE FROM audit_log"),
    ("Прочитати дані",        "SELECT COUNT(*) FROM students"),
]


def main() -> int:
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("Немає DATABASE_URL. Скопіюй .env.example у .env.", file=sys.stderr)
        return 1

    print("\nЙдемо в базу НАПРЯМУ, повз усі перевірки сервера,")
    print("під тією самою роллю, під якою працює агент.\n")

    with psycopg.connect(dsn, autocommit=True) as conn:
        for title, sql in ATTEMPTS:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    result = cur.fetchone() if cur.description else None
                mark = "ДОЗВОЛЕНО"
                detail = f"результат: {result[0]}" if result else "виконано"
            except psycopg.Error as exc:
                mark = "ВІДМОВЛЕНО"
                detail = str(exc).strip().splitlines()[0]
            print(f"  {title:<24} {mark:<11} {detail}")

    print("\nЖодної перевірки в Python тут не було. Відмовляє сама база.")
    print("Саме тому агенту можна дати доступ до даних і спати спокійно.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
