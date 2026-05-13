"""
schema_prompts.py
-----------------
Prompt templates for domain detection and semantic schema generation.
"""

from __future__ import annotations

DOMAIN_DETECTION_PROMPT = """\
You are a data classification expert.

Given a list of field names and sample values from a scraped dataset, \
identify the domain/industry this data belongs to.

Choose EXACTLY ONE from this list:
  football-analysis | e-commerce | real-estate | news | logs | \
  jobs | finance | healthcare | social-media | unknown

Return ONLY the domain string. No explanation. No punctuation.

Field names: {field_names}
Sample values (first row): {sample_row}
Source URL: {source_url}
"""


SCHEMA_GENERATION_PROMPT = """\
You are a semantic data modeling expert.

Analyze the following field names, sample data rows, and domain type, \
then produce a semantic schema as a JSON object.

DOMAIN: {domain}
FIELD NAMES: {field_names}
SAMPLE ROWS (up to 3):
{sample_rows}

Return a JSON object with this EXACT structure (no markdown, no explanation):
{{
  "entities": [
    {{
      "name": "<EntityName>",
      "description": "<short description>",
      "primary_key": "<field_name or null>",
      "attributes": [
        {{
          "name": "<original_field_name>",
          "canonical_name": "<snake_case_normalized_name>",
          "inferred_type": "<string|integer|float|boolean|date|datetime|url|email|currency|percentage|array|object|null|unknown>",
          "description": "<what this field represents>",
          "nullable": true,
          "example_value": <example from data>
        }}
      ]
    }}
  ],
  "relationships": [
    {{
      "from_entity": "<EntityName>",
      "to_entity": "<EntityName>",
      "via_attribute": "<field_name>",
      "cardinality": "1:1 | 1:N | N:M",
      "description": "<optional>"
    }}
  ],
  "confidence": <0.0 to 1.0>,
  "notes": "<any important observations>"
}}

RULES:
- Only include fields that ACTUALLY EXIST in the field names list.
- Do NOT invent fields.
- Use snake_case for canonical_name.
- Group related fields into a single entity.
- If only one entity makes sense, use one.
- relationships list can be empty [] if there is only one entity.
"""
