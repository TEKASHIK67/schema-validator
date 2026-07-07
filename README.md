# Валидатор структурированной разметки schema.org

CLI-утилита для аудита JSON-LD микроразметки (Hotel, Product, BreadcrumbList)
на страницах сайта. Проверяет синтаксис JSON и соответствие требованиям
schema.org / рекомендациям Google, формирует отчёт в CSV и HTML.

## Структура репозитория

```
├── extractor.py         — извлечение JSON-LD блоков из HTML
├── validator.py          — правила валидации (синтаксис + Hotel/Product/BreadcrumbList)
├── report.py             — генерация CSV/HTML отчётов
├── cli.py                — точка входа (CLI)
├── requirements.txt
├── samples/               — тестовые страницы для проверки работы валидатора
│   ├── page_valid.html
│   ├── page_invalid.html
│   └── urls.txt
├── reports/               — пример готового отчёта
│   ├── example_report.csv
│   └── example_report.html
└── docs/
    └── accuracy_report.md — отчёт о точности на контрольной выборке
```

## Как запустить

Есть два независимых способа — выбери один, оба делают одно и то же.

### Способ 1 (рекомендуется): через Docker — ничего ставить не нужно

Подробности и все команды — в разделе [Запуск через Docker](#запуск-через-docker) ниже.
Docker сам разворачивает Python и все зависимости внутри контейнера, ничего
устанавливать на компьютер не требуется, кроме самого Docker Desktop.

### Способ 2: напрямую через Python (без Docker)

Если Docker не установлен/не нужен — можно запускать скрипт как обычную
Python-программу. Понадобится Python 3.10+ и установка одной зависимости:

```bash
pip install -r requirements.txt
```

Дальше запуск:

```bash
# Обход списка реальных URL
python3 cli.py --input samples/urls.txt --output-dir ./report --workers 10

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
| `--output-dir` | папка для report.csv / report.html | `./report_output` |
| `--workers` | число потоков параллельного обхода | 8 |
| `--timeout` | таймаут запроса, сек | 10 |
| `--retries` | число повторных попыток при сетевой ошибке | 2 |
| `--json-stdout` | вывод в JSON вместо файлов | выкл |

## Проверка на тестовых данных

| Файл | Ожидаемо | Получено |
|---|---|---|
| `samples/page_valid.html` | 0 ошибок | 0 ошибок ✅ |
| `samples/page_invalid.html` | 4 ошибки | 4 ошибки ✅ |

Подробности — в `reports/example_report.html`.

## Точность на реальной выборке

См. [docs/accuracy_report.md](docs/accuracy_report.md).

## Запуск через Docker

Проект контейнеризирован — не нужно ставить Python и зависимости вручную.

### Собрать образ
```bash
docker build -t schema-validator .
```

### Проверка тестовых файлов (уже лежат внутри образа в samples/)
```bash
docker run --rm schema-validator --input samples/page_valid.html samples/page_invalid.html --local --json-stdout
```

### Обход реального списка URL с сохранением отчёта на диск
Нужно "пробросить" папку с выходными отчётами наружу, иначе отчёт останется
только внутри контейнера и исчезнет после его завершения. Синтаксис пути
монтирования отличается **в зависимости от того, в каком терминале ты
работаешь** — это частый источник ошибок, поэтому ниже три варианта:

**cmd.exe (обычная командная строка Windows):**
```cmd
docker run --rm -v "%cd%\report_output:/app/report_output" schema-validator --input samples/urls.txt --output-dir /app/report_output --workers 10
```

**PowerShell:**
```powershell
docker run --rm -v "${PWD}\report_output:/app/report_output" schema-validator `
  --input samples/urls.txt --output-dir /app/report_output --workers 10
```

**WSL2 / Git Bash / Linux / macOS:**
```bash
docker run --rm -v "$(pwd)/report_output:/app/report_output" schema-validator \
  --input samples/urls.txt --output-dir /app/report_output --workers 10
```

После выполнения отчёт `report.csv` и `report.html` появятся в локальной папке
`report_output/` рядом с проектом.

> Примечание: если запускаешь Docker Desktop на Windows, сам движок в любом
> случае работает через WSL2-бэкенд — это не влияет на то, из какого терминала
> ты вводишь команды (cmd.exe/PowerShell/WSL2), просто синтаксис пути к текущей
> папке у них разный.

### Проверка своих HTML-файлов, не встроенных в образ
Если нужно проверить файлы, которых нет внутри образа — смонтируй их папку
(команда для cmd.exe, для PowerShell/WSL2 — по аналогии с примером выше):
```cmd
docker run --rm -v "%cd%\my_pages:/app/my_pages" schema-validator --input my_pages/page1.html my_pages/page2.html --local
```

## Поддерживаемые типы schema.org

- `Hotel` / `LodgingBusiness`
- `Product`
- `BreadcrumbList`

Правила лежат в `validator.py`, в функциях `validate_hotel`, `validate_product`,
`validate_breadcrumb`. Новый тип добавляется одной функцией и записью в
словарь `TYPE_VALIDATORS`.
