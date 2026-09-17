"""Налаштування Claude Desktop для цього сервера.

    make config          показати, що треба додати
    make config-write    додати автоматично (з резервною копією)

Claude Desktop не «підключається» до сервера по адресі — він запускає його
сам, як звичайну програму. Тому в налаштуваннях вказується не посилання, а
команда запуску: який саме Python узяти і з якої теки.

Через це шляхи мають бути абсолютними. Claude Desktop працює не з тієї теки,
у якій ти сидиш у терміналі, тож «python» і «.» означають для нього зовсім
інше. Щоб не помилитись, скрипт рахує шляхи сам.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER_NAME = "ai-analyst"


def interpreter() -> str:
    """Той Python, у якому встановлені залежності проєкту."""
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def config_path() -> Path:
    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        return home / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        return home / "AppData/Roaming/Claude/claude_desktop_config.json"
    return home / ".config/Claude/claude_desktop_config.json"


def server_block() -> dict:
    return {
        "command": interpreter(),
        "args": ["-m", "server.main"],
        "cwd": str(ROOT),
    }


def show() -> None:
    target = config_path()
    exists = target.exists()

    print()
    print("Файл налаштувань Claude Desktop:")
    print(f"   {target}")
    if exists:
        print("   (файл уже є — до нього треба ДОДАТИ, а не замінити його цілком)")
    else:
        print("   (файлу ще немає — його треба створити)")

    if platform.system() == "Darwin":
        # Тека ~/Library у Finder прихована, тому просто «знайти очима» її
        # не вийде. Ця команда відкриє її напряму.
        print()
        print("Відкрити теку у Finder:")
        print(f'   open "{target.parent}"')

    print()
    print("Потрібен такий запис:")
    print()
    print(json.dumps({"mcpServers": {SERVER_NAME: server_block()}},
                     indent=2, ensure_ascii=False))

    if exists:
        try:
            current = json.loads(target.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            current = None
        if current is not None and current.keys() - {"mcpServers"}:
            print()
            print("У файлі вже є інші налаштування: "
                  f"{', '.join(sorted(current.keys() - {'mcpServers'}))}.")
            print("Їх треба зберегти — простіше довіритись команді:")
            print("   make config-write")

    print()
    print("Після зміни ПОВНІСТЮ вийди з Claude Desktop і запусти знову:")
    print("   macOS — Cmd+Q (закрити вікно недостатньо)")
    print("   Windows — вихід через іконку в треї")
    print("Налаштування читаються лише під час запуску застосунку.")
    print()

    if shutil.which("pbcopy"):
        print("Підказка: make config | pbcopy — і текст уже в буфері обміну.")
        print()


def write() -> int:
    """Додає запис у наявний файл, не чіпаючи решту налаштувань."""
    target = config_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    current: dict = {}
    if target.exists() and target.read_text(encoding="utf-8").strip():
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"Файл існує, але це не коректний JSON: {exc}", file=sys.stderr)
            print("Виправ його або перейменуй, потім повтори.", file=sys.stderr)
            return 1

        backup = target.with_suffix(
            f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
        shutil.copy2(target, backup)
        print(f"Резервна копія: {backup}")

    servers = current.setdefault("mcpServers", {})
    replaced = SERVER_NAME in servers
    servers[SERVER_NAME] = server_block()
    target.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")

    print(f"{'Оновлено' if replaced else 'Додано'} запис «{SERVER_NAME}» у {target}")
    others = sorted(current.keys() - {"mcpServers"})
    if others:
        print(f"Решта налаштувань збережена: {', '.join(others)}")
    print()
    print("Тепер ПОВНІСТЮ вийди з Claude Desktop (Cmd+Q) і запусти знову.")
    print("Далі спитай у новому чаті: «що є в цій базі?»")
    print()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Налаштування Claude Desktop")
    p.add_argument("--write", action="store_true",
                   help="додати запис у файл автоматично")
    if p.parse_args().write:
        return write()
    show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
