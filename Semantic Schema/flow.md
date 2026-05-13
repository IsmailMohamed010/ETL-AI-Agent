parsed_rows (list[dict])
        │
        ▼
┌─────────────────────────────┐
│   node_semantic_schema      │
│                             │
│  1. detect_domain()         │  → heuristic keywords + URL patterns
│     └─ LLM fallback         │    (calls Ollama only if confidence < threshold)
│                             │
│  2. generate_schema()       │  → infer types locally + LLM for entity structure
│                             │
│  3. validate_schema()       │  → remove hallucinated fields not in actual data
│                             │
│  4. validate_rows()         │  → coerce types, handle nulls
│     + normalize_rows()      │  → rename to canonical_name, add _schema_domain
└─────────────────────────────┘
        │
        ▼
normalized_rows  +  semantic_schema (JSONB)  +  schema_validation