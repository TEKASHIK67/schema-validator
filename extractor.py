# -*- coding: utf-8 -*-
"""
extractor.py
Извлекает все блоки <script type="application/ld+json">...</script> из HTML-страницы.
Не использует полноценный HTML-парсер намеренно (regex быстрее и достаточен для
задачи, т.к. нас интересует только содержимое конкретного тега), но при желании
легко заменить на BeautifulSoup.
"""

import re
from dataclasses import dataclass


@dataclass
class JsonLdBlock:
    index: int          # порядковый номер блока на странице (с 1)
    raw_text: str        # сырой текст внутри <script>...</script>
    start_offset: int    # позиция начала блока в исходном HTML (для отладки)


SCRIPT_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def extract_jsonld_blocks(html: str) -> list[JsonLdBlock]:
    """Находит все script-блоки с типом application/ld+json в HTML."""
    blocks = []
    for i, match in enumerate(SCRIPT_RE.finditer(html), start=1):
        raw = match.group(1).strip()
        blocks.append(JsonLdBlock(index=i, raw_text=raw, start_offset=match.start()))
    return blocks
