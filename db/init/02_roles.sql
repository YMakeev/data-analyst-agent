-- Роль, під якою MCP-сервер ходить у базу.
--
-- Це головна гарантія безпеки всього рішення. SQL-guard у Python (server/db.py)
-- ловить очевидні дурниці й дає моделі зрозумілу помилку — але guard це зручність,
-- а не захист: будь-який парсер можна обійти. Захист ось тут: права, яких просто
-- немає. Навіть якщо запит пролізе повз guard, база відмовить.
--
-- На воркшопі це показується наживо: просимо Claude видалити таблицю.
-- Він щиро намагається — і отримує permission denied.

CREATE ROLE analyst_ro WITH LOGIN PASSWORD 'analyst_ro_pwd';

GRANT CONNECT ON DATABASE analytics TO analyst_ro;
GRANT USAGE ON SCHEMA public TO analyst_ro;

-- Читати — все.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analyst_ro;

-- Писати — лише в журнал власних звернень, і лише додавати.
-- UPDATE і DELETE не даємо свідомо: лог, який агент може підчистити,
-- не є логом.
GRANT INSERT ON audit_log TO analyst_ro;
GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO analyst_ro;

-- Таблиці, створені пізніше (наприклад, коли учасник додасть свою),
-- теж автоматично будуть доступні на читання.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO analyst_ro;

-- Явно забороняємо створювати щось у схемі: агент не має розкладати
-- тимчасові таблиці в робочій базі.
REVOKE CREATE ON SCHEMA public FROM analyst_ro;

-- Страховка від запиту, який випадково вичитає півбази і підвісить з'єднання.
-- Дублює SQL_TIMEOUT_SECONDS з .env — навмисно, бо ліміт на рівні бази
-- діє навіть якщо сервер зламали або переписали.
ALTER ROLE analyst_ro SET statement_timeout = '15s';
ALTER ROLE analyst_ro SET idle_in_transaction_session_timeout = '30s';
