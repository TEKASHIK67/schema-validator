#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py — CLI-утилита валидации структурированной разметки schema.org.
"""

import argparse
import json
import os
import sys
import time
import concurrent.futures as cf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor import extract_structured_data
from validator import validate_block
from report import write_csv_report, write_html_report

DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 1
DEFAULT_WORKERS = 4  # Оптимально для стабильной параллельной работы в Docker
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def read_url_list(path: str) -> list[str]:
    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls


def fetch_html(url: str, timeout: int, retries: int, proxy: str = None):
    """
    Загружает HTML с помощью безголового браузера Playwright.
    Использует динамическое ожидание прохождения проверки Qrator.
    """
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth
    import time

    last_err = None
    timeout_ms = timeout * 1000

    for attempt in range(retries + 1):
        try:
            with Stealth().use_sync(sync_playwright()) as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled"
                    ]
                )

                context = browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()

                # Устанавливаем жесткий лимит времени на уровне страницы
                page.set_default_timeout(timeout_ms)

                # Быстрый переход: не ждем загрузки тяжелых картинок и шрифтов
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                # Ждем прохождения Qrator: на реальной странице отеля появится тег <h1>.
                # Скрипт Qrator отработает, поставит куки и перезагрузит страницу —
                # Playwright корректно переждет этот переход.
                try:
                    page.wait_for_selector("h1", timeout=12000)
                except Exception:
                    # Если h1 не появился (например, страница не отеля), продолжаем парсинг того, что есть
                    pass

                # Небольшая пауза для завершения рендеринга скриптов разметки
                page.wait_for_timeout(1500)

                html_content = page.content()
                browser.close()
                return html_content, None
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(2 * (attempt + 1))

    return None, last_err


def process_source(source: str, is_local: bool, timeout: int, retries: int, proxy: str = None) -> dict:
    """Полный цикл обработки одной страницы: загрузка -> извлечение -> валидация."""
    if is_local:
        try:
            with open(source, "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception as e:
            return {"url": source, "status": "fetch_failed", "message": str(e), "errors": []}
    else:
        html_content, err = fetch_html(source, timeout, retries, proxy)
        if html_content is None:
            return {"url": source, "status": "fetch_failed", "message": err, "errors": []}

    # Используем новый экстрактор, поддерживающий JSON-LD и Microdata
    blocks = extract_structured_data(html_content)

    if not blocks:
        from validator import ValidationError
        no_markup_error = ValidationError(
            code="NO_MARKUP_FOUND",
            severity="warning",
            message="На странице не найдено структурированной разметки schema.org (ни в JSON-LD, ни в Microdata).",
            recommendation="Добавьте структурированную разметку schema.org для этой страницы.",
            schema_type="Unknown",
            block_index=0,
        )
        return {"url": source, "status": "ok", "errors": [no_markup_error]}

    all_errors = []
    for block in blocks:
        all_errors.extend(validate_block(block))

    return {"url": source, "status": "ok", "errors": all_errors}


def main():
    parser = argparse.ArgumentParser(
        description="Валидатор структурированной разметки schema.org (Hotel, Product, BreadcrumbList)."
    )
    parser.add_argument(
        "--input", nargs="+", required=True,
        help="Путь к файлу со списком URL (по одному на строку) ИЛИ, с флагом --local, "
             "один или несколько путей к локальным HTML-файлам."
    )
    parser.add_argument(
        "--local", action="store_true",
        help="Трактовать --input как список локальных HTML-файлов, а не файл со списком URL."
    )
    parser.add_argument(
        "--output-dir", default="./report_output",
        help="Папка для сохранения report.csv и report.html (по умолчанию ./report_output)."
    )
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS,
        help=f"Число параллельных потоков обхода (по умолчанию {DEFAULT_WORKERS})."
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help=f"Таймаут запроса в секундах (по умолчанию {DEFAULT_TIMEOUT})."
    )
    parser.add_argument(
        "--retries", type=int, default=DEFAULT_RETRIES,
        help=f"Число повторных попыток при сетевой ошибке (по умолчанию {DEFAULT_RETRIES})."
    )
    parser.add_argument(
        "--json-stdout", action="store_true",
        help="Не писать файлы отчёта, а вывести результат в JSON в stdout (удобно для REST-обвязки)."
    )
    args = parser.parse_args()

    if args.local:
        sources = args.input
    else:
        if len(args.input) != 1:
            parser.error("Без --local ожидается ровно один файл со списком URL.")
        sources = read_url_list(args.input[0])

    if not sources:
        print("Список источников пуст — нечего проверять.", file=sys.stderr)
        sys.exit(1)

    print(f"Найдено источников: {len(sources)}. Запуск проверки...", file=sys.stderr)

    results = []
    start = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_source = {
            executor.submit(process_source, src, args.local, args.timeout, args.retries): src
            for src in sources
        }
        done = 0
        for future in cf.as_completed(future_to_source):
            result = future.result()
            results.append(result)
            done += 1
            if done % 10 == 0 or done == len(sources):
                print(f"  обработано {done}/{len(sources)}", file=sys.stderr)

    elapsed = time.time() - start
    print(f"Готово за {elapsed:.1f} сек.", file=sys.stderr)

    order = {src: i for i, src in enumerate(sources)}
    results.sort(key=lambda r: order.get(r["url"], 0))

    if args.json_stdout:
        serializable = []
        for r in results:
            serializable.append({
                "url": r["url"],
                "status": r["status"],
                "message": r.get("message", ""),
                "errors": [
                    {
                        "code": e.code,
                        "severity": e.severity,
                        "message": e.message,
                        "recommendation": e.recommendation,
                        "schema_type": e.schema_type,
                    } for e in r.get("errors", [])
                ],
            })
        print(json.dumps(serializable, ensure_ascii=False, indent=2))
        return

    os.makedirs(args.output_dir, exist_ok=True)
    csv_path = os.path.join(args.output_dir, "report.csv")
    html_path = os.path.join(args.output_dir, "report.html")
    write_csv_report(results, csv_path)
    write_html_report(results, html_path)

    total_errors = sum(
        sum(1 for e in r["errors"] if e.severity == "error")
        for r in results if r["status"] == "ok"
    )
    print(f"Отчёт сохранён: {csv_path}", file=sys.stderr)
    print(f"Отчёт сохранён: {html_path}", file=sys.stderr)
    print(f"Всего ошибок найдено: {total_errors}", file=sys.stderr)


if __name__ == "__main__":
    main()