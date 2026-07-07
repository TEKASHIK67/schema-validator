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

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

### Обход списка реальных URL
```bash
python3 cli.py --input samples/urls.txt --output-dir ./report --workers 10
```

### Проверка локальных HTML-файлов (без сети, для теста)
```bash
python3 cli.py --input samples/page_valid.html samples/page_invalid.html --local --output-dir ./report
```

### JSON в stdout (для интеграции / REST-обвязки)
```bash
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

## Поддерживаемые типы schema.org

- `Hotel` / `LodgingBusiness`
- `Product`
- `BreadcrumbList`

Правила лежат в `validator.py`, в функциях `validate_hotel`, `validate_product`,
`validate_breadcrumb`. Новый тип добавляется одной функцией и записью в
словарь `TYPE_VALIDATORS`.
