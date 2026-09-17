import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "/Users/hannapylieva/Projects/data-analyst-agent";
const SKILL_DIR = "/Users/hannapylieva/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations";
const RUNTIME_PYTHON = "/Users/hannapylieva/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const buildDir = path.join(workspaceDir, ".codex-build/presentation");
const assetsDir = path.join(workspaceDir, ".codex-build/assets");
const finalPath = path.join(workspaceDir, "deliverables/ai-analyst-mcp-workshop-participant-final-v2.pptx");
const TOTAL = 34;

const C = {
  navy: "#0F0F3E",
  deep: "#131348",
  purple: "#1E125E",
  violet: "#440FAC",
  indigo: "#444BD0",
  periwinkle: "#6676EC",
  lavender: "#9EA7FF",
  pale: "#C8C9E8",
  line: "#3E3D78",
  lime: "#D6F134",
  white: "#FFFFFF",
  offWhite: "#F5F5FA",
  ink: "#101340",
  muted: "#98A2B3",
  docker: "#2496ED",
  pythonYellow: "#FFD343",
  postgres: "#4169E1",
  orange: "#F7931E",
  red: "#F05A4F",
  green: "#49C17A",
};
const FONT = "Arial";

const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

function shape(slide, geometry, left, top, width, height, fill = "none", lineFill = "none", lineWidth = 0, radius = undefined) {
  return slide.shapes.add({
    geometry,
    position: { left, top, width, height },
    fill,
    line: { style: "solid", fill: lineFill, width: lineWidth },
    ...(radius !== undefined ? { borderRadius: radius } : {}),
  });
}

function text(slide, value, left, top, width, height, options = {}) {
  const box = shape(slide, "textbox", left, top, width, height, options.fill ?? "none", options.lineFill ?? "none", options.lineWidth ?? 0, options.radius);
  box.text = value;
  box.text.style = {
    typeface: FONT,
    fontSize: options.fontSize ?? 26,
    bold: options.bold ?? false,
    color: options.color ?? C.white,
    alignment: options.align ?? "left",
    verticalAlignment: options.valign ?? "top",
    autoFit: options.autoFit ?? "none",
    wrap: "square",
    lineSpacing: options.lineSpacing ?? 1.0,
    insets: options.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
  };
  return box;
}

function title(slide, value, light = false) {
  const size = value.length > 64 ? 39 : value.length > 48 ? 42 : 46;
  return text(slide, value, 72, 48, 1130, 110, {
    fontSize: size,
    bold: true,
    color: light ? C.ink : C.white,
    valign: "top",
  });
}

function tag(slide, value, left, top, width, options = {}) {
  return text(slide, value, left, top, width, options.height ?? 34, {
    fill: options.fill ?? C.lime,
    color: options.color ?? C.ink,
    fontSize: options.fontSize ?? 15,
    bold: true,
    align: "center",
    valign: "middle",
    radius: 20,
    insets: { top: 4, right: 8, bottom: 4, left: 8 },
  });
}

function footer(slide, number, light = false) {
  shape(slide, "rect", 0, 0, 14, 720, C.periwinkle);
  text(slide, String(number).padStart(2, "0"), 1192, 666, 35, 20, {
    fontSize: 13,
    bold: true,
    color: light ? C.ink : C.pale,
    align: "right",
  });
}

function baseSlide(number, options = {}) {
  const slide = presentation.slides.add();
  slide.background.fill = options.light ? C.offWhite : (options.background ?? C.navy);
  if (number > 1) footer(slide, number, options.light ?? false);
  return slide;
}

async function image(slide, filename, left, top, width, height, options = {}) {
  const p = path.join(assetsDir, filename);
  const ext = path.extname(filename).toLowerCase();
  const contentType = ext === ".svg" ? "image/svg+xml" : "image/png";
  return slide.images.add({
    blob: await fs.readFile(p),
    contentType,
    alt: options.alt ?? filename,
    fit: options.fit ?? "contain",
    position: { left, top, width, height },
    ...(options.geometry ? { geometry: options.geometry } : {}),
    ...(options.crop ? { crop: options.crop } : {}),
  });
}

function card(slide, left, top, width, height, options = {}) {
  return shape(slide, "roundRect", left, top, width, height, options.fill ?? C.purple, options.lineFill ?? C.line, options.lineWidth ?? 1.2, options.radius ?? 20);
}

function cardText(slide, heading, body, left, top, width, height, options = {}) {
  card(slide, left, top, width, height, options);
  if (options.kicker) {
    text(slide, options.kicker, left + 20, top + 18, width - 40, 24, {
      fontSize: 15, bold: true, color: options.kickerColor ?? C.periwinkle,
    });
  }
  text(slide, heading, left + 20, top + (options.kicker ? 56 : 28), width - 40, options.headingHeight ?? 62, {
    fontSize: options.headingSize ?? 26,
    bold: true,
    color: options.headingColor ?? C.white,
    valign: "middle",
  });
  if (body) {
    text(slide, body, left + 20, top + (options.bodyTop ?? 105), width - 40, height - (options.bodyTop ?? 105) - 18, {
      fontSize: options.bodySize ?? 20,
      color: options.bodyColor ?? C.pale,
      lineSpacing: 1.06,
    });
  }
}

function connect(slide, from, to, options = {}) {
  return slide.shapes.connect(from, to, {
    kind: options.kind ?? "straight",
    fromSide: options.fromSide ?? "right",
    toSide: options.toSide ?? "left",
    line: { style: options.style ?? "solid", fill: options.color ?? C.lavender, width: options.width ?? 2 },
    head: { type: "none" },
    tail: options.head === false ? { type: "none" } : { type: "triangle", width: "sm", length: "sm" },
  });
}

function numberDot(slide, value, left, top, options = {}) {
  const dot = shape(slide, "ellipse", left, top, options.size ?? 34, options.size ?? 34, options.fill ?? C.indigo);
  text(slide, String(value), left, top + 1, options.size ?? 34, (options.size ?? 34) - 2, {
    fontSize: options.fontSize ?? 15, bold: true, align: "center", valign: "middle", color: options.color ?? C.white,
  });
  return dot;
}

function codeBlock(slide, code, left, top, width, height, options = {}) {
  card(slide, left, top, width, height, { fill: options.fill ?? C.deep, lineFill: options.lineFill ?? C.line, radius: 16 });
  if (options.label) tag(slide, options.label, left + 16, top + 14, options.labelWidth ?? 110, { fill: options.labelFill ?? C.lime, height: 28, fontSize: 13 });
  text(slide, code, left + 20, top + (options.label ? 54 : 20), width - 40, height - (options.label ? 70 : 40), {
    fontSize: options.fontSize ?? 20,
    color: options.color ?? C.white,
    lineSpacing: 1.08,
  });
}

function notes(slide, value) {
  slide.speakerNotes.textFrame.setText(value);
  slide.speakerNotes.setVisible(true);
}

// 1 — cover
{
  const s = baseSlide(1, { background: C.navy });
  await image(s, "ai-analyst-cover-16x9.png", 0, 0, 1280, 720, { alt: "AI-аналітикиня з ноутбуком та візуальною схемою потоків даних", fit: "cover" });
  await image(s, "data-loves-logo.png", 72, 40, 300, 72, { alt: "Data Loves Academy" });
  text(s, "AI-аналітик\nнад базою даних", 72, 178, 650, 165, { fontSize: 64, bold: true, lineSpacing: 0.92, valign: "middle" });
  text(s, "Будуємо аналітика даних як MCP для Claude", 76, 382, 610, 82, { fontSize: 29, color: C.pale, bold: true, lineSpacing: 1.04 });
  notes(s, `Таймінг: 00:00–00:30\n\nВідкриття:\n«Сьогодні ми не будемо вчити всі слова зі світу розробки. Ми зберемо одну зрозумілу систему від питання людини до відповіді з бази і винесемо її в хмару».\n\nПопросіть підняти руку тих, хто ніколи не запускав Docker або MCP. Це нормальна стартова точка.`);
}

// 2 — route
{
  const s = baseSlide(2);
  title(s, "Протягом воркшопу ми пройдемо весь шлях");
  const items = [
    ["Термінологія", "GitHub, Docker, база, MCP"],
    ["Як працює агент", "архітектура, інструменти, безпека"],
    ["Локальний запуск", "підготовка та живе демо"],
    ["Хмара", "Docker-образ, Railway, підключення"],
  ];
  items.forEach((it, i) => {
    const x = 72 + i * 292;
    cardText(s, it[0], it[1], x, 190, 260, 280, { headingSize: 27, headingHeight: 78, bodySize: 20, bodyTop: 135, fill: i === 3 ? C.indigo : C.purple, headingColor: i === 3 ? C.ink : C.white, bodyColor: i === 3 ? C.ink : C.pale });
  });
  text(s, "Питання можна ставити по ходу", 72, 530, 1135, 40, { fontSize: 22, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 00:30–01:15\n\nПокажіть маршрут і домовтесь: питання можна ставити по ходу, але довгі розбори підуть після основного маршруту.\n\nКлючова обіцянка: наприкінці людина розуміє не лише «які команди вставити», а й навіщо існує кожна частина.`);
}

// 3 — outcome
{
  const s = baseSlide(3);
  title(s, "Звичайне питання стає перевіреною відповіддю");
  const prompt = card(s, 78, 202, 410, 170, { fill: C.offWhite, lineFill: C.pale, radius: 24 });
  text(s, "«Скільки уроків ми провели минулого місяця?»", 110, 232, 346, 110, { fontSize: 30, bold: true, color: C.ink, align: "center", valign: "middle" });
  const answer = card(s, 790, 202, 410, 170, { fill: C.indigo, lineFill: C.indigo, radius: 24 });
  text(s, "1 284 уроки", 820, 232, 350, 56, { fontSize: 42, bold: true, color: C.ink, align: "center" });
  text(s, "із SQL, поясненням і можливістю зберегти звіт", 825, 300, 340, 58, { fontSize: 21, color: C.ink, align: "center" });
  const middle = card(s, 545, 202, 180, 170, { fill: C.purple, lineFill: C.periwinkle, radius: 18 });
  text(s, "АГЕНТ", 565, 228, 140, 35, { fontSize: 26, bold: true, color: C.lime, align: "center" });
  text(s, "перевіряє схему\nпише SELECT", 565, 284, 140, 70, { fontSize: 19, color: C.white, align: "center" });
  connect(s, prompt, middle);
  connect(s, middle, answer);
  text(s, "Наша мета — зробити цей шлях видимим і контрольованим", 160, 455, 960, 52, { fontSize: 28, bold: true, color: C.white, align: "center" });
  notes(s, `Таймінг: 01:15–02:15\n\nПочніть із конкретного питання. Поясніть, що цифра на слайді ілюстративна: на демо побачимо реальну відповідь із поточного набору даних.\n\nГоловна думка: користувач не пише SQL, але система все одно показує, що саме було виконано.`);
}

// 4 — workshop task
{
  const s = baseSlide(4);
  title(s, "Що ми будемо робити");
  text(s, "Підключимо Claude до PostgreSQL через MCP-сервер", 110, 150, 1060, 76, { fontSize: 38, bold: true, color: C.white, align: "center", valign: "middle" });
  const a = card(s, 110, 305, 245, 150, { fill: C.indigo, lineFill: C.indigo });
  const b = card(s, 515, 305, 245, 150, { fill: C.purple, lineFill: C.periwinkle });
  const c = card(s, 925, 305, 245, 150, { fill: C.purple, lineFill: C.periwinkle });
  text(s, "Людина + Claude", 135, 350, 195, 58, { fontSize: 27, bold: true, color: C.ink, align: "center", valign: "middle" });
  text(s, "MCP-сервер", 540, 350, 195, 58, { fontSize: 29, bold: true, align: "center", valign: "middle" });
  text(s, "PostgreSQL", 950, 350, 195, 58, { fontSize: 29, bold: true, align: "center", valign: "middle" });
  connect(s, a, b, { color: C.lime, width: 3 });
  connect(s, b, c, { color: C.lime, width: 3 });
  text(s, "Сервер дає Claude п’ять дозволених функцій", 300, 530, 680, 42, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 02:15–03:15\n\nСкажіть одним подихом: «Ми не даємо Claude пароль і свободу робити будь-що. Ми даємо серверу п’ять чітко описаних функцій».\n\nЦе рамка для всього воркшопу.`);
}

// 5 — glossary
{
  const s = baseSlide(5);
  title(s, "Наш словник термінів на сьогодні");
  const rows = [
    ["Модель", "генерує наступний крок або текст"],
    ["Агент", "повторює цикл: подумав, викликав, перевірив"],
    ["Інструмент", "звичайна функція з чітким входом і виходом"],
    ["MCP", "правила розмови клієнта з інструментами"],
    ["База", "структуровано зберігає дані"],
    ["Деплой", "процес розгортання сервісу, щоб він був доступний іншим користувачам"],
  ];
  rows.forEach((r, i) => {
    const y = 145 + i * 80;
    numberDot(s, i + 1, 88, y + 4, { size: 34 });
    text(s, r[0], 144, y, 230, 42, { fontSize: 25, bold: true, color: i === 3 ? C.lime : C.white, valign: "middle" });
    text(s, r[1], 380, y, 780, 42, { fontSize: 23, color: C.pale, valign: "middle" });
    if (i < 5) shape(s, "rect", 145, y + 56, 1015, 1, C.line);
  });
  notes(s, `Таймінг: 03:15–04:30\n\nПройдіть визначення без заглиблення.\n\nПобутова аналогія: модель — мозок, агент — поведінка, інструменти — руки, MCP — розетка стандартного формату, база — склад, деплой — відкрита майстерня в хмарі.`);
}

// 6 — Git and GitHub
{
  const s = baseSlide(6);
  title(s, "Git зберігає історію, GitHub — репозиторій онлайн");
  card(s, 92, 170, 500, 350, { fill: C.purple, lineFill: C.line });
  card(s, 688, 170, 500, 350, { fill: C.purple, lineFill: C.line });
  await image(s, "git.png", 130, 215, 110, 110, { alt: "Git" });
  await image(s, "github.png", 735, 215, 110, 110, { alt: "GitHub" });
  text(s, "Git", 270, 215, 270, 56, { fontSize: 38, bold: true });
  text(s, "«машина часу» для файлів", 270, 280, 270, 42, { fontSize: 23, color: C.pale });
  text(s, "commit = збережена версія\nbranch = окрема лінія роботи", 130, 360, 410, 100, { fontSize: 23, color: C.white, lineSpacing: 1.1 });
  text(s, "GitHub", 875, 215, 270, 56, { fontSize: 38, bold: true });
  text(s, "хостинг для Git-репозиторію", 875, 280, 270, 42, { fontSize: 23, color: C.pale });
  text(s, "clone = завантажити копію\npush = відправити зміни", 735, 360, 410, 100, { fontSize: 23, color: C.white, lineSpacing: 1.1 });
  text(s, "Railway бере код саме з GitHub", 340, 565, 600, 38, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 04:30–06:00\n\nПояснення для новачка:\nGit працює і без інтернету та пам’ятає версії. GitHub — сайт, де репозиторій лежить онлайн, ним можна ділитись і підключити Railway.\n\nУ цьому проєкті є дві гілки: main і workshop-start.\n\nДжерело: https://docs.github.com/en/get-started/learning-to-code/getting-started-with-git`);
}

// 7 — Docker
{
  const s = baseSlide(7, { light: true });
  title(s, "Docker дає однакове середовище на кожному комп’ютері", true);
  await image(s, "docker.png", 90, 180, 300, 260, { alt: "Docker" });
  text(s, "Контейнер", 455, 180, 600, 54, { fontSize: 38, bold: true, color: C.ink });
  text(s, "Ізольований процес із потрібною версією програми та її налаштуваннями", 455, 250, 675, 90, { fontSize: 27, color: C.ink, lineSpacing: 1.05 });
  const img = card(s, 455, 380, 300, 120, { fill: "#E8E9FA", lineFill: C.pale });
  const run = card(s, 820, 380, 300, 120, { fill: C.indigo, lineFill: C.indigo });
  text(s, "Образ", 485, 400, 240, 35, { fontSize: 27, bold: true, color: C.ink, align: "center" });
  text(s, "рецепт", 485, 446, 240, 30, { fontSize: 21, color: C.ink, align: "center" });
  text(s, "Контейнер", 850, 400, 240, 35, { fontSize: 27, bold: true, color: C.ink, align: "center" });
  text(s, "запущена страва", 850, 446, 240, 30, { fontSize: 21, color: C.ink, align: "center" });
  connect(s, img, run, { color: C.indigo, width: 3 });
  text(s, "У нас Docker локально запускає PostgreSQL", 455, 548, 680, 38, { fontSize: 24, bold: true, color: C.violet });
  notes(s, `Таймінг: 06:00–07:30\n\nАналогія: образ — рецепт і запаковані інгредієнти, контейнер — конкретно запущена страва. Один образ можна запускати багато разів.\n\nУ docker-compose.yml описано один сервіс db на PostgreSQL 16 Alpine. Порт 5433 зовні навмисно уникає конфлікту зі звичайним 5432.\n\nДжерело: https://docs.docker.com/get-started/docker-overview/`);
}

// 8 — Python and PostgreSQL
{
  const s = baseSlide(8);
  title(s, "Python виконує логіку, PostgreSQL зберігає дані");
  card(s, 90, 170, 500, 370, { fill: C.purple, lineFill: C.line });
  card(s, 690, 170, 500, 370, { fill: C.purple, lineFill: C.line });
  await image(s, "python.png", 130, 215, 120, 120, { alt: "Python" });
  await image(s, "postgresql.png", 730, 215, 120, 120, { alt: "PostgreSQL" });
  text(s, "Python", 285, 220, 250, 45, { fontSize: 37, bold: true });
  text(s, "server/\nінструменти\nML-модель", 130, 370, 395, 120, { fontSize: 26, bold: true, lineSpacing: 1.15 });
  text(s, "PostgreSQL", 880, 220, 265, 45, { fontSize: 37, bold: true });
  text(s, "таблиці\nзв’язки\nправа доступу", 730, 370, 395, 120, { fontSize: 26, bold: true, lineSpacing: 1.15 });
  text(s, "psycopg = бібліотека-мостик між Python і PostgreSQL", 210, 585, 860, 36, { fontSize: 24, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 07:30–09:00\n\nPython — мова, якою написано сервер і ML. PostgreSQL — окрема програма-база. psycopg відкриває з’єднання та передає SQL.\n\nПідкресліть: дані не живуть «у Python-файлі». Сервер лише приходить до бази, читає і повертає результат.`);
}

// 9 — MCP messages
{
  const s = baseSlide(9);
  title(s, "MCP задає формат повідомлень");
  await image(s, "mcp.png", 82, 205, 210, 210, { alt: "Model Context Protocol" });
  const messageTypes = [
    ["tools/list", "які інструменти доступні"],
    ["tools/call", "який інструмент викликати"],
    ["result", "що повернув сервер"],
  ];
  messageTypes.forEach((r, i) => {
    const x = 350 + i * 285;
    card(s, x, 205, 245, 225, { fill: i === 1 ? C.indigo : C.purple, lineFill: i === 1 ? C.indigo : C.line, radius: 18 });
    text(s, r[0], x + 20, 250, 205, 44, { fontSize: 25, bold: true, color: i === 1 ? C.ink : C.white, align: "center" });
    text(s, r[1], x + 20, 325, 205, 70, { fontSize: 20, color: i === 1 ? C.ink : C.pale, align: "center", lineSpacing: 1.05 });
  });
  text(s, "Claude аналізує. Сервер виконує функцію. MCP переносить повідомлення", 180, 520, 920, 62, { fontSize: 26, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 09:00–09:45\n\nПоясніть MCP як домовленість про формат повідомлень. Клієнт спершу запитує список інструментів, потім викликає потрібний і отримує структурований результат.\n\nMCP не виконує аналіз самостійно: рішення приймає Claude, а Python-функцію виконує наш сервер.`);
}

// 10 — MCP connection
{
  const s = baseSlide(10);
  title(s, "MCP з’єднує Claude з інструментами");
  await image(s, "mcp.png", 90, 190, 210, 210, { alt: "Model Context Protocol" });
  const client = card(s, 370, 190, 300, 190, { fill: C.indigo, lineFill: C.indigo });
  const server = card(s, 840, 190, 300, 190, { fill: C.purple, lineFill: C.periwinkle });
  text(s, "Клієнт", 410, 230, 220, 42, { fontSize: 31, bold: true, color: C.ink, align: "center" });
  text(s, "Claude Desktop", 410, 292, 220, 36, { fontSize: 23, color: C.ink, align: "center" });
  text(s, "Сервер", 880, 230, 220, 42, { fontSize: 31, bold: true, align: "center" });
  text(s, "наші 5 інструментів", 880, 292, 220, 36, { fontSize: 23, color: C.pale, align: "center" });
  connect(s, client, server, { color: C.lime, width: 4 });
  tag(s, "СТАНДАРТНИЙ ПРОТОКОЛ", 560, 410, 380, { height: 36 });
  text(s, "Клієнт бачить назву, опис, аргументи та результат кожного інструмента", 240, 500, 850, 70, { fontSize: 27, bold: true, align: "center", color: C.white });
  notes(s, `Таймінг: 09:45–10:45\n\nАналогія: USB-C задає зрозумілий спосіб з’єднання різних пристроїв. MCP так само дає клієнту стандартний спосіб побачити та викликати інструменти сервера.\n\nУ специфікації MCP сервер може давати tools, resources і prompts. У цьому демо головне — tools.\n\nДжерело: https://modelcontextprotocol.io/specification/draft/server/index`);
}

// 11 — model agent tools
{
  const s = baseSlide(11);
  title(s, "Модель, агент і інструменти мають різні ролі");
  const xs = [80, 455, 830];
  const specs = [
    ["1", "Модель", "вирішує, що робити далі"],
    ["2", "Агентний цикл", "викликає функцію та читає результат"],
    ["3", "Інструмент", "детерміновано виконує одну дію"],
  ];
  const boxes = [];
  specs.forEach((r, i) => {
    const b = card(s, xs[i], 205, 300, 255, { fill: i === 1 ? C.indigo : C.purple, lineFill: i === 1 ? C.indigo : C.line });
    boxes.push(b);
    numberDot(s, r[0], xs[i] + 24, 230, { fill: i === 1 ? C.ink : C.indigo, color: i === 1 ? C.white : C.white });
    text(s, r[1], xs[i] + 24, 290, 250, 46, { fontSize: 30, bold: true, color: i === 1 ? C.ink : C.white });
    text(s, r[2], xs[i] + 24, 355, 250, 70, { fontSize: 22, color: i === 1 ? C.ink : C.pale, lineSpacing: 1.05 });
  });
  connect(s, boxes[0], boxes[1], { color: C.lime });
  connect(s, boxes[1], boxes[2], { color: C.lime });
  text(s, "У коді ми пишемо інструменти. Послідовність обирає Claude", 190, 535, 900, 48, { fontSize: 27, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 10:45–11:45\n\nClaude як модель обирає крок. Агентний цикл виконує послідовність кроків. Python-функції роблять конкретну роботу.\n\nУ цьому проєкті немає вручну прописаного маршруту list_tables, describe_table, run_sql. Модель складає його під запит.`);
}

// 12 — architecture
{
  const s = baseSlide(12);
  title(s, "Доступ до даних проходить через MCP-сервер");
  const user = card(s, 70, 210, 205, 150, { fill: C.indigo, lineFill: C.indigo });
  const mcp = card(s, 390, 180, 300, 210, { fill: C.purple, lineFill: C.periwinkle });
  const db = card(s, 830, 140, 320, 150, { fill: C.purple, lineFill: C.periwinkle });
  const ml = card(s, 830, 350, 320, 120, { fill: C.purple, lineFill: C.line });
  const report = card(s, 390, 480, 300, 105, { fill: C.offWhite, lineFill: C.pale });
  text(s, "Людина\n+ Claude", 100, 248, 145, 72, { fontSize: 28, bold: true, color: C.ink, align: "center", valign: "middle" });
  text(s, "MCP-сервер", 430, 210, 220, 42, { fontSize: 31, bold: true, align: "center" });
  text(s, "5 інструментів\nперевірки\nжурнал", 430, 280, 220, 86, { fontSize: 21, color: C.pale, align: "center", lineSpacing: 1.05 });
  text(s, "PostgreSQL", 880, 175, 220, 40, { fontSize: 30, bold: true, align: "center" });
  text(s, "read-only роль", 880, 228, 220, 32, { fontSize: 21, color: C.lime, align: "center" });
  text(s, "ML-модель", 880, 380, 220, 38, { fontSize: 28, bold: true, align: "center" });
  text(s, "готовий model.pkl", 880, 426, 220, 28, { fontSize: 20, color: C.pale, align: "center" });
  text(s, "HTML-звіт", 430, 510, 220, 36, { fontSize: 28, bold: true, color: C.ink, align: "center" });
  connect(s, user, mcp, { color: C.lime, width: 3 });
  connect(s, mcp, db, { color: C.lavender, width: 3 });
  connect(s, mcp, ml, { color: C.lavender, width: 3 });
  connect(s, mcp, report, { kind: "elbow", fromSide: "bottom", toSide: "top", color: C.lavender, width: 3 });
  text(s, "Пароль від бази зберігається на сервері, а не в чаті", 730, 535, 470, 50, { fontSize: 21, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 11:45–13:00\n\nПройдіть схему зліва направо. Claude бачить лише контракт інструментів. MCP-сервер тримає DATABASE_URL і сам підключається до PostgreSQL.\n\nML-модель — локальний файл, який сервер завантажує. save_report пише HTML у reports/.\n\nВажливо: у хмарі публічний MCP без автентифікації підходить лише для синтетичних даних.`);
}

// 13 — schema discovery
{
  const s = baseSlide(13);
  title(s, "Як агент дізнається, що є в базі");
  const steps = [
    ["1", "list_tables", "отримує назви й описи таблиць"],
    ["2", "describe_table", "читає колонки, типи, зв’язки й коментарі"],
    ["3", "Claude", "обирає потрібні таблиці та поля"],
    ["4", "run_sql", "складає і виконує SELECT"],
  ];
  const boxes = [];
  steps.forEach((r, i) => {
    const x = 55 + i * 300;
    const b = card(s, x, 200, 250, 270, { fill: i === 2 ? C.indigo : C.purple, lineFill: i === 2 ? C.indigo : C.line, radius: 18 });
    boxes.push(b);
    numberDot(s, r[0], x + 20, 222, { fill: i === 2 ? C.ink : C.indigo });
    text(s, r[1], x + 18, 290, 214, 44, { fontSize: 24, bold: true, color: i === 2 ? C.ink : C.white, align: "center" });
    text(s, r[2], x + 20, 360, 210, 78, { fontSize: 19, color: i === 2 ? C.ink : C.pale, align: "center", lineSpacing: 1.04 });
    if (i > 0) connect(s, boxes[i - 1], b, { color: C.lime, width: 2 });
  });
  text(s, "Спочатку агент читає схему, потім складає SQL", 230, 535, 820, 44, { fontSize: 27, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 13:00–14:15\n\nКоли користувач питає «Що є в цій базі?», агент викликає list_tables. Для конкретного питання він читає структуру потрібних таблиць через describe_table. Лише після цього складає SELECT.\n\nСаме описи таблиць, колонок і зв’язків дають моделі контекст про дані.`);
}

// 14 — request lifecycle
{
  const s = baseSlide(14);
  title(s, "Один запит проходить шість видимих кроків");
  const labels = ["Питання", "Список таблиць", "Опис схеми", "SELECT", "Результат", "Пояснення"];
  const boxes = [];
  labels.forEach((label, i) => {
    const x = 65 + i * 202;
    const b = card(s, x, 240, 170, 170, { fill: i === 5 ? C.indigo : C.purple, lineFill: i === 5 ? C.indigo : C.line, radius: 18 });
    boxes.push(b);
    numberDot(s, i + 1, x + 18, 258, { size: 28, fill: i === 5 ? C.ink : C.indigo, fontSize: 13 });
    text(s, label, x + 15, 315, 140, 58, { fontSize: 22, bold: true, color: i === 5 ? C.ink : C.white, align: "center", valign: "middle" });
    if (i > 0) connect(s, boxes[i - 1], b, { color: C.lime, width: 2 });
  });
  text(s, "Кожен виклик можна розгорнути й перевірити в інтерфейсі Claude", 200, 500, 880, 50, { fontSize: 26, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 14:15–15:30\n\nПоясніть спостережуваність: ми бачимо, який інструмент викликано, з якими аргументами та що він повернув.\n\nЦе не гарантує правильність відповіді, але робить помилку діагностованою.`);
}

// 15 — five tools
{
  const s = baseSlide(15);
  title(s, "П’ять інструментів: від схеми до прогнозу");
  const tools = [
    ["1", "list_tables", "що є"],
    ["2", "describe_table", "як влаштовано"],
    ["3", "run_sql", "прочитати дані"],
    ["4", "save_report", "зберегти HTML"],
    ["5", "predict_churn", "оцінити ризик"],
  ];
  tools.forEach((r, i) => {
    const x = 50 + i * 246;
    card(s, x, 200, 220, 270, { fill: C.purple, lineFill: C.line });
    numberDot(s, r[0], x + 20, 222, { fill: C.indigo });
    text(s, r[1], x + 18, 295, 184, 48, { fontSize: 22, bold: true, color: C.white, align: "center", valign: "middle" });
    text(s, r[2], x + 18, 375, 184, 48, { fontSize: 20, color: C.pale, align: "center", valign: "middle" });
  });
  text(s, "Окремого інструмента «побудувати графік» навмисно немає", 160, 535, 960, 44, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 15:30–17:00\n\nШвидко поясніть усі п’ять.\n\nsave_report не генерує звіт. Claude створює HTML, а інструмент лише безпечно зберігає файл. Це залишає моделі свободу оформлення, але обмежує файлову дію.`);
}

// 16 — docstrings
{
  const s = baseSlide(16);
  title(s, "Docstring у Python пояснює моделі, коли викликати інструмент");
  codeBlock(s, `def run_sql(query: str, limit: int = 200):\n    """Виконує лише SELECT-запит.\n\n    Спершу перевір схему таблиці.\n    Повертає колонки, рядки й ознаку truncation.\n    """`, 90, 170, 690, 380, { label: "PYTHON", labelWidth: 90, fontSize: 22 });
  cardText(s, "Опис = інтерфейс для AI", "Назва функції замала. Модель читає призначення, обмеження та формат результату.", 845, 205, 330, 280, { kicker: "КЛЮЧОВА ІДЕЯ", headingSize: 29, bodySize: 22, bodyTop: 122, fill: C.indigo, headingColor: C.ink, bodyColor: C.ink, kickerColor: C.ink });
  notes(s, `Таймінг: 17:00–18:00\n\nПокажіть docstring як частину продукту, а не коментар «для програміста». Якщо опис нечіткий, модель вибиратиме інструмент гірше.\n\nУ workshop-start ми дописуємо функції, але докстрінги вже задають очікувану поведінку.`);
}

// 17 — schema comments
{
  const s = baseSlide(17);
  title(s, "Знання про дані живуть поруч із даними");
  codeBlock(s, `COMMENT ON COLUMN lessons.status IS\n'completed — урок відбувся;\ncancelled_by_parent — не рахувати як проведений';`, 90, 190, 640, 250, { label: "POSTGRESQL", labelWidth: 130, fontSize: 23 });
  const box = card(s, 840, 190, 330, 250, { fill: C.offWhite, lineFill: C.pale });
  text(s, "describe_table", 875, 225, 260, 42, { fontSize: 29, bold: true, color: C.ink, align: "center" });
  text(s, "повертає коментар моделі разом із типами, зв’язками та прикладами", 875, 300, 260, 100, { fontSize: 23, color: C.ink, align: "center", lineSpacing: 1.05 });
  text(s, "Менше прихованих правил у промпті", 260, 515, 760, 45, { fontSize: 27, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 18:00–19:00\n\nПоясніть «пастку» status: без коментаря модель може порахувати всі заплановані уроки як проведені.\n\nПеревага: визначення знаходиться там, де його бачить і людина, і інструмент. Зміна схеми не вимагає переписувати великий системний промпт.`);
}

// 18 — safety
{
  const s = baseSlide(18);
  title(s, "Три шари не дають агенту зіпсувати базу");
  const specs = [
    ["1", "SQL guard", "пропускає SELECT і WITH"],
    ["2", "read-only роль", "PostgreSQL відхиляє запис"],
    ["3", "audit_log", "зберігає успіхи й помилки"],
  ];
  specs.forEach((r, i) => {
    const x = 90 + i * 395;
    cardText(s, r[1], r[2], x, 205, 330, 250, { kicker: "ШАР " + r[0], headingSize: 29, bodySize: 22, bodyTop: 135, fill: i === 1 ? C.indigo : C.purple, headingColor: i === 1 ? C.ink : C.white, bodyColor: i === 1 ? C.ink : C.pale, kickerColor: i === 1 ? C.ink : C.periwinkle });
  });
  text(s, "Справжній бар’єр — права бази, а guard дає зрозумілу помилку раніше", 140, 530, 1000, 56, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 19:00–20:30\n\nПідкресліть різницю між зручністю та безпекою. Guard ловить очевидний DELETE і пояснює моделі, що дозволено. Але остаточно захищає роль analyst_ro у PostgreSQL.\n\nКоманда для демонстрації: python scripts/prove_readonly.py. Вона обходить сервер і доводить, що сама база відмовляє у записі.`);
}

// 19 — repo map
{
  const s = baseSlide(19);
  title(s, "Карта репозиторію: де що лежить");
  codeBlock(s, `data-analyst-agent/\n├─ server/        MCP-сервер та інструменти\n├─ db/            схема, роль, демо-дані\n├─ ml/            навчання й model.pkl\n├─ tests/         перевірки поведінки\n├─ docs/          setup, deploy, next steps\n├─ deploy/        Dockerfile і старт у хмарі\n├─ docker-compose.yml\n└─ railway.toml`, 70, 150, 710, 465, { label: "ПАПКИ", labelWidth: 88, fontSize: 21 });
  const callouts = [
    ["server/main.py", "реєструє 5 tools, обирає transport"],
    ["server/db.py", "пул з’єднань, guard, помилки"],
    ["server/features.py", "єдине джерело ML-ознак"],
  ];
  callouts.forEach((r, i) => cardText(s, r[0], r[1], 840, 170 + i * 145, 350, 118, { headingSize: 23, headingHeight: 35, bodySize: 18, bodyTop: 68, fill: i === 0 ? C.indigo : C.purple, headingColor: i === 0 ? C.ink : C.white, bodyColor: i === 0 ? C.ink : C.pale }));
  notes(s, `Таймінг: 20:30–22:15\n\nПроведіть екскурсію, не відкриваючи кожен файл.\n\nМнемоніка: server виконує, db зберігає, ml прогнозує, tests перевіряє, docs пояснює, deploy пакує.\n\nПокажіть, що railway.toml лежить у корені, бо Railway шукає конфіг саме там.`);
}

// 20 — core tables
{
  const s = baseSlide(20);
  title(s, "Чотири таблиці описують навчальний процес");
  const students = card(s, 90, 250, 240, 120, { fill: C.indigo, lineFill: C.indigo });
  const subs = card(s, 390, 250, 240, 120, { fill: C.purple, lineFill: C.periwinkle });
  const lessons = card(s, 690, 180, 240, 120, { fill: C.purple, lineFill: C.periwinkle });
  const tutors = card(s, 990, 180, 200, 120, { fill: C.purple, lineFill: C.line });
  text(s, "students", 120, 278, 180, 34, { fontSize: 27, bold: true, color: C.ink, align: "center" });
  text(s, "учень", 120, 326, 180, 28, { fontSize: 19, color: C.ink, align: "center" });
  text(s, "subscriptions", 420, 278, 180, 34, { fontSize: 26, bold: true, align: "center" });
  text(s, "план занять", 420, 326, 180, 28, { fontSize: 19, color: C.pale, align: "center" });
  text(s, "lessons", 720, 208, 180, 34, { fontSize: 27, bold: true, align: "center" });
  text(s, "уроки й статуси", 720, 256, 180, 28, { fontSize: 19, color: C.pale, align: "center" });
  text(s, "tutors", 1010, 208, 160, 34, { fontSize: 27, bold: true, align: "center" });
  text(s, "викладачі", 1010, 256, 160, 28, { fontSize: 19, color: C.pale, align: "center" });
  connect(s, students, subs, { color: C.lime, width: 3 });
  connect(s, subs, lessons, { kind: "elbow", color: C.lavender, width: 3 });
  connect(s, tutors, lessons, { fromSide: "left", toSide: "right", color: C.lavender, width: 3 });
  text(s, "Один учень має підписку, підписка має уроки, урок проводить репетитор", 160, 470, 960, 70, { fontSize: 28, bold: true, align: "center", color: C.white });
  notes(s, `Таймінг: 22:15–23:30\n\nПоясніть зв’язки як речення. Це легше за терміни «foreign key» і «one-to-many».\n\nПісля речення додайте: foreign key — це колонка, яка посилається на ідентифікатор у іншій таблиці.`);
}

// 21 — support tables
{
  const s = baseSlide(21);
  title(s, "Платежі, підтримка й аудит доповнюють картину");
  const specs = [
    ["payments", "успішні й невдалі списання", "90 днів для churn"],
    ["support_tickets", "звернення учня", "сигнал незадоволення"],
    ["audit_log", "всі виклики MCP", "хто, що, коли, результат"],
  ];
  specs.forEach((r, i) => cardText(s, r[0], r[1] + "\n\n" + r[2], 90 + i * 395, 190, 330, 300, { kicker: "ТАБЛИЦЯ", headingSize: 28, bodySize: 21, bodyTop: 125, fill: i === 2 ? C.indigo : C.purple, headingColor: i === 2 ? C.ink : C.white, bodyColor: i === 2 ? C.ink : C.pale, kickerColor: i === 2 ? C.ink : C.periwinkle }));
  text(s, "Разом у демо 7 таблиць", 370, 550, 540, 44, { fontSize: 28, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 23:30–24:30\n\nПокажіть, що агент бачить не одну «таблицю уроків», а контекст клієнта. Платежі та тікети стають ознаками churn. audit_log не є бізнес-даними, це слід роботи системи.`);
}

// 22 — local options
{
  const s = baseSlide(22);
  title(s, "Локально є два способи отримати базу");
  cardText(s, "А. База від ведучої", "Вставити DATABASE_URL у .env\nDocker не потрібен", 95, 190, 500, 320, { kicker: "НАЙШВИДШЕ", headingSize: 31, bodySize: 24, bodyTop: 155 });
  cardText(s, "Б. Своя база", "Запустити Docker Desktop\nВиконати make setup", 685, 190, 500, 320, { kicker: "БІЛЬШЕ КОНТРОЛЮ", headingSize: 31, bodySize: 24, bodyTop: 155, fill: C.indigo, headingColor: C.ink, bodyColor: C.ink, kickerColor: C.ink });
  text(s, "Обидва варіанти дають серверу однаковий DATABASE_URL", 235, 560, 810, 42, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 24:30–25:30\n\nЯкщо аудиторія зовсім нова, рекомендуйте варіант А для воркшопу. Варіант Б показуйте тим, хто хоче забрати повну локальну копію.\n\n.env — локальний файл із налаштуваннями й секретами. Він не потрапляє в Git.`);
}

// 23 — setup commands
{
  const s = baseSlide(23);
  title(s, "Чотири етапи до першого локального запиту");
  const steps = [
    ["1", "Завантажити", "git clone …\ncd data-analyst-agent"],
    ["2", "Ізолювати Python", "python3 -m venv .venv\npip install -e \".[dev]\""],
    ["3", "Підготувати", "make setup\nmake doctor"],
    ["4", "Підключити", "make config\nперезапустити Claude"],
  ];
  steps.forEach((r, i) => {
    const x = 70 + i * 300;
    card(s, x, 180, 260, 330, { fill: i === 3 ? C.indigo : C.purple, lineFill: i === 3 ? C.indigo : C.line });
    numberDot(s, r[0], x + 22, 205, { fill: i === 3 ? C.ink : C.indigo });
    text(s, r[1], x + 22, 270, 216, 48, { fontSize: 27, bold: true, color: i === 3 ? C.ink : C.white, align: "center" });
    text(s, r[2], x + 22, 360, 216, 95, { fontSize: 19, color: i === 3 ? C.ink : C.pale, align: "center", lineSpacing: 1.1 });
  });
  text(s, "make — короткі назви для довгих команд", 325, 560, 630, 40, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 25:30–26:30\n\nНе читайте команди по символах. Поясніть їх призначення.\n\nvenv створює окреме Python-оточення. pip ставить залежності з pyproject.toml. make setup оркеструє Docker, seed і train. make config друкує конфіг із абсолютними шляхами.`);
}

// 24 — live demo local
{
  const s = baseSlide(24);
  tag(s, "LIVE DEMO · 7 ХВ", 72, 52, 190, { height: 34 });
  text(s, "Локальний MCP через stdio", 72, 112, 850, 62, { fontSize: 50, bold: true });
  codeBlock(s, `make doctor\nmake config\n\n# після перезапуску Claude\nЩо є в цій базі?\nПобудуй графік уроків по місяцях\nЗбережи цей звіт файлом`, 80, 215, 700, 350, { label: "ПОКАЗАТИ НАЖИВО", labelWidth: 180, fontSize: 22 });
  cardText(s, "Ознаки успіху", "✓ 7 таблиць\n✓ видно tool calls\n✓ SQL лише SELECT\n✓ звіт у reports/", 850, 215, 340, 350, { kicker: "CHECKLIST", headingSize: 30, bodySize: 23, bodyTop: 122, fill: C.indigo, headingColor: C.ink, bodyColor: C.ink, kickerColor: C.ink });
  notes(s, `Таймінг: 26:30–33:30\n\nLIVE DEMO 1\n\n1. У терміналі покажіть make doctor. Якщо все green, не затримуйтесь.\n2. Запустіть make config і коротко покажіть, що шляхи абсолютні. Не копіюйте секрети на великий екран.\n3. У Claude Desktop відкрийте новий чат. Поставте «Що є в цій базі?».\n4. Розгорніть виклики інструментів. Назвіть list_tables і describe_table.\n5. Поставте запит про уроки по місяцях. Покажіть SQL.\n6. Попросіть зберегти звіт і відкрийте HTML.\n\nПлан Б: якщо Claude не підключився, запустіть make run і покажіть помилку дослівно; далі перейдіть до заздалегідь підготовленого чату.`);
}

// 25 — tool chain
{
  const s = baseSlide(25);
  title(s, "Claude сам складає ланцюжок інструментів");
  const prompt = card(s, 80, 175, 290, 170, { fill: C.offWhite, lineFill: C.pale });
  text(s, "«Хто з учнів у зоні ризику і що в них спільного?»", 105, 205, 240, 110, { fontSize: 24, bold: true, color: C.ink, align: "center", valign: "middle" });
  const tools = ["list_tables", "describe_table", "predict_churn", "run_sql"];
  const boxes = [];
  tools.forEach((name, i) => {
    const y = 145 + i * 105;
    const b = card(s, 520, y, 260, 74, { fill: i === 2 ? C.indigo : C.purple, lineFill: i === 2 ? C.indigo : C.line, radius: 16 });
    boxes.push(b);
    text(s, name, 545, y + 18, 210, 34, { fontSize: 22, bold: true, color: i === 2 ? C.ink : C.white, align: "center" });
    if (i > 0) connect(s, boxes[i - 1], b, { kind: "elbow", fromSide: "bottom", toSide: "top", color: C.lavender, width: 2 });
  });
  const answer = card(s, 900, 230, 300, 180, { fill: C.indigo, lineFill: C.indigo });
  text(s, "Список учнів", 935, 260, 230, 42, { fontSize: 29, bold: true, color: C.ink, align: "center" });
  text(s, "ймовірність\nтоп-фактори\nзастереження", 935, 325, 230, 68, { fontSize: 21, color: C.ink, align: "center", lineSpacing: 1.05 });
  connect(s, prompt, boxes[0], { color: C.lime, width: 3 });
  connect(s, boxes[3], answer, { color: C.lime, width: 3 });
  text(s, "Послідовність зміниться, якщо зміниться питання", 285, 595, 710, 38, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 33:30–35:00\n\nПісля демо закріпіть: код не містить цього workflow. Модель може пропустити run_sql, якщо predict_churn уже повернув достатньо пояснень. Це нормально, якщо відповідь обґрунтована.`);
}

// 26 — workshop branch
{
  const s = baseSlide(26);
  title(s, "workshop-start залишає місця для спільного коду");
  cardText(s, "main", "повне рішення\nусі тести мають проходити", 110, 190, 440, 300, { kicker: "РОБОЧИЙ СТАН", headingSize: 37, bodySize: 24, bodyTop: 145, fill: C.indigo, headingColor: C.ink, bodyColor: C.ink, kickerColor: C.ink });
  cardText(s, "workshop-start", "каркас із TODO\nпишемо db.py, schema.py, sql.py, report.py", 730, 190, 440, 300, { kicker: "НАВЧАЛЬНИЙ СТАН", headingSize: 32, bodySize: 22, bodyTop: 145 });
  shape(s, "rect", 570, 325, 140, 3, C.lime);
  text(s, "git checkout", 570, 280, 140, 35, { fontSize: 19, bold: true, color: C.lime, align: "center" });
  text(s, "База й model.pkl не зникають під час перемикання гілки", 220, 550, 840, 40, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 35:00–36:00\n\nПоясніть гілку як паралельну версію папки, але без дублювання файлів вручну.\n\nРятувальний шлях учасника: якщо відстав, git checkout main повертає повне рішення. Повернутися до каркаса можна пізніше.`);
}

// 27 — tests
{
  const s = baseSlide(27);
  title(s, "Тести — автоматичний чеклист очікувань");
  await image(s, "pytest.png", 95, 190, 180, 180, { alt: "pytest" });
  const checks = [
    ["test_sql_guard.py", "не пропускає DELETE, але дозволяє чесний SELECT"],
    ["test_tools_smoke.py", "перевіряє форму відповіді кожного інструмента"],
    ["prove_readonly.py", "доводить обмеження прямо на рівні бази"],
  ];
  checks.forEach((r, i) => {
    numberDot(s, i + 1, 350, 180 + i * 120, { size: 32 });
    text(s, r[0], 405, 174 + i * 120, 340, 36, { fontSize: 24, bold: true });
    text(s, r[1], 760, 170 + i * 120, 410, 66, { fontSize: 21, color: C.pale, lineSpacing: 1.05 });
  });
  codeBlock(s, "make test", 420, 550, 440, 64, { fontSize: 25, fill: C.indigo, color: C.ink });
  notes(s, `Таймінг: 36:00–37:00\n\npytest — інструмент, який запускає короткі сценарії перевірки. На workshop-start червоні тести — це карта того, що ще треба реалізувати. На main вони мають бути зеленими.`);
}

// 28 — ML
{
  const s = baseSlide(28);
  title(s, "ML дає сигнал ризику, рішення лишається за людиною");
  await image(s, "scikitlearn.png", 80, 180, 180, 180, { alt: "scikit-learn" });
  const feats = card(s, 320, 180, 240, 180, { fill: C.purple, lineFill: C.line });
  const model = card(s, 650, 180, 240, 180, { fill: C.indigo, lineFill: C.indigo });
  const human = card(s, 980, 180, 220, 180, { fill: C.purple, lineFill: C.line });
  text(s, "14 ознак", 345, 215, 190, 40, { fontSize: 30, bold: true, align: "center" });
  text(s, "уроки, оцінки, платежі, тікети", 345, 278, 190, 64, { fontSize: 20, color: C.pale, align: "center" });
  text(s, "Gradient Boosting", 675, 215, 190, 56, { fontSize: 26, bold: true, color: C.ink, align: "center" });
  text(s, "ROC AUC 0.776", 675, 300, 190, 32, { fontSize: 21, bold: true, color: C.ink, align: "center" });
  text(s, "Людина", 1005, 215, 170, 40, { fontSize: 30, bold: true, align: "center" });
  text(s, "вирішує, кому і як допомогти", 1005, 278, 170, 64, { fontSize: 20, color: C.pale, align: "center" });
  connect(s, feats, model, { color: C.lime, width: 3 });
  connect(s, model, human, { color: C.lime, width: 3 });
  text(s, "Прогноз: відтік у наступні 30 днів + три фактори для пояснення", 175, 465, 930, 70, { fontSize: 27, bold: true, color: C.white, align: "center" });
  tag(s, "ЦЕ ПІДКАЗКА, НЕ ВИРОК", 440, 565, 400, { height: 36 });
  notes(s, `Таймінг: 37:00–38:30\n\nПоясніть, що модель навчається окремою командою make train і зберігається в ml/model.pkl. Сервер лише завантажує готовий файл.\n\n14 ознак дивляться тільки в минуле. Ціль — відтік у наступні 30 днів. У поточному файлі моделі ROC AUC = 0.776, дата навчання 2026-09-16.\n\nscikit-learn 1.7.2 та numpy 2.2.6 закріплено точними версіями, бо pickle залежить від оточення.`);
}

// 29 — report
{
  const s = baseSlide(29);
  title(s, "HTML-звіт легко відкрити й надіслати");
  const html = card(s, 120, 200, 330, 260, { fill: C.offWhite, lineFill: C.pale });
  text(s, "<html>", 155, 235, 260, 45, { fontSize: 31, bold: true, color: C.violet, align: "center" });
  text(s, "текст\nтаблиці\nграфіки", 155, 305, 260, 110, { fontSize: 25, color: C.ink, align: "center", lineSpacing: 1.08 });
  const save = card(s, 520, 240, 260, 180, { fill: C.purple, lineFill: C.periwinkle });
  text(s, "save_report", 550, 275, 200, 42, { fontSize: 28, bold: true, align: "center" });
  text(s, "перевіряє HTML\nі безпечну назву", 550, 340, 200, 58, { fontSize: 20, color: C.pale, align: "center" });
  const file = card(s, 860, 200, 300, 260, { fill: C.indigo, lineFill: C.indigo });
  text(s, "reports/", 895, 235, 230, 42, { fontSize: 31, bold: true, color: C.ink, align: "center" });
  text(s, "уроки-по-місяцях.html", 885, 325, 250, 64, { fontSize: 18, bold: true, color: C.ink, align: "center" });
  connect(s, html, save, { color: C.lime, width: 3 });
  connect(s, save, file, { color: C.lime, width: 3 });
  text(s, "Інструмент зберігає результат, але не вирішує, що малювати", 210, 545, 860, 45, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 38:30–39:15\n\nHTML — звичайна веб-сторінка в одному файлі. Claude генерує вміст, save_report перевіряє, що це справді HTML, і створює безпечне ім’я в reports/.`);
}

// 30 — local vs cloud
{
  const s = baseSlide(30);
  title(s, "Локально Claude запускає сервер, у хмарі приходить за URL");
  cardText(s, "stdio", "стандартний вхід і вихід програми\n\nClaude запускає Python-сервер на цьому ж комп’ютері", 100, 175, 470, 350, { kicker: "ЛОКАЛЬНО", headingSize: 38, bodySize: 22, bodyTop: 135 });
  cardText(s, "HTTP", "сервер уже працює в Railway\n\nClaude підключається за адресою https://…/mcp", 710, 175, 470, 350, { kicker: "У ХМАРІ", headingSize: 38, bodySize: 22, bodyTop: 135, fill: C.indigo, headingColor: C.ink, bodyColor: C.ink, kickerColor: C.ink });
  text(s, "Код інструментів той самий. Змінюється спосіб підключення", 195, 560, 890, 42, { fontSize: 25, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 39:15–40:45\n\nstdio означає standard input / standard output, тобто стандартний вхід і вихід програми. Claude Desktop запускає Python-процес на цьому ж комп’ютері та обмінюється з ним повідомленнями напряму. Вебадреса й відкритий порт не потрібні.\n\nУ хмарі сервер працює постійно. Клієнт звертається до нього через HTTP за адресою /mcp. MCP_TRANSPORT перемикає лише спосіб підключення.`);
}

// 31 — Railway flow
{
  const s = baseSlide(31);
  title(s, "Railway збирає контейнер і дає MCP-адресу");
  const specs = [
    ["github.png", "GitHub", "код"],
    ["railway.png", "Railway", "build + run"],
    ["docker.png", "Контейнер", "Python MCP"],
    ["mcp.png", "/mcp", "публічний URL"],
  ];
  const boxes = [];
  for (let i = 0; i < specs.length; i++) {
    const x = 65 + i * 300;
    const b = card(s, x, 190, 250, 250, { fill: i === 3 ? C.indigo : C.purple, lineFill: i === 3 ? C.indigo : C.line });
    boxes.push(b);
    await image(s, specs[i][0], x + 78, 218, 94, 94, { alt: specs[i][1] });
    text(s, specs[i][1], x + 25, 330, 200, 40, { fontSize: 27, bold: true, color: i === 3 ? C.ink : C.white, align: "center" });
    text(s, specs[i][2], x + 25, 382, 200, 30, { fontSize: 20, color: i === 3 ? C.ink : C.pale, align: "center" });
    if (i > 0) connect(s, boxes[i - 1], b, { color: C.lime, width: 3 });
  }
  const db = card(s, 470, 505, 340, 90, { fill: C.deep, lineFill: C.periwinkle, radius: 18 });
  await image(s, "postgresql.png", 495, 520, 60, 60, { alt: "PostgreSQL" });
  text(s, "База живе окремо в мережі", 575, 530, 210, 34, { fontSize: 22, bold: true, align: "center" });
  connect(s, boxes[2], db, { kind: "elbow", fromSide: "bottom", toSide: "top", color: C.lavender, width: 2 });
  notes(s, `Таймінг: 40:45–42:30\n\nRailway стежить за GitHub, читає railway.toml, будує образ через deploy/Dockerfile і запускає контейнер.\n\nБаза мусить бути доступна з інтернету, наприклад Neon або PostgreSQL у Railway. Локальний Docker на ноутбуці з хмари недосяжний.\n\nДжерело: https://docs.railway.com/deployments/reference`);
}

// 32 — live demo cloud
{
  const s = baseSlide(32);
  tag(s, "LIVE DEMO · 6 ХВ", 72, 52, 190, { height: 34 });
  text(s, "Деплой на Railway", 72, 112, 850, 62, { fontSize: 50, bold: true });
  const steps = [
    ["1", "Deploy from GitHub", "repo + main"],
    ["2", "Variables", "DATABASE_URL\nTRANSPORT=http"],
    ["3", "Generate Domain", "додати /mcp"],
    ["4", "Logs", "база відповідає\nсервер стартував"],
    ["5", "Claude Connector", "назва + URL"],
  ];
  steps.forEach((r, i) => {
    const x = 55 + i * 245;
    card(s, x, 220, 215, 300, { fill: i === 4 ? C.indigo : C.purple, lineFill: i === 4 ? C.indigo : C.line, radius: 18 });
    numberDot(s, r[0], x + 18, 240, { size: 30, fill: i === 4 ? C.ink : C.indigo });
    text(s, r[1], x + 15, 300, 185, 58, { fontSize: 22, bold: true, color: i === 4 ? C.ink : C.white, align: "center", valign: "middle" });
    text(s, r[2], x + 15, 390, 185, 72, { fontSize: 18, color: i === 4 ? C.ink : C.pale, align: "center", lineSpacing: 1.05 });
  });
  text(s, "Не показуйте ADMIN_DATABASE_URL і не вмикайте SEED_ON_START без потреби", 135, 575, 1010, 42, { fontSize: 23, bold: true, color: C.lime, align: "center" });
  notes(s, `Таймінг: 42:30–48:30\n\nLIVE DEMO 2\n\n1. Відкрийте готовий проєкт Railway або створіть New Project → Deploy from GitHub repo.\n2. Покажіть, що railway.toml вказує deploy/Dockerfile.\n3. У Variables додайте рівно DATABASE_URL і MCP_TRANSPORT=http. Закрийте значення пароля від аудиторії.\n4. Settings → Networking → Generate Domain. До адреси додайте /mcp.\n5. У Logs знайдіть «База відповідає» і «Стартую MCP-сервер».\n6. Claude → Connectors → Add custom connector. Додайте URL і повторіть «Що є в цій базі?».\n\nВажливе попередження: адреса без auth публічна. Для реальних даних спершу виконайте deploy/AUTH.md.\n\nЯкщо відкриття /mcp у браузері дає Missing session ID, це очікувано: браузер не виконав MCP initialize.`);
}

// 33 — next steps
{
  const s = baseSlide(33);
  await image(s, "data-loves-logo.png", 970, 30, 220, 54, { alt: "Data Loves Academy" });
  title(s, "Перед роботою з реальними даними");
  const next = [
    ["1", "Права ролей", "окрема read-only роль і мінімально потрібний доступ"],
    ["2", "Автентифікація", "сервер перевіряє, хто може викликати інструменти"],
    ["3", "Документація метрик", "визначення, формула, фільтри, джерело та відповідальний"],
  ];
  next.forEach((r, i) => cardText(s, r[1], r[2], 85 + i * 400, 205, 350, 260, { kicker: "КРОК " + r[0], headingSize: 30, bodySize: 22, bodyTop: 128, fill: i === 2 ? C.indigo : C.purple, headingColor: i === 2 ? C.ink : C.white, bodyColor: i === 2 ? C.ink : C.pale, kickerColor: i === 2 ? C.ink : C.periwinkle }));
  text(s, "Без опису метрик агент може правильно порахувати не ту цифру", 165, 525, 950, 48, { fontSize: 27, bold: true, color: C.lime, align: "center" });
  text(s, "Питання?", 430, 598, 420, 48, { fontSize: 34, bold: true, color: C.white, align: "center" });
  notes(s, `Таймінг: 48:30–50:00\n\nДля реальних даних почніть із трьох речей.\n\nПерша: окрема роль бази з мінімальними правами. Друга: автентифікація на публічному MCP, щоб сервер розумів, хто підключився. Третя: словник метрик із визначенням, формулою, фільтрами, джерелом даних і відповідальним.\n\nДокументація метрик потрібна і людям, і агенту. Без неї технічно правильний SQL може відповідати на інше бізнес-питання.\n\nДеталі: docs/NEXT-STEPS.md, docs/DEPLOY.md, deploy/AUTH.md.`);
}

// 34 — participant materials
{
  const s = baseSlide(34);
  await image(s, "data-loves-logo.png", 72, 42, 270, 65, { alt: "Data Loves Academy" });
  text(s, "Матеріали\nворкшопу", 72, 165, 590, 135, { fontSize: 58, bold: true, lineSpacing: 0.95 });
  text(s, "Репозиторій, доступ до навчальної бази та інструкції для Windows і macOS", 76, 330, 560, 105, { fontSize: 28, color: C.pale, lineSpacing: 1.08 });
  card(s, 72, 480, 565, 96, { fill: C.lime, lineFill: C.lime, radius: 18 });
  text(s, "База доступна до 24 вересня 2026 включно", 96, 500, 517, 56, { fontSize: 25, bold: true, color: C.ink, align: "center", valign: "middle" });
  card(s, 760, 90, 450, 450, { fill: C.white, lineFill: C.white, radius: 18 });
  await image(s, "notion-workshop-qr.png", 780, 110, 410, 410, { alt: "QR-код на сторінку матеріалів воркшопу" });
  text(s, "Відскануйте камерою телефона", 760, 580, 450, 38, { fontSize: 24, bold: true, color: C.white, align: "center" });
  notes(s, `Сторінка матеріалів для учасників:\nhttps://hannapylieva.notion.site/3de94835849480c58b37c95fd65fa978?source=copy_link\n\nНа сторінці є репозиторій, місце для DATABASE_URL та інструкції встановлення Git, Python і Claude Desktop для Windows та macOS.`);
}

await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(path.dirname(finalPath), { recursive: true });
const stagingDir = path.join(workspaceDir, ".codex-finalizer");
await fs.mkdir(stagingDir, { recursive: true });
const candidatePath = path.join(stagingDir, "ai-analyst-mcp-workshop-participant-v2-candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const { finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);
const result = await finalizePresentation({
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-heading-fit",
  ],
  explicitTotalSlideCount: TOTAL,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  fontPolicy: {
    basis: "reference",
    families: [FONT],
    referencePath: "/Users/hannapylieva/Downloads/data-specialist-2026-brand-v3.pptx",
    referenceSha256: "b0abaf01d357f33baeaf22ae8b338acf8cceb058c669af75349bbfc0f27bd63b",
  },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "ai-analyst-mcp-workshop-participant-final-v2.validation.json"),
});

console.log(JSON.stringify({ finalPath, slideCount: TOTAL, result }, null, 2));
