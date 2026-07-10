# -*- coding: utf-8 -*-
"""
extractor.py
Извлекает все блоки структурированной разметки из HTML-страницы.
Поддерживает:
  1. JSON-LD (извлекает сырой текст блоков <script type="application/ld+json">,
     чтобы validator.py мог проверить синтаксис и выполнить восстановление).
  2. Microdata (извлекает с помощью библиотеки extruct и нормализует в формат словаря).
"""

import re
import extruct
from dataclasses import dataclass


@dataclass
class ParsedBlock:
    index: int          # порядковый номер блока на странице (с 1)
    raw_text: str = ""   # сырой текст (только для JSON-LD, для проверки синтаксиса)
    raw_data: dict = None # готовый словарь (для Microdata)
    source_format: str = "json-ld" # "json-ld" или "microdata"


SCRIPT_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def normalize_microdata_item(item: dict) -> dict:
    """
    Приводит структуру Microdata от extruct к плоскому словарю,
    похожему на структуру JSON-LD, для совместимости с валидатором.
    """
    if not isinstance(item, dict):
        return item

    full_type = item.get("type", "Unknown")
    # Превращаем "http://schema.org/Hotel" в "Hotel"
    schema_type = str(full_type).split('/')[-1] if full_type else "Unknown"

    normalized = {"@type": schema_type}
    properties = item.get("properties", {})

    for key, val in properties.items():
        if isinstance(val, dict) and "properties" in val:
            normalized[key] = normalize_microdata_item(val)
        elif isinstance(val, list):
            normalized_list = []
            for sub_val in val:
                if isinstance(sub_val, dict) and "properties" in sub_val:
                    normalized_list.append(normalize_microdata_item(sub_val))
                else:
                    normalized_list.append(sub_val)
            normalized[key] = normalized_list
        else:
            normalized[key] = val

    return normalized


def extract_structured_data(html: str) -> list[ParsedBlock]:
    """Находит все блоки разметки (JSON-LD и Microdata) в HTML-коде."""
    blocks = []
    block_index = 1

    # 1. Извлекаем JSON-LD как сырой текст для валидации синтаксиса
    for match in SCRIPT_RE.finditer(html):
        raw = match.group(1).strip()
        blocks.append(ParsedBlock(
            index=block_index,
            raw_text=raw,
            source_format="json-ld"
        ))
        block_index += 1

    # 2. Извлекаем Microdata через extruct
    try:
        extracted = extruct.extract(html, syntaxes=['microdata'])
        microdata_items = extracted.get('microdata', [])
        for item in microdata_items:
            if isinstance(item, dict):
                normalized = normalize_microdata_item(item)
                blocks.append(ParsedBlock(
                    index=block_index,
                    raw_data=normalized,
                    source_format="microdata"
                ))
                block_index += 1
    except Exception as extruct_err:
        # === ВРЕМЕННЫЙ ДЕБАГ ===
        import sys
        print(f"--- [DEBUG] Ошибка библиотеки extruct: {extruct_err} ---", file=sys.stderr)
        # === КОНЕЦ ВРЕМЕННОГО ДЕБАГА ===
        pass

    return blocks