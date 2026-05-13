"""
schema_validator.py
-------------------
Validate and clean:
  1. The SemanticSchema itself (remove hallucinated attributes)
  2. Each data row against the schema (type coercion + null handling)
"""

from __future__ import annotations
import logging
import re
from datetime import datetime
from typing import Any

from schema_models import (
    SemanticSchema, SchemaValidationResult, ValidationIssue,
    InferredType, SchemaAttribute,
)

logger = logging.getLogger(__name__)


# ── Schema self-validation ─────────────────────────────────────────────────────

def validate_schema(schema: SemanticSchema, actual_fields: set[str]) -> SchemaValidationResult:
    """
    Check schema attributes against actual field names.
    Remove attributes that do not exist in the real data.
    """
    issues:          list[ValidationIssue] = []
    removed_fields:  list[str]             = []

    for entity in schema.entities:
        valid_attrs = []
        for attr in entity.attributes:
            if attr.name not in actual_fields and attr.name != "_source_url":
                issues.append(ValidationIssue(
                    field    = attr.name,
                    issue    = f"Field '{attr.name}' not found in extracted data — removed.",
                    severity = "warning",
                ))
                removed_fields.append(attr.name)
                logger.debug("Removed hallucinated schema field: %s", attr.name)
            else:
                valid_attrs.append(attr)
        entity.attributes = valid_attrs

    # Check primary keys still exist
    for entity in schema.entities:
        if entity.primary_key:
            pk_names = {a.name for a in entity.attributes}
            if entity.primary_key not in pk_names:
                issues.append(ValidationIssue(
                    field    = entity.primary_key,
                    issue    = f"Primary key '{entity.primary_key}' was removed — setting to None.",
                    severity = "warning",
                ))
                entity.primary_key = None

    return SchemaValidationResult(
        valid          = len([i for i in issues if i.severity == "error"]) == 0,
        issues         = issues,
        removed_fields = removed_fields,
    )


# ── Row coercion helpers ───────────────────────────────────────────────────────

def _coerce(value: Any, attr: SchemaAttribute) -> Any:
    """
    Try to coerce a raw value to the expected InferredType.
    Returns the coerced value, or None on failure.
    """
    if value is None or str(value).strip() in ("", "null", "None", "N/A", "n/a", "-"):
        return None

    t = attr.inferred_type
    s = str(value).strip()

    try:
        if t == InferredType.INTEGER:
            return int(re.sub(r"[^\d\-]", "", s))

        if t == InferredType.FLOAT:
            clean = re.sub(r"[^\d\-\.]", "", s)
            return float(clean)

        if t == InferredType.BOOLEAN:
            return s.lower() in ("true", "yes", "1", "on")

        if t == InferredType.CURRENCY:
            clean = re.sub(r"[^\d\-\.]", "", s)
            return float(clean) if clean else None

        if t == InferredType.PERCENTAGE:
            clean = s.replace("%", "").strip()
            return float(clean) if clean else None

        if t == InferredType.DATE:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(s, fmt).date().isoformat()
                except ValueError:
                    pass
            return s   # keep as-is if we can't parse

        if t == InferredType.DATETIME:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(s, fmt).isoformat()
                except ValueError:
                    pass
            return s

        # STRING, URL, EMAIL, ARRAY, OBJECT, UNKNOWN → keep as string
        return s

    except Exception:
        return s   # never lose data — return original string


# ── Row validation ─────────────────────────────────────────────────────────────

def validate_rows(
    rows:   list[dict],
    schema: SemanticSchema,
) -> tuple[list[dict], SchemaValidationResult]:
    """
    Validate and coerce every row against the schema.
    Returns (cleaned_rows, validation_result).
    """
    # Build field → attribute lookup
    attr_map: dict[str, SchemaAttribute] = {}
    for entity in schema.entities:
        for attr in entity.attributes:
            attr_map[attr.name] = attr

    issues:         list[ValidationIssue] = []
    coerced_fields: list[str]             = set()
    cleaned_rows:   list[dict]            = []

    for i, row in enumerate(rows):
        clean_row = {}
        for field, value in row.items():
            if field not in attr_map:
                # Field not in schema — pass through as-is
                clean_row[field] = value
                continue

            attr         = attr_map[field]
            coerced_val  = _coerce(value, attr)

            if coerced_val is None and not attr.nullable:
                issues.append(ValidationIssue(
                    field    = field,
                    issue    = f"Row {i}: non-nullable field '{field}' is null.",
                    severity = "warning",
                ))

            if coerced_val != value and value is not None:
                coerced_fields.add(field)

            # Use canonical_name as the output key
            out_key = attr.canonical_name or field
            clean_row[out_key] = coerced_val

        cleaned_rows.append(clean_row)

    return cleaned_rows, SchemaValidationResult(
        valid          = True,
        issues         = issues,
        coerced_fields = list(coerced_fields),
    )
