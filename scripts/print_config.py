"""Друкує готовий конфіг для Claude Desktop з абсолютними шляхами цієї машини.

Найчастіша причина, чому на воркшопі «сервер не підключається» — відносний
шлях або не той інтерпретатор. Тому шлях до Python і до проєкту ми не
пояснюємо словами, а рахуємо й друкуємо.
"""

from __future__ import annotations

import json
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def interpreter() -> str:
    """Той Python, у якому встановлені залежності проєкту."""
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.exists():
        return str(venv)
    return sys.executable


def config_path() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        return home / "Library/Application Support/Claude/claude_desktop_config.json"
    if platform.system() == "Windows":
        return home / "AppData/Roaming/Claude/claude_desktop_config.json"
    return home / ".config/Claude/claude_desktop_config.json"


def main() -> None:
    block = {
        "mcpServers": {
            "ai-analyst": {
                "command": interpreter(),
                "args": ["-m", "server.main"],
                "cwd": str(ROOT),
            }
        }
    }

    target = config_path()
    print()
    print("1. Відкрий цей файл (якщо його немає — створи):")
    print(f"   {target}")
    print()
    print("2. Встав у нього цей блок. Якщо в файлі вже є mcpServers —")
    print("   додай туди тільки внутрішню частину 'ai-analyst'.")
    print()
    print(json.dumps(block, indent=2, ensure_ascii=False))
    print()
    print("3. Повністю вийди з Claude Desktop (Cmd+Q, не просто закрий вікно)")
    print("   і запусти знову. Конфіг читається лише на старті.")
    print()

    if shutil.which("pbcopy"):
        print("   Підказка: make config | pbcopy — і конфіг уже в буфері.")
        print()


if __name__ == "__main__":
    main()
