# Команди воркшопу. Якщо щось пішло не так — `make reset` і починаємо спочатку.

# Беремо .venv, якщо він є; інакше активне оточення (conda/venv); інакше системний python3.
PY := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; \
       elif [ -n "$$VIRTUAL_ENV" ]; then echo "$$VIRTUAL_ENV/bin/python"; \
       elif [ -n "$$CONDA_PREFIX" ]; then echo "$$CONDA_PREFIX/bin/python"; \
       else echo python3; fi)
ROOT := $(shell pwd)

.PHONY: help setup up down seed train run test config reset check

help:
	@echo "make setup   — повний сетап: база + залежності + дані + модель"
	@echo "make config  — показати JSON для Claude Desktop (з правильними шляхами)"
	@echo "make run     — запустити MCP-сервер вручну (для дебагу)"
	@echo "make test    — прогнати тести"
	@echo "make reset   — знести базу і зібрати заново"

check:
	@$(PY) -c "import sys; v=sys.version_info; \
	sys.exit(0) if v>=(3,10) else (print(f'Потрібен Python 3.10+, а тут {v.major}.{v.minor}. Див. docs/SETUP.md') or sys.exit(1))"
	@docker info >/dev/null 2>&1 || (echo "Docker не запущений. Відкрий Docker Desktop і повтори."; exit 1)

setup: check up
	@echo "==> Ставлю залежності"
	@$(PY) -m pip install -q -e ".[dev]"
	@[ -f .env ] || cp .env.example .env
	@$(MAKE) seed
	@$(MAKE) train
	@echo ""
	@echo "Готово. Далі:  make config"

up:
	@echo "==> Піднімаю Postgres"
	@docker compose up -d
	@printf "==> Чекаю на базу"
	@until docker compose exec -T db pg_isready -U postgres -d analytics >/dev/null 2>&1; do printf "."; sleep 1; done
	@echo " ok"

down:
	@docker compose down

seed:
	@echo "==> Генерую дані"
	@$(PY) db/seed.py

train:
	@echo "==> Треную churn-модель"
	@$(PY) ml/train.py

run:
	@$(PY) -m server.main

test:
	@$(PY) -m pytest -q

# Друкує готовий блок для claude_desktop_config.json з абсолютними шляхами.
# Без цього половина залу воює зі шляхами замість того, щоб слухати.
config:
	@$(PY) scripts/print_config.py

reset:
	@docker compose down -v
	@rm -f ml/model.pkl
	@$(MAKE) setup
