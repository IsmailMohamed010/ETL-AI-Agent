"""
schema_generator.py
-------------------
Generate a SemanticSchema from extracted rows using the LLM.
"""

from __future__ import annotations
import json
import logging
import re
import requests

from schema_models import (
    DomainType, SemanticSchema, SchemaEntity, SchemaAttribute,
    SchemaRelationship, InferredType, RelationshipCardinality,
)
from schema_prompts import SCHEMA_GENERATION_PROMPT

logger  = logging.getLogger(__name__)

OLLAMA_URL  = "http://localhost:11434/api/chat"
MODEL_ID    = "qwen2.5:7b-instruct"


# ── Type inference helpers ─────────────────────────────────────────────────────

_INT_RE   = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")
_DATE_RE  = re.compile(r"\d{4}-\d{2}-\d{2}")
_URL_RE   = re.compile(r"^https?://")
_EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
_PCT_RE   = re.compile(r"^-?\d+(\.\d+)?%$")
_CUR_RE   = re.compile(r"^[$€£¥]\s*[\d,]+(\.\d+)?$")


def _infer_type(value) -> InferredType:
    if value is None:
        return InferredType.NULL
    s = str(value).strip()
    if not s:
        return InferredType.NULL
    if s.lower() in ("true", "false"):
        return InferredType.BOOLEAN
    if _PCT_RE.match(s):
        return InferredType.PERCENTAGE
    if _CUR_RE.match(s):
        return InferredType.CURRENCY
    if _EMAIL_RE.match(s):
        return InferredType.EMAIL
    if _URL_RE.match(s):
        return InferredType.URL
    if _INT_RE.match(s):
        return InferredType.INTEGER
    if _FLOAT_RE.match(s):
        return InferredType.FLOAT
    if _DATE_RE.search(s):
        return InferredType.DATETIME if "T" in s or len(s) > 10 else InferredType.DATE
    return InferredType.STRING


def _infer_types_from_rows(rows: list[dict]) -> dict[str, InferredType]:
    """Infer the best type for each field across all rows."""
    field_types: dict[str, list[InferredType]] = {}
    for row in rows:
        for k, v in row.items():
            field_types.setdefault(k, []).append(_infer_type(v))

    result = {}
    for field, types in field_types.items():
        non_null = [t for t in types if t != InferredType.NULL]
        if not non_null:
            result[field] = InferredType.NULL
        else:
            # majority vote
            result[field] = max(set(non_null), key=non_null.count)
    return result


# ── LLM schema call ────────────────────────────────────────────────────────────

def _call_llm_for_schema(
    rows:         list[dict],
    domain:       DomainType,
    field_names:  list[str],
) -> dict:
    sample_rows = json.dumps(rows[:3], ensure_ascii=False, indent=2)
    prompt      = SCHEMA_GENERATION_PROMPT.format(
        domain      = domain.value,
        field_names = field_names,
        sample_rows = sample_rows,
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model":    MODEL_ID,
                "messages": [
                    {"role": "system", "content": "You are a semantic data modeling expert. Return only valid JSON."},
                    {"role": "user",   "content": prompt},
                ],
                "stream":  False,
                "options": {"temperature": 0, "num_predict": 2048},
            },
            timeout=120,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()

        # Strip markdown fences if present
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()

        # Extract first JSON object
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            return json.loads(match.group(0))

    except Exception as exc:
        logger.warning("LLM schema generation failed: %s", exc)

    return {}


# ── Schema assembly ────────────────────────────────────────────────────────────

def _assemble_schema(
    llm_output:   dict,
    domain:       DomainType,
    field_names:  list[str],
    inferred:     dict[str, InferredType],
    url:          str,
) -> SemanticSchema:
    """
    Build a SemanticSchema from LLM output.
    Falls back to auto-generated flat schema if LLM output is empty/invalid.
    """
    entities:       list[SchemaEntity]       = []
    relationships:  list[SchemaRelationship] = []
    confidence      = float(llm_output.get("confidence", 0.5))
    notes           = llm_output.get("notes")

    valid_fields = set(field_names)

    for raw_entity in llm_output.get("entities", []):
        attrs = []
        for raw_attr in raw_entity.get("attributes", []):
            name = raw_attr.get("name", "")
            if name not in valid_fields:
                logger.debug("Removing hallucinated field: %s", name)
                continue
            try:
                itype = InferredType(raw_attr.get("inferred_type", "unknown"))
            except ValueError:
                itype = InferredType.UNKNOWN
            # Override with locally inferred type if LLM returned unknown
            if itype == InferredType.UNKNOWN:
                itype = inferred.get(name, InferredType.UNKNOWN)
            attrs.append(SchemaAttribute(
                name           = name,
                canonical_name = raw_attr.get("canonical_name") or _to_snake(name),
                inferred_type  = itype,
                description    = raw_attr.get("description"),
                nullable       = raw_attr.get("nullable", True),
                example_value  = raw_attr.get("example_value"),
            ))
        entities.append(SchemaEntity(
            name        = raw_entity.get("name", "Record"),
            description = raw_entity.get("description"),
            primary_key = raw_entity.get("primary_key"),
            attributes  = attrs,
        ))

    for raw_rel in llm_output.get("relationships", []):
        try:
            card = RelationshipCardinality(raw_rel.get("cardinality", "1:N"))
        except ValueError:
            card = RelationshipCardinality.ONE_TO_MANY
        relationships.append(SchemaRelationship(
            from_entity   = raw_rel.get("from_entity", ""),
            to_entity     = raw_rel.get("to_entity", ""),
            via_attribute = raw_rel.get("via_attribute", ""),
            cardinality   = card,
            description   = raw_rel.get("description"),
        ))

    # Fallback: auto-build a flat entity if LLM gave nothing
    if not entities:
        logger.warning("LLM returned no entities — building flat schema from field names.")
        attrs = [
            SchemaAttribute(
                name           = f,
                canonical_name = _to_snake(f),
                inferred_type  = inferred.get(f, InferredType.UNKNOWN),
            )
            for f in field_names if f != "_source_url"
        ]
        entities = [SchemaEntity(name="Record", attributes=attrs)]
        confidence = 0.3

    return SemanticSchema(
        domain        = domain,
        entities      = entities,
        relationships = relationships,
        raw_fields    = field_names,
        confidence    = confidence,
        source_url    = url,
        notes         = notes,
    )


def _to_snake(name: str) -> str:
    s = re.sub(r"[\s\-\.]+", "_", name.strip().lower())
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or name


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_schema(
    rows:   list[dict],
    domain: DomainType,
    url:    str = "",
) -> SemanticSchema:
    """
    Generate a SemanticSchema from extracted rows.
    1. Infer types locally (fast, no LLM)
    2. Call LLM for entity/relationship structure
    3. Assemble final schema with validation guard
    """
    field_names = list({k for row in rows for k in row.keys()})
    inferred    = _infer_types_from_rows(rows)

    logger.info("Calling LLM for schema generation (domain=%s, fields=%d)…",
                domain.value, len(field_names))

    llm_output = _call_llm_for_schema(rows, domain, field_names)

    schema = _assemble_schema(llm_output, domain, field_names, inferred, url)
    logger.info(
        "Schema generated: %d entities, %d relationships, confidence=%.2f",
        len(schema.entities), len(schema.relationships), schema.confidence,
    )
    return schema
