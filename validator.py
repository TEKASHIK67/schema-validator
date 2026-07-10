# -*- coding: utf-8 -*-
"""
validator.py
Проверяет каждый блок разметки в два этапа:
  1. Синтаксическая валидность (только для JSON-LD блоков).
  2. Семантическая валидность по правилам для конкретного @type
     (Hotel, Product, BreadcrumbList) — обязательные поля, типы данных,
     согласованность нумерации и т.д.
"""

import json
import re
from dataclasses import dataclass, field
from extractor import ParsedBlock


@dataclass
class ValidationError:
    code: str            # короткий машиночитаемый код ошибки
    severity: str        # "error" | "warning"
    message: str         # человекочитаемое описание
    recommendation: str  # что сделать, чтобы исправить
    schema_type: str = "" # Hotel / Product / BreadcrumbList / Unknown
    block_index: int = 0


# --------------------------------------------------------------------------
# Этап 1: синтаксис
# --------------------------------------------------------------------------

TRAILING_COMMA_RE = re.compile(r',\s*([}\]])')


def try_strict_parse(raw_text: str):
    """Возвращает (data, error) — data=None при ошибке."""
    try:
        return json.loads(raw_text), None
    except json.JSONDecodeError as e:
        return None, e


def try_lenient_parse(raw_text: str):
    """
    Пытается исправить самые частые синтаксические ошибки (висячие запятые)
    и распарсить ещё раз.
    """
    fixed = TRAILING_COMMA_RE.sub(r'\1', raw_text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------
# Этап 2: семантика по типам schema.org
# --------------------------------------------------------------------------

def _is_number(value) -> bool:
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.replace(',', '.'))
            return True
        except ValueError:
            return False
    return False


def validate_hotel(data: dict, block_index: int) -> list[ValidationError]:
    errors = []
    schema_type = "Hotel"

    # Обязательные поля по рекомендациям Google для LodgingBusiness/Hotel
    required_fields = ["name", "address"]
    for field_name in required_fields:
        if field_name not in data:
            errors.append(ValidationError(
                code="MISSING_REQUIRED_FIELD",
                severity="error",
                message=f'Отсутствует обязательное поле "{field_name}" для типа Hotel.',
                recommendation=(
                    f'Добавьте поле "{field_name}" в объект Hotel. '
                    'Без него Google может не показать rich-результат в выдаче.'
                ),
                schema_type=schema_type,
                block_index=block_index,
            ))

    # Рекомендованные, но не обязательные поля
    recommended_fields = ["starRating", "aggregateRating", "image", "geo"]
    for field_name in recommended_fields:
        if field_name not in data:
            errors.append(ValidationError(
                code="MISSING_RECOMMENDED_FIELD",
                severity="warning",
                message=f'Отсутствует рекомендованное поле "{field_name}" для Hotel.',
                recommendation=f'Рекомендуется добавить "{field_name}" для более полного сниппета.',
                schema_type=schema_type,
                block_index=block_index,
            ))

    # starRating.ratingValue — число от 1 до 5
    star = data.get("starRating")
    if isinstance(star, dict) and "ratingValue" in star:
        if not _is_number(star["ratingValue"]):
            errors.append(ValidationError(
                code="INVALID_TYPE",
                severity="error",
                message=f'starRating.ratingValue должно быть числом, получено: {star["ratingValue"]!r}.',
                recommendation='Укажите числовое значение звёздности отеля, например "5".',
                schema_type=schema_type,
                block_index=block_index,
            ))

    # aggregateRating.ratingValue и reviewCount — числа
    agg = data.get("aggregateRating")
    if isinstance(agg, dict):
        if "ratingValue" in agg and not _is_number(agg["ratingValue"]):
            errors.append(ValidationError(
                code="INVALID_TYPE",
                severity="error",
                message=f'aggregateRating.ratingValue должно быть числом, получено: {agg["ratingValue"]!r}.',
                recommendation='Укажите числовое значение рейтинга, например "9.4", а не текстовую оценку.',
                schema_type=schema_type,
                block_index=block_index,
            ))
        if "reviewCount" in agg and not _is_number(agg["reviewCount"]):
            errors.append(ValidationError(
                code="INVALID_TYPE",
                severity="error",
                message=f'aggregateRating.reviewCount должно быть числом, получено: {agg["reviewCount"]!r}.',
                recommendation='Укажите числовое количество отзывов.',
                schema_type=schema_type,
                block_index=block_index,
            ))

    # address — минимальная структура
    address = data.get("address")
    if isinstance(address, dict):
        for sub_field in ["addressCountry", "addressLocality"]:
            if sub_field not in address:
                errors.append(ValidationError(
                    code="MISSING_RECOMMENDED_FIELD",
                    severity="warning",
                    message=f'В address отсутствует "{sub_field}".',
                    recommendation=f'Добавьте "{sub_field}" в объект address для более точной геопривязки.',
                    schema_type=schema_type,
                    block_index=block_index,
                ))

    return errors


def validate_product(data: dict, block_index: int) -> list[ValidationError]:
    errors = []
    schema_type = "Product"

    required_fields = ["name", "offers"]
    for field_name in required_fields:
        if field_name not in data:
            errors.append(ValidationError(
                code="MISSING_REQUIRED_FIELD",
                severity="error",
                message=f'Отсутствует обязательное поле "{field_name}" для типа Product.',
                recommendation=f'Добавьте поле "{field_name}" — оно обязательно для rich-результатов товара.',
                schema_type=schema_type,
                block_index=block_index,
            ))

    offers = data.get("offers")
    if isinstance(offers, dict):
        for f in ["price", "priceCurrency"]:
            if f not in offers:
                errors.append(ValidationError(
                    code="MISSING_REQUIRED_FIELD",
                    severity="error",
                    message=f'В offers отсутствует обязательное поле "{f}".',
                    recommendation=f'Добавьте "{f}" в объект offers.',
                    schema_type=schema_type,
                    block_index=block_index,
                ))
        if "price" in offers and not _is_number(offers["price"]):
            errors.append(ValidationError(
                code="INVALID_TYPE",
                severity="error",
                message=f'offers.price должно быть числом, получено: {offers["price"]!r}.',
                recommendation='Укажите числовое значение цены без валютных символов.',
                schema_type=schema_type,
                block_index=block_index,
            ))

    agg = data.get("aggregateRating")
    if isinstance(agg, dict) and "ratingValue" in agg and not _is_number(agg["ratingValue"]):
        errors.append(ValidationError(
            code="INVALID_TYPE",
            severity="error",
            message=f'aggregateRating.ratingValue должно быть числом, получено: {agg["ratingValue"]!r}.',
            recommendation='Укажите числовое значение рейтинга.',
            schema_type=schema_type,
            block_index=block_index,
        ))

    return errors


def validate_breadcrumb(data: dict, block_index: int) -> list[ValidationError]:
    errors = []
    schema_type = "BreadcrumbList"

    items = data.get("itemListElement")
    if not isinstance(items, list) or not items:
        errors.append(ValidationError(
            code="MISSING_REQUIRED_FIELD",
            severity="error",
            message='В BreadcrumbList отсутствует непустой массив itemListElement.',
            recommendation='Добавьте массив itemListElement с элементами ListItem.',
            schema_type=schema_type,
            block_index=block_index,
        ))
        return errors

    positions = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        if "position" not in item:
            errors.append(ValidationError(
                code="MISSING_REQUIRED_FIELD",
                severity="error",
                message=f'Элемент #{i + 1} в itemListElement не содержит поле "position".',
                recommendation='Добавьте поле "position" к каждому ListItem.',
                schema_type=schema_type,
                block_index=block_index,
            ))
        else:
            pos_val = item["position"]
            try:
                # Безопасно приводим строковые числа "1", 1.0 и т.д. к целому числу (актуально для Microdata)
                pos_val = int(float(str(pos_val).replace(',', '.')))
            except (ValueError, TypeError):
                pass
            positions.append(pos_val)

        if "name" not in item:
            errors.append(ValidationError(
                code="MISSING_REQUIRED_FIELD",
                severity="error",
                message=f'Элемент #{i + 1} в itemListElement не содержит поле "name".',
                recommendation='Добавьте поле "name" с текстом хлебной крошки.',
                schema_type=schema_type,
                block_index=block_index,
            ))

    # Проверка непрерывности нумерации: 1, 2, 3, ... без пропусков
    if positions:
        sorted_positions = sorted(positions)
        expected = list(range(1, len(positions) + 1))
        if sorted_positions != expected:
            errors.append(ValidationError(
                code="BROKEN_SEQUENCE",
                severity="error",
                message=(
                    f'Нарушена нумерация position в BreadcrumbList: '
                    f'получено {sorted_positions}, ожидалось {expected} (без пропусков).'
                ),
                recommendation='Пронумеруйте элементы подряд начиная с 1, без пропусков.',
                schema_type=schema_type,
                block_index=block_index,
            ))

    return errors


TYPE_VALIDATORS = {
    "Hotel": validate_hotel,
    "LodgingBusiness": validate_hotel,
    "Product": validate_product,
    "BreadcrumbList": validate_breadcrumb,
}


def validate_block(block: ParsedBlock) -> list[ValidationError]:
    """Полная проверка одного блока разметки: синтаксис (только для JSON-LD) + семантика."""
    errors: list[ValidationError] = []
    data = None

    if block.source_format == "json-ld":
        data, json_err = try_strict_parse(block.raw_text)

        if json_err is not None:
            errors.append(ValidationError(
                code="JSON_SYNTAX_ERROR",
                severity="error",
                message=f'Синтаксическая ошибка JSON: {json_err.msg} (строка {json_err.lineno}, символ {json_err.colno}).',
                recommendation='Исправьте синтаксис JSON (частая причина — висячая запятая перед } или ]).',
                schema_type="Unknown",
                block_index=block.index,
            ))
            # Пробуем восстановиться, чтобы найти дополнительные (семантические) проблемы
            data = try_lenient_parse(block.raw_text)
            if data is None:
                # Не удалось восстановить — дальше проверять нечего
                return errors
    else:
        # Для Microdata данные уже распарсены и нормализованы библиотекой extruct
        data = block.raw_data

    if not isinstance(data, dict):
        return errors

    schema_type = data.get("@type", "Unknown")
    validator_fn = TYPE_VALIDATORS.get(schema_type)

    if validator_fn is None:
        errors.append(ValidationError(
            code="UNSUPPORTED_TYPE",
            severity="warning",
            message=f'Тип "@type": "{schema_type}" не поддерживается текущим набором правил валидатора.',
            recommendation='Добавьте правила валидации для этого типа, если он важен для SEO.',
            schema_type=str(schema_type),
            block_index=block.index,
        ))
        return errors

    for err in validator_fn(data, block.index):
        errors.append(err)

    return errors