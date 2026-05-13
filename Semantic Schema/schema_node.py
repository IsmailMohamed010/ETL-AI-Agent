"""
schema_node.py
--------------
LangGraph node: Semantic Schema Layer

Pipeline position:
  Extract → [node_semantic_schema] → Transformation → Load

Reads:   parsed_rows, url (from WebAgentState or equivalent)
Writes:  normalized_rows, semantic_schema, schema_validation
"""

from __future__ import annotations
import logging
from typing import Any

from domain_detector  import detect_domain
from schema_generator import generate_schema
from schema_validator import validate_schema, validate_rows
from schema_normalizer import normalize_rows
from schema_models    import SemanticSchema

logger = logging.getLogger(__name__)


def node_semantic_schema(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node for semantic schema generation and normalization.

    Input state keys:
        parsed_rows  (list[dict])  — from node_parse / extract pipeline
        url          (str)         — source URL (used for domain detection hints)
        config       (dict)        — optional keys:
                                       schema_drop_unknown  (bool, default False)
                                       schema_add_meta      (bool, default True)
                                       schema_llm_threshold (float, default 0.15)

    Output state keys added:
        normalized_rows   (list[dict])  — rows with canonical field names
        semantic_schema   (dict)        — SemanticSchema.to_jsonb()
        schema_validation (dict)        — validation issues summary
    """
    try:
        rows   = state.get("parsed_rows", [])
        url    = state.get("url", "")
        cfg    = state.get("config", {})

        if not rows:
            raise ValueError("parsed_rows is empty — nothing to build schema from.")

        drop_unknown    = cfg.get("schema_drop_unknown",   False)
        add_meta        = cfg.get("schema_add_meta",       True)
        llm_threshold   = cfg.get("schema_llm_threshold",  0.15)

        # ── Step 1: Detect domain ─────────────────────────────────────────────
        logger.info("[SemanticSchema] Step 1/4 — Domain detection (%d rows)…", len(rows))
        domain = detect_domain(rows, url=url, llm_threshold=llm_threshold)
        logger.info("[SemanticSchema] Domain detected: %s", domain.value)

        # ── Step 2: Generate schema ───────────────────────────────────────────
        logger.info("[SemanticSchema] Step 2/4 — Schema generation…")
        schema: SemanticSchema = generate_schema(rows, domain, url=url)

        # ── Step 3: Validate schema ───────────────────────────────────────────
        logger.info("[SemanticSchema] Step 3/4 — Schema validation…")
        actual_fields  = {k for row in rows for k in row.keys()}
        schema_result  = validate_schema(schema, actual_fields)

        if schema_result.removed_fields:
            logger.warning(
                "[SemanticSchema] Removed %d hallucinated fields: %s",
                len(schema_result.removed_fields),
                schema_result.removed_fields,
            )

        # ── Step 4: Normalize rows ────────────────────────────────────────────
        logger.info("[SemanticSchema] Step 4/4 — Row normalization + coercion…")
        normalized, row_result = validate_rows(rows, schema)
        normalized = normalize_rows(
            normalized,
            schema,
            drop_unknown    = drop_unknown,
            add_meta_column = add_meta,
        )

        # Merge validation results
        all_issues = schema_result.issues + row_result.issues

        logger.info(
            "[SemanticSchema] Complete. %d rows normalized, %d issues.",
            len(normalized), len(all_issues),
        )

        return {
            "normalized_rows":   normalized,
            "semantic_schema":   schema.to_jsonb(),
            "schema_validation": {
                "valid":           schema_result.valid and row_result.valid,
                "removed_fields":  schema_result.removed_fields,
                "coerced_fields":  row_result.coerced_fields,
                "issues":          [i.model_dump() for i in all_issues],
                "domain":          domain.value,
                "confidence":      schema.confidence,
            },
            "status": "running",
        }

    except Exception as exc:
        logger.error("[SemanticSchema] node_semantic_schema failed: %s", exc, exc_info=True)
        return {
            "errors": state.get("errors", []) + [f"semantic_schema: {exc}"],
            "status": "failed",
        }
