"""Точка входу MCP-сервера.

Зараз тут один інструмент-пустишка. Решту допишемо разом на воркшопі.

Якщо відстала — `git checkout main` поверне повне рішення, і ти не випадеш
із потоку. Повертатись у workshop-start можна будь-коли.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv()

mcp = MCPServer("ai-analyst")


@mcp.tool()
def ping() -> str:
    """Перевіряє, що сервер живий. Повертає pong і назву сервера.

    Це найпростіший можливий MCP-інструмент. Зверни увагу: модель дізнається,
    що він робить і коли його викликати, НЕ з назви функції, а з цього
    докстрінга. Докстрінг і є промпт.
    """
    return "pong від ai-analyst"


def register() -> None:
    """Реєструє інструменти.

    Імпорти всередині функції навмисно: sklearn вантажиться помітно довго,
    а Claude Desktop чекає відповіді сервера на старті обмежений час.
    """
    # TODO (8-12 хв): підключити list_tables
    # TODO (15-19 хв): підключити describe_table і run_sql
    # TODO (33-38 хв): підключити save_report
    # TODO (38-45 хв): підключити predict_churn
    #
    # Реєстрація виглядатиме так:
    #     from server.tools.schema import list_tables
    #     mcp.tool()(list_tables)


def main() -> None:
    register()

    # TODO (45-50 хв): перемикач транспорту.
    # Локально Claude Desktop породжує цей процес і говорить через stdio.
    # У хмарі той самий сервер слухає HTTP — і це вся різниця між
    # «працює в мене» і «працює у всієї команди».
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
