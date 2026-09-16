# Команди воркшопу. Якщо щось пішло не так — `make reset` і починаємо спочатку.

# Беремо .venv, якщо він є; інакше активне оточення (conda/venv); інакше системний python3.
PY := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; \
       elif [ -n "$$VIRTUAL_ENV" ]; then echo "$$VIRTUAL_ENV/bin/python"; \
       elif [ -n "$$CONDA_PREFIX" ]; then echo "$$CONDA_PREFIX/bin/python"; \
       else echo python3; fi)
ROOT := $(shell pwd)

.PHONY: help setup up down seed train run test config reset check doctor

help:
	@echo "make doctor  — перевірити, чи все готове до роботи"
	@echo "make config  — показати налаштування для Claude Desktop"
	@echo "make setup   — підняти свою базу в Docker і підготувати все з нуля"
	@echo "make train   — натренувати модель ризику відтоку"
	@echo "make run     — запустити сервер вручну, щоб побачити помилки"
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

# Перевіряє оточення, базу й модель і пояснює, що саме не так.
doctor:
	@$(PY) scripts/doctor.py

# Друкує готові налаштування для Claude Desktop з абсолютними шляхами
# саме цього комп'ютера — щоб не писати їх руками й не помилятись.
config:
	@$(PY) scripts/print_config.py

reset:
	@docker compose down -v
	@rm -f ml/model.pkl
	@$(MAKE) setup
