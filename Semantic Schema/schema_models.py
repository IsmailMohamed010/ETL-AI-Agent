"""
schema_models.py
----------------
Pydantic models for semantic schema representation.
PostgreSQL JSONB-compatible (all models support .model_dump()).
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Domain Types ───────────────────────────────────────────────────────────────

class DomainType(str, Enum):
    FOOTBALL        = "football-analysis"
    ECOMMERCE       = "e-commerce"
    REAL_ESTATE     = "real-estate"
    NEWS            = "news"
    LOGS            = "logs"
    JOBS            = "jobs"
    FINANCE         = "finance"
    HEALTHCARE      = "healthcare"
    SOCIAL_MEDIA    = "social-media"
    UNKNOWN         = "unknown"


# ── Inferred Datatypes ─────────────────────────────────────────────────────────

class InferredType(str, Enum):
    STRING      = "string"
    INTEGER     = "integer"
    FLOAT       = "float"
    BOOLEAN     = "boolean"
    DATE        = "date"
    DATETIME    = "datetime"
    URL         = "url"
    EMAIL       = "email"
    CURRENCY    = "currency"
    PERCENTAGE  = "percentage"
    ARRAY       = "array"
    OBJECT      = "object"
    NULL        = "null"
    UNKNOWN     = "unknown"


# ── Attribute ──────────────────────────────────────────────────────────────────

class SchemaAttribute(BaseModel):
    name:           str
    inferred_type:  InferredType        = InferredType.UNKNOWN
    description:    Optional[str]       = None
    nullable:       bool                = True
    example_value:  Optional[Any]       = None
    canonical_name: Optional[str]       = None   # normalized snake_case name


# ── Entity ─────────────────────────────────────────────────────────────────────

class SchemaEntity(BaseModel):
    name:           str
    description:    Optional[str]       = None
    attributes:     list[SchemaAttribute] = Field(default_factory=list)
    primary_key:    Optional[str]       = None   # attribute name that is the PK


# ── Relationship ───────────────────────────────────────────────────────────────

class RelationshipCardinality(str, Enum):
    ONE_TO_ONE   = "1:1"
    ONE_TO_MANY  = "1:N"
    MANY_TO_MANY = "N:M"

class SchemaRelationship(BaseModel):
    from_entity:    str
    to_entity:      str
    via_attribute:  str                              # foreign key / join field
    cardinality:    RelationshipCardinality = RelationshipCardinality.ONE_TO_MANY
    description:    Optional[str]           = None


# ── Full Semantic Schema ───────────────────────────────────────────────────────

class SemanticSchema(BaseModel):
    domain:         DomainType              = DomainType.UNKNOWN
    entities:       list[SchemaEntity]      = Field(default_factory=list)
    relationships:  list[SchemaRelationship]= Field(default_factory=list)
    raw_fields:     list[str]               = Field(default_factory=list)   # original column names
    confidence:     float                   = 0.0                           # 0-1
    source_url:     Optional[str]           = None
    notes:          Optional[str]           = None

    def to_jsonb(self) -> dict:
        """Serialize to PostgreSQL JSONB-compatible dict."""
        return self.model_dump(mode="json")

    def attribute_map(self) -> dict[str, SchemaAttribute]:
        """Flat map: raw_field_name → SchemaAttribute (across all entities)."""
        mapping = {}
        for entity in self.entities:
            for attr in entity.attributes:
                key = attr.canonical_name or attr.name
                mapping[key] = attr
        return mapping


# ── Validation Result ──────────────────────────────────────────────────────────

class ValidationIssue(BaseModel):
    field:      str
    issue:      str
    severity:   str = "warning"   # "warning" | "error"

class SchemaValidationResult(BaseModel):
    valid:          bool
    issues:         list[ValidationIssue] = Field(default_factory=list)
    removed_fields: list[str]             = Field(default_factory=list)
    coerced_fields: list[str]             = Field(default_factory=list)
