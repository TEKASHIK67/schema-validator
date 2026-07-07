#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py — CLI-утилита валидации структурированной разметки schema.org.

Использование:

  # Обход списка URL из файла (по одному URL в строке, строки с # игнорируются)
  python3 cli.py --input urls.txt --output-dir ./report --workers 10

  # Проверка локальных HTML-файлов (для теста / отладки без сети)
  python3 cli.py --input page1.html page2.html --local --output-dir ./report

  # Проверка одной страницы с выводом только в JSON в stdout (для REST-обвязки)
  python3 cli.py --input page.html --local --json-stdout

Результат:
  report.csv  — построчный список нарушений
  report.html — наглядный HTML-отчёт со сводкой
"""

import argparse
import json
import os
import sys
import time
import concurrent.futures as cf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor import extract_jsonld_blocks
from validator import validate_block
from report import write_csv_report, write_html_report

DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 2
DEFAULT_WORKERS = 8
USER_AGENT = "SchemaValidatorBot/1.0 (+SEO structured data audit)"


def read_url_list(path: str) -> list[str]:
    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls


def fetch_html(url: str, timeout: int, retries: int):
    """Загружает HTML по URL с повторными попытками. Возвращает (html, error)."""
    import requests
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            return resp.text, None
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))  # экспоненциальная задержка
    return None, last_err


def process_source(source: str, is_local: bool, timeout: int, retries: int) -> dict:
    """Полный цикл обработки одной страницы: загрузка -> извлечение -> валидация."""
    if is_local:
        try:
            with open(source, "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception as e:
            return {"url": source, "status": "fetch_failed", "message": str(e), "errors": []}
    else:
        html_content, err = fetch_html(source, timeout, retries)
        if html_content is None:
            return {"url": source, "status": "fetch_failed", "message": err, "errors": []}

    blocks = extract_jsonld_blocks(html_content)

    if not blocks:
        # Отсутствие микроразметки — это тоже находка для SEO-отчёта
        from validator import ValidationError
        no_ld_error = ValidationError(
            code="NO_JSONLD_FOUND",
            severity="warning",
            message="На странице не найдено ни одного блока application/ld+json.",
            recommendation="Добавьте структурированную разметку schema.org для этой страницы.",
            schema_type="Unknown",
            block_index=0,
        )
        return {"url": source, "status": "ok", "errors": [no_ld_error]}

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
            if done % 50 == 0 or done == len(sources):
                print(f"  обработано {done}/{len(sources)}", file=sys.stderr)

    elapsed = time.time() - start
    print(f"Готово за {elapsed:.1f} сек.", file=sys.stderr)

    # Сохраняем порядок как во входном списке (потоки завершаются не по порядку)
    order = {src: i for i, src in enumerate(sources)}
    results.sort(key=lambda r: order.get(r["url"], 0))

    if args.json_stdout:
        serializable = []
        for r in results:
            serializable.append({
                "url": r["url"],
                "status": r["status"],
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
