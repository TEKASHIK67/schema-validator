# Валидатор структурированной разметки schema.org

CLI-утилита для аудита структурированной разметки (Hotel, Product,
BreadcrumbList) на страницах сайта. Поддерживает оба формата разметки —
**JSON-LD** и **Microdata**. Проверяет синтаксис и соответствие требованиям
schema.org / рекомендациям Google, формирует отчёт в CSV и HTML.

Страницы загружаются через настоящий headless-браузер (Playwright + Chromium
в stealth-режиме), что позволяет проходить антибот-защиту сайта (Qrator),
которая блокирует обычные HTTP-запросы кодом 401.

## Структура репозитория

```
├── extractor.py          — извлечение JSON-LD и Microdata блоков из HTML
├── validator.py           — правила валидации (синтаксис + Hotel/Product/BreadcrumbList)
├── report.py              — генерация CSV/HTML отчётов
├── cli.py                 — точка входа (CLI), загрузка страниц через Playwright
├── requirements.txt
├── Dockerfile
├── samples/                — тестовые страницы для проверки работы валидатора
│   ├── page_valid.html
│   ├── page_invalid.html
│   └── urls.txt
├── reports/                — пример готового отчёта
│   ├── example_report.csv
│   └── example_report.html
└── docs/
    └── accuracy_report.md  — отчёт о точности на контрольной выборке
```

## Как запустить

Есть два независимых способа — выбери один, оба делают одно и то же.

### Способ 1 (рекомендуется): через Docker

```bash
docker build -t schema-validator .
```

> Сборка образа в этот раз займёт заметно дольше и будет тяжелее по весу,
> чем раньше — на этапе `playwright install --with-deps chromium` скачивается
> и устанавливается сам браузер Chromium со всеми системными библиотеками.
> Это нормально, разовая плата за то, что дальше ничего доустанавливать не
> придётся.

Дальше запуск — см. раздел [Запуск через Docker](#запуск-через-docker) ниже.

### Способ 2: напрямую через Python (без Docker)

Потребуется Python 3.10+, а также сам браузер для Playwright (одноразовая
установка):

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
```

Дальше запуск:

```bash
# Обход списка реальных URL (порционно, по 100 ссылок за раз — см. ниже)
python3 cli.py --input samples/urls.txt --output-dir ./report --workers 4

# Проверка локальных HTML-файлов (без сети, для теста)
python3 cli.py --input samples/page_valid.html samples/page_invalid.html --local --output-dir ./report

# JSON в stdout (для интеграции / REST-обвязки)
python3 cli.py --input samples/page_valid.html --local --json-stdout
```

## Параметры

| Параметр | Описание | По умолчанию |
|---|---|---|
| `--input` | файл со списком URL, либо (с `--local`) пути к HTML-файлам | обязателен |
| `--local` | трактовать `--input` как локальные HTML-файлы | выкл |
| `--output-dir` | папка для report.csv / report.html / result/ | `./report_output` |
| `--workers` | число параллельных потоков обхода | 4 |
| `--timeout` | таймаут запроса на страницу, сек | 15 |
| `--retries` | число повторных попыток при сетевой ошибке | 1 |
| `--batch-size` | размер порции для промежуточной записи (см. ниже) | 100 |
| `--json-stdout` | вывод в JSON вместо файлов | выкл |

> Совет по `--workers`: в отличие от обычных HTTP-запросов, здесь каждый
> "воркер" запускает отдельный процесс браузера Chromium — это ощутимо тяжелее
> по памяти и CPU, чем обычный `requests.get()`. Не стоит бездумно повышать
> `--workers` до десятков — 4-8 обычно оптимальный диапазон для одной машины.

## Порционная запись результатов (батчинг)

При обходе большого списка (например, 1000+ ссылок) скрипт делит его на
порции по `--batch-size` штук (по умолчанию 100). После завершения **каждой**
порции результат сразу сохраняется на диск, в папку `result/` внутри
`--output-dir`:

```
report_output/
├── report.csv              — итоговый сводный отчёт по ВСЕМ ссылкам
├── report.html
└── result/
    ├── batch_001_1-100.csv
    ├── batch_001_1-100.html
    ├── batch_002_101-200.csv
    ├── batch_002_101-200.html
    └── ...
```

Смысл — если скрипт упадёт или его придётся остановить на середине большого
прогона (это реально возможно, учитывая, что каждая страница грузится через
полноценный браузер с прохождением антибот-защиты — процесс не самый быстрый
и не всегда стабильный), уже обработанные порции не теряются: их можно открыть
и посмотреть, даже если весь прогон не успел завершиться.

## Обход антибот-защиты сайта (Qrator)

Прямые HTTP-запросы (`requests`) к страницам отелей возвращают `401
Unauthorized` — сайт защищён антибот-сервисом Qrator, который требует
исполнения JavaScript в браузере для прохождения проверки. Обычная библиотека
`requests` этого сделать не может в принципе.

Поэтому `cli.py` загружает страницы через **headless Chromium** (Playwright)
в связке с `playwright-stealth` (маскирует типичные признаки автоматизации,
по которым антибот-системы отличают браузер под управлением скрипта от
настоящего пользователя). После перехода на страницу скрипt ждёт появления
тега `<h1>` — это служит сигналом, что Qrator-проверка пройдена и Chromium
перезагрузил страницу с реальным контентом.

## Проверка на тестовых данных

| Файл | Ожидаемо | Получено |
|---|---|---|
| `samples/page_valid.html` | 0 ошибок | 0 ошибок ✅ |
| `samples/page_invalid.html` | 4 ошибки | 4 ошибки ✅ |

Подробности — в `reports/example_report.html`.

## Точность на реальной выборке

См. [docs/accuracy_report.md](docs/accuracy_report.md).

## Запуск через Docker

### Собрать образ
```bash
docker build -t schema-validator .
```

### Проверка тестовых файлов (уже лежат внутри образа в samples/)
```bash
docker run --rm schema-validator --input samples/page_valid.html samples/page_invalid.html --local --json-stdout
```

### Обход реального списка URL с сохранением отчёта на диск
Нужно "пробросить" папку с отчётами наружу, иначе всё останется только внутри
контейнера. Синтаксис пути монтирования отличается **в зависимости от
терминала**:

**cmd.exe:**
```cmd
docker run --rm -v "%cd%\report_output:/app/report_output" schema-validator --input samples/urls.txt --output-dir /app/report_output --workers 4
```

**PowerShell:**
```powershell
docker run --rm -v "${PWD}\report_output:/app/report_output" schema-validator `
  --input samples/urls.txt --output-dir /app/report_output --workers 4
```

**WSL2 / Git Bash / Linux / macOS:**
```bash
docker run --rm -v "$(pwd)/report_output:/app/report_output" schema-validator \
  --input samples/urls.txt --output-dir /app/report_output --workers 4
```

> Примечание: Docker Desktop на Windows в любом случае работает через
> WSL2-бэкенд — это не влияет на то, из какого терминала вводятся команды,
> просто синтаксис пути к текущей папке у них разный.

### Проверка своих HTML-файлов, не встроенных в образ
```cmd
docker run --rm -v "%cd%\my_pages:/app/my_pages" schema-validator --input my_pages/page1.html my_pages/page2.html --local
```

## Поддерживаемые форматы и типы schema.org

**Форматы разметки:** JSON-LD, Microdata.

**Типы schema.org:**
- `Hotel` / `LodgingBusiness`
- `Product`
- `BreadcrumbList`

Правила лежат в `validator.py`, в функциях `validate_hotel`, `validate_product`,
`validate_breadcrumb`. Новый тип добавляется одной функцией и записью в
словарь `TYPE_VALIDATORS`. Извлечение разметки из HTML (оба формата) —
в `extractor.py`, функция `extract_structured_data`.
