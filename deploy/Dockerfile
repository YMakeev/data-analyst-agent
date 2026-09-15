# Образ MCP-сервера для деплою на команду.
#
# Зверни увагу, чого тут НЕМАЄ: жодного окремого «серверного» коду. Той самий
# server/, який локально спілкувався з Claude Desktop через stdin, тут слухає
# HTTP. Різниця — одна змінна оточення.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_TRANSPORT=http \
    HOST=0.0.0.0

WORKDIR /app

# Спершу тільки метадані — шар із залежностями кешується й не перезбирається
# на кожну зміну коду.
COPY pyproject.toml README.md ./
COPY server ./server
RUN pip install --no-cache-dir .

COPY ml ./ml
COPY db ./db
COPY deploy/entrypoint.sh ./deploy/entrypoint.sh
RUN chmod +x deploy/entrypoint.sh && mkdir -p reports

# Railway підставляє свій PORT у змінну оточення; 8000 — просто дефолт.
EXPOSE 8000

CMD ["./deploy/entrypoint.sh"]
