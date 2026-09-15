"""Точка входу MCP-сервера.

Тут майже немає логіки — тільки реєстрація інструментів і вибір транспорту.
І саме цей файл містить головний сюрприз воркшопу: різниця між «локальна
іграшка на моєму ноутбуці» і «сервіс для всієї команди» — це кілька рядків
у функції main(). Увесь код інструментів однаковий.

Локально Claude Desktop сам запускає цей процес і спілкується з ним через
stdin/stdout. У хмарі той самий сервер слухає HTTP, і до нього під'єднується
вся команда за одним URL.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv()

# instructions — це підказка рівня всього сервера, яку модель читає до того,
# як почне викликати інструменти. Дешевий спосіб задати правила гри один раз,
# замість того щоб повторювати їх у кожному docstring.
INSTRUCTIONS = """
Ти працюєш з базою даних сервісу онлайн-репетиторства через набір інструментів.

Порядок роботи, який дає правильні відповіді:
1. list_tables — побачити, що є в базі.
2. describe_table для потрібних таблиць — ОБОВ'ЯЗКОВО перед першим запитом
   до незнайомої таблиці. У коментарях до колонок описані особливості даних,
   без яких результат буде правдоподібним, але неправильним.
3. run_sql — виконати запит.

База підключена в режимі тільки для читання. Змінити дані неможливо.

Якщо треба візуалізація — згенеруй HTML-звіт сам і збережи через save_report.
Окремого інструмента для побудови графіків немає і не потрібно.

Коли рахуєш бізнес-метрики, завжди перевіряй у коментарях до колонок, які
рядки треба виключити і які значення статусу означають потрібну подію.
""".strip()

mcp = MCPServer("ai-analyst", instructions=INSTRUCTIONS)


def register() -> None:
    """Реєструє інструменти.

    Імпорти всередині функції навмисно: sklearn вантажиться помітно довго,
    а Claude Desktop чекає відповіді сервера на старті обмежений час.
    """
    from server.tools.ml import predict_churn
    from server.tools.report import save_report
    from server.tools.schema import describe_table, list_tables
    from server.tools.sql import run_sql

    # Опис інструмента для моделі — це його docstring. Не назва функції, не
    # назва файлу. Змінюєш docstring — змінюєш поведінку Claude.
    for fn in (list_tables, describe_table, run_sql, save_report, predict_churn):
        mcp.tool()(fn)


def main() -> None:
    register()

    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http"):
        # Один інстанс на всю команду. Креденшели до бази лишаються тут,
        # людям не роздаються.
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        print(f"ai-analyst: HTTP на {host}:{port}/mcp", file=sys.stderr)
        mcp.run(transport="streamable-http", host=host, port=port)
    else:
        # Claude Desktop породжує цей процес сам і говорить через stdio.
        # Друкувати у stdout не можна — там протокол. Тільки stderr.
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
