#!/usr/bin/env sh
# Старт сервера в хмарі.
#
# Керована база не виконує db/init/*.sql сама — на відміну від локального
# контейнера. Тому при першому запуску схему й read-only роль розгортаємо явно.
# За замовчуванням це ВИМКНЕНО: перезаписати дані випадковим рестартом — саме
# той сюрприз, якого не хочеться. Вмикається змінною SEED_ON_START=1.

set -e

# Serverless-база (Neon, Aurora Serverless) на момент старту контейнера цілком
# може спати. Без цього очікування тренування моделі падало б об сплячу базу,
# сервер піднімався б без моделі — і predict_churn був би зламаний до
# наступного рестарту, тоді як решта інструментів працювали б нормально.
# Такий напівживий стан гірший за чесну затримку на старті.
wait_for_db() {
    i=1
    while [ "$i" -le 12 ]; do
        if python -c "
import os, sys, psycopg
try:
    with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=10,
                         prepare_threshold=None) as c:
        c.execute('SELECT 1')
except Exception as exc:
    print(exc, file=sys.stderr); sys.exit(1)
" 2>/dev/null; then
            echo "==> База відповідає (спроба $i)"
            return 0
        fi
        echo "    база ще не відповідає, спроба $i з 12"
        i=$((i + 1))
        sleep 5
    done
    echo "!! База недосяжна після 12 спроб. Перевір DATABASE_URL у змінних оточення."
    return 1
}

if [ -z "$DATABASE_URL" ]; then
    echo "!! Не задано DATABASE_URL. Додай її у Variables і перезапусти сервіс."
    exit 1
fi

wait_for_db || exit 1

if [ "$SEED_ON_START" = "1" ]; then
    echo "==> SEED_ON_START=1: розгортаю схему й роль"
    python db/bootstrap.py
    echo "==> Заливаю демо-дані"
    python db/seed.py
fi

# Модель у контейнер приїжджає готовим файлом ml/model.pkl — її тренують
# заздалегідь командою make train і перевіряють якість. Сервер нічого не
# навчає: він лише завантажує готову модель.

echo "==> Стартую MCP-сервер на порту ${PORT:-8000}"
exec python -m server.main
