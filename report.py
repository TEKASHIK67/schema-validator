# -*- coding: utf-8 -*-
"""
report.py
Формирует итоговый отчёт по результатам проверки списка страниц.
Поддерживает CSV и HTML форматы.
"""

import csv
import html as html_lib
from datetime import datetime


def write_csv_report(results: list[dict], output_path: str) -> None:
    """
    results: список словарей вида
      {
        "url": str,
        "status": "ok" | "error" | "fetch_failed",
        "errors": list[ValidationError],
      }
    Одна строка CSV = одна найденная ошибка. Страницы без ошибок получают
    одну строку с пометкой "OK".
    """
    fieldnames = [
        "url", "schema_type", "severity", "error_code",
        "message", "recommendation",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            url = result["url"]
            if result["status"] == "fetch_failed":
                writer.writerow({
                    "url": url,
                    "schema_type": "",
                    "severity": "error",
                    "error_code": "FETCH_FAILED",
                    "message": result.get("message", "Не удалось загрузить страницу."),
                    "recommendation": "Проверьте доступность URL и повторите попытку.",
                })
                continue

            errors = result["errors"]
            if not errors:
                writer.writerow({
                    "url": url,
                    "schema_type": "",
                    "severity": "ok",
                    "error_code": "",
                    "message": "Нарушений не найдено.",
                    "recommendation": "",
                })
                continue

            for err in errors:
                writer.writerow({
                    "url": url,
                    "schema_type": err.schema_type,
                    "severity": err.severity,
                    "error_code": err.code,
                    "message": err.message,
                    "recommendation": err.recommendation,
                })


def write_html_report(results: list[dict], output_path: str) -> None:
    total_pages = len(results)
    pages_with_errors = sum(
        1 for r in results
        if r["status"] == "fetch_failed" or any(e.severity == "error" for e in r["errors"])
    )
    total_errors = sum(
        sum(1 for e in r["errors"] if e.severity == "error")
        for r in results if r["status"] == "ok"
    )
    total_warnings = sum(
        sum(1 for e in r["errors"] if e.severity == "warning")
        for r in results if r["status"] == "ok"
    )

    rows_html = []
    for group_index, result in enumerate(results):
        url = html_lib.escape(result["url"])
        group_class = "group-even" if group_index % 2 == 0 else "group-odd"

        if result["status"] == "fetch_failed":
            rows_html.append(f'''
            <tr class="row-error {group_class} group-start">
              <td><a href="{url}" target="_blank">{url}</a></td>
              <td>—</td>
              <td><span class="badge badge-error">ошибка</span></td>
              <td>FETCH_FAILED</td>
              <td colspan="2">{html_lib.escape(result.get("message", "Не удалось загрузить страницу."))}</td>
            </tr>''')
            continue

        errors = result["errors"]
        if not errors:
            rows_html.append(f'''
            <tr class="row-ok {group_class} group-start">
              <td><a href="{url}" target="_blank">{url}</a></td>
              <td>—</td>
              <td><span class="badge badge-ok">OK</span></td>
              <td>—</td>
              <td colspan="2">Нарушений не найдено</td>
            </tr>''')
            continue

        row_count = len(errors)
        for i, err in enumerate(errors):
            badge_class = "badge-error" if err.severity == "error" else "badge-warning"
            badge_text = "ошибка" if err.severity == "error" else "предупреждение"
            row_class = "row-error" if err.severity == "error" else "row-warning"
            start_class = "group-start" if i == 0 else ""
            url_cell = (
                f'<td class="url-cell" rowspan="{row_count}">'
                f'<a href="{url}" target="_blank">{url}</a></td>'
                if i == 0 else ""
            )
            rows_html.append(f'''
            <tr class="{row_class} {group_class} {start_class}">
              {url_cell}
              <td>{html_lib.escape(err.schema_type)}</td>
              <td><span class="badge {badge_class}">{badge_text}</span></td>
              <td>{html_lib.escape(err.code)}</td>
              <td>{html_lib.escape(err.message)}</td>
              <td>{html_lib.escape(err.recommendation)}</td>
            </tr>''')

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_doc = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Отчёт валидатора микроразметки schema.org</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 24px; color: #1a1a1a; background: #fafafa; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 20px; }}
  .summary {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .summary-card {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 14px 20px; min-width: 140px; }}
  .summary-card .num {{ font-size: 24px; font-weight: 700; }}
  .summary-card .label {{ font-size: 12px; color: #666; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; }}
  th, td {{ border: 1px solid #e0e0e0; padding: 8px 10px; font-size: 13px; text-align: left; vertical-align: top; }}
  th {{ background: #f0f0f0; position: sticky; top: 0; }}
  .badge {{ padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
  .badge-error {{ background: #fdecea; color: #c0392b; }}
  .badge-warning {{ background: #fff8e1; color: #a9760a; }}
  .badge-ok {{ background: #e8f5e9; color: #2e7d32; }}
  .group-even td {{ background: #ffffff; }}
  .group-odd td {{ background: #f5f7fa; }}
  .row-error.group-even td {{ background: #fff5f4; }}
  .row-error.group-odd td {{ background: #fbeeec; }}
  .row-ok.group-even td {{ background: #f4fbf5; }}
  .row-ok.group-odd td {{ background: #ecf7ed; }}
  .group-start td {{ border-top: 2px solid #999; }}
  .url-cell {{ font-weight: 600; vertical-align: middle !important; border-right: 2px solid #999; }}
  a {{ color: #1565c0; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
  <h1>Отчёт валидатора структурированной разметки (schema.org)</h1>
  <div class="meta">Сформирован: {generated_at}</div>

  <div class="summary">
    <div class="summary-card"><div class="num">{total_pages}</div><div class="label">страниц проверено</div></div>
    <div class="summary-card"><div class="num">{pages_with_errors}</div><div class="label">страниц с ошибками</div></div>
    <div class="summary-card"><div class="num">{total_errors}</div><div class="label">ошибок всего</div></div>
    <div class="summary-card"><div class="num">{total_warnings}</div><div class="label">предупреждений всего</div></div>
  </div>

  <table>
    <thead>
      <tr>
        <th>URL / файл</th>
        <th>Тип разметки</th>
        <th>Уровень</th>
        <th>Код ошибки</th>
        <th>Описание</th>
        <th>Рекомендация</th>
      </tr>
    </thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
</body>
</html>'''

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
