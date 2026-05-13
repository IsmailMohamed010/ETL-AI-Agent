"""
schema_normalizer.py
--------------------
Normalize extracted rows using the generated SemanticSchema:
  - Rename fields to canonical_name (snake_case)
  - Drop unknown fields (optional, configurable)
  - Add schema metadata column _schema_domain
"""

from __future__ import annotations
import logging
from schema_models import SemanticSchema

logger = logging.getLogger(__name__)


def normalize_rows(
    rows:            list[dict],
    schema:          SemanticSchema,
    drop_unknown:    bool = False,
    add_meta_column: bool = True,
) -> list[dict]:
    """
    Normalize raw rows:
    - Rename each field to its canonical_name from the schema.
    - Optionally drop fields not present in the schema.
    - Optionally inject _schema_domain column.

    Args:
        rows:            Raw extracted rows from the ETL pipeline.
        schema:          Validated SemanticSchema.
        drop_unknown:    If True, remove fields not defined in schema.
        add_meta_column: If True, add _schema_domain field to every row.

    Returns:
        List of normalized dicts.
    """
    # Build rename map: original_name → canonical_name
    rename_map: dict[str, str] = {}
    schema_fields: set[str]    = set()

    for entity in schema.entities:
        for attr in entity.attributes:
            rename_map[attr.name] = attr.canonical_name or attr.name
            schema_fields.add(attr.name)

    if not rename_map:
        logger.warning("Schema has no attributes — normalization is a pass-through.")
        return rows

    normalized: list[dict] = []

    for row in rows:
        new_row: dict = {}

        for field, value in row.items():
            if field == "_source_url":
                new_row["_source_url"] = value
                continue

            if field in rename_map:
                new_row[rename_map[field]] = value
            elif not drop_unknown:
                new_row[field] = value
            else:
                logger.debug("Dropping unknown field: %s", field)

        if add_meta_column:
            new_row["_schema_domain"] = schema.domain.value

        normalized.append(new_row)

    logger.info(
        "Normalized %d rows. Renamed %d fields. drop_unknown=%s",
        len(normalized), len(rename_map), drop_unknown,
    )
    return normalized
