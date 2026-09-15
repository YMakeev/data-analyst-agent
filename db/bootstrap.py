"""Розгортання схеми й ролі в базі, яку ми не піднімали самі.

Локально файли з db/init/ виконує сам Docker при першому старті контейнера.
Керована база в хмарі (Railway, Cloud SQL, RDS) так не вміє — там є лише
готовий Postgres і DSN суперкористувача. Цей скрипт закриває різницю.

Важливо: керована база дає DSN з правами на все. Якщо підключити сервер
під ним, уся історія з read-only роллю перетворюється на декорацію. Тому
тут ми створюємо analyst_ro і в хмарі теж — саме його DSN потім іде
в змінну DATABASE_URL сервера.

Запуск:
    python db/bootstrap.py --dsn postgresql://...
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv

INIT_DIR = Path(__file__).resolve().parent / "init"
RO_USER = "analyst_ro"
RO_PASSWORD = os.getenv("ANALYST_RO_PASSWORD", "analyst_ro_pwd")


def statements(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def readonly_dsn(admin_dsn: str) -> str:
    """Той самий host і база, але під роллю лише для читання."""
    parts = urlsplit(admin_dsn)
    host = parts.hostname or "localhost"
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{RO_USER}:{RO_PASSWORD}@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="Створити схему й read-only роль")
    p.add_argument("--dsn", default=os.getenv("ADMIN_DATABASE_URL"),
                   help="DSN з правами адміністратора")
    p.add_argument("--drop", action="store_true",
                   help="Спершу знести наявні таблиці (обережно)")
    args = p.parse_args()

    if not args.dsn:
        print("Немає DSN. Передай --dsn або задай ADMIN_DATABASE_URL.", file=sys.stderr)
        return 1

    schema_sql = statements(INIT_DIR / "01_schema.sql")
    roles_sql = statements(INIT_DIR / "02_roles.sql")
    # Пароль ролі може відрізнятись від дефолтного — підставляємо фактичний.
    roles_sql = roles_sql.replace("'analyst_ro_pwd'", f"'{RO_PASSWORD}'")

    with psycopg.connect(args.dsn, autocommit=True, prepare_threshold=None) as conn:
        db_name = conn.info.dbname
        roles_sql = roles_sql.replace("DATABASE analytics", f'DATABASE "{db_name}"')

        if args.drop:
            print("==> Зношу наявні таблиці")
            conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")

        print("==> Створюю схему")
        try:
            conn.execute(schema_sql)
        except psycopg.errors.DuplicateTable:
            print("    таблиці вже є — пропускаю (--drop, щоб перестворити)")

        print(f"==> Створюю роль {RO_USER}")
        try:
            conn.execute(roles_sql)
        except psycopg.errors.DuplicateObject:
            # Роль уже є — права все одно переприсвоюємо, бо таблиці могли
            # з'явитись пізніше за роль.
            print("    роль існує — оновлюю права")
            grants = "\n".join(
                line for line in roles_sql.splitlines()
                if line.strip().upper().startswith(("GRANT", "ALTER", "REVOKE"))
            )
            conn.execute(grants)

    print("\nГотово. DSN для сервера (змінна DATABASE_URL):")
    print(f"    {readonly_dsn(args.dsn)}")
    print("\nДалі залий дані:  python db/seed.py --dsn <адмінський DSN>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
