# Підготовка до воркшопу

**Зроби це заздалегідь, не в день воркшопу.** Нам буде 50 хвилин на код —
витрачати їх на встановлення Docker не вийде. Усе разом займає хвилин
п'ятнадцять, більшість з яких качається саме.

---

## 1. Docker

Потрібен, щоб підняти базу даних однією командою.

[Docker Desktop](https://www.docker.com/products/docker-desktop/) — постав і
**запусти застосунок**. Він має працювати у фоні, інакше команди не пройдуть.

```bash
docker --version
docker info
```

Друга команда має видати кілька екранів тексту. Якщо каже
`Cannot connect to the Docker daemon` — Docker Desktop не запущений.

## 2. Python 3.10 або новіший

```bash
python3 --version
```

Якщо там 3.9 або менше — постав новіший. Варіанти:

- **macOS**: завантаж з [python.org](https://www.python.org/downloads/) або `brew install python@3.12`
- **Windows**: з [python.org](https://www.python.org/downloads/), обов'язково постав галочку «Add Python to PATH»
- **Linux**: `sudo apt install python3.12 python3.12-venv`

**Якщо користуєшся Anaconda:** перевір, що твоє оточення справді на 3.10+,
`conda activate` потрібного середовища. На Mac з процесором Apple Silicon
переконайся, що Python не x86-збірка — інакше частина пакетів
збиратиметься з сорсів по пів години:

```bash
python3 -c "import platform; print(platform.machine())"
```

Має бути `arm64`. Якщо `x86_64` на новому Mac — візьми Python з python.org.

## 3. Claude Desktop

[claude.ai/download](https://claude.ai/download). Зайди у свій акаунт.
Підписка Pro не обов'язкова, але з нею живіше.

## 4. Проєкт

```bash
git clone <URL-репозиторію>
cd data-analyst-agent
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
make setup
```

`make setup` підніме базу, поставить залежності, згенерує дані й натренує
модель. Дві-три хвилини.

---

## Перевірка, що все готове

```bash
make test
```

Має бути `50 passed`. Якщо так — ти повністю готова, далі можна не читати.

> **Підготовку роби на гілці `main`** — там повне рішення, і тести мають
> проходити. На початку воркшопу ми перемкнемось на `workshop-start`, де
> частина коду навмисно не написана: її ми набираємо разом. База, дані й
> модель від перемикання гілки нікуди не діваються. Деталі —
> [WORKSHOP-START.md](WORKSHOP-START.md).

Якщо хочеться переконатись руками:

```bash
docker compose ps                 # контейнер analyst-db має бути running
.venv/bin/python -c "from server.tools.schema import list_tables; print(len(list_tables()['tables']), 'таблиць')"
```

---

## Підключення до Claude Desktop

Це ми зробимо разом на воркшопі, але якщо хочеш спробувати заздалегідь:

```bash
make config
```

Команда надрукує готовий JSON саме для твоєї машини. Скопіюй його у файл
конфігурації Claude Desktop (шлях команда теж покаже) і **повністю перезапусти
Claude Desktop** — Cmd+Q на Mac, вихід із трею на Windows. Просто закрити
вікно недостатньо: конфіг читається лише при старті.

Потім спитай у Claude: *«що є в цій базі?»*. Якщо він перелічив сім таблиць —
працює.

Не вийшло — [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md). І не переживай,
на воркшопі розберемось разом.

---

## Якщо щось зовсім не встановлюється

Приходь усе одно. Буде резервний варіант: спільна база в хмарі, до якої можна
під'єднатись без Docker. Напиши про це заздалегідь, щоб я підготувала доступ.
