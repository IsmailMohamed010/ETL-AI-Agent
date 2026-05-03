# extractor_llm.py
"""
extractor_llm.py
----------------
Converts raw page text → structured JSON using Ollama (local LLM).
No model downloads required — uses whatever model is already running in Ollama.
"""

import json
import logging
import re

import requests

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_URL      = "http://localhost:11434/api/chat"
MODEL_ID        = "qwen2.5:7b-instruct"   # change to any model you have: ollama list
CHUNK_SIZE    = 3000   # ~25-30 jobs per chunk instead of 100
CHUNK_OVERLAP = 300
MAX_NEW_TOKENS = 2048   # more overlap to help with context loss at chunk boundaries


def _build_system_prompt(search_query: str) -> str:
    return (
        "You are a precise data-extraction assistant.\n"
        f"Extract ONLY: {search_query}\n\n"
        "STRICT OUTPUT RULES — follow every rule exactly:\n"
        "1. Return a JSON ARRAY of objects. Each object = one item.\n"
        "2. Every object MUST be FLAT — all fields at the top level.\n"
        "3. ALWAYS use these exact field names — never invent new ones:\n"
        "   Use the simplest snake_case name for each concept.\n"
        "   Example: country name → 'country', population → 'population'\n"
        "   Do NOT use long names like 'Population (1 July 2023)' or 'Country or territory'.\n"
        "4. Extract ONLY information that literally appears in the TEXT below.\n"
        "   Do NOT invent, guess, or fill in missing fields.\n"
        "5. If a field is not present for an item, set it to null.\n"
        "6. Do NOT repeat the same item more than once.\n"
        "7. Extract ALL items present. Do not stop early.\n"
        "8. No markdown, no code fences, no explanation — raw JSON array only.\n"
        "9. The JSON MUST be complete and valid — close every bracket.\n"   
    )


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start  = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            newline_pos = text.rfind("\n", start, end)
            if newline_pos > start + chunk_size // 2:
                end = newline_pos
        chunks.append(text[start:end])
        start = end - overlap
    logger.info("Split text (%d chars) into %d chunks.", len(text), len(chunks))
    return chunks


def _repair_truncated_json(text: str) -> str:
    last_close = max(text.rfind("}"), text.rfind("]"))
    if last_close == -1:
        return text
    text = text[: last_close + 1]
    depth_curly  = text.count("{") - text.count("}")
    depth_square = text.count("[") - text.count("]")
    text += "}" * max(depth_curly,  0)
    text += "]" * max(depth_square, 0)
    return text


def _parse_json_output(raw: str) -> list:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    def _try_parse(s: str):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None

    result = _try_parse(cleaned)
    if result is not None:
        return _to_list(result)

    for pattern in [r"(\[[\s\S]*\])", r"(\{[\s\S]*\})"]:
        match = re.search(pattern, cleaned)
        if match:
            result = _try_parse(match.group(1))
            if result is not None:
                return _to_list(result)
            repaired = _repair_truncated_json(match.group(1))
            result   = _try_parse(repaired)
            if result is not None:
                logger.info("Recovered partial JSON after truncation repair.")
                return _to_list(result)

    repaired = _repair_truncated_json(cleaned)
    result   = _try_parse(repaired)
    if result is not None:
        return _to_list(result)

    logger.warning("JSON parse failed for chunk. Raw (first 300): %s", raw[:300])
    return []


def _to_list(data) -> list:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        list_values = {k: v for k, v in data.items() if isinstance(v, list)}
        if list_values:
            keys    = list(list_values.keys())
            arrays  = [list_values[k] for k in keys]
            max_len = max(len(a) for a in arrays)
            merged  = []
            for i in range(max_len):
                row = {}
                for k, arr in zip(keys, arrays):
                    if i < len(arr):
                        item = arr[i]
                        if isinstance(item, dict):
                            row.update(item)
                        else:
                            row[k] = item
                merged.append(row)
            return merged
        return [data]
    return []


def _extract_chunk(chunk: str, search_query: str) -> list:
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": _build_system_prompt(search_query)},
            {"role": "user",   "content": f"TEXT TO EXTRACT FROM:\n{chunk}"},
        ],
        "stream": False,
        "options": {
            "num_predict": MAX_NEW_TOKENS,  # output token limit
            "num_ctx":     12000,           # context window: chunk + system prompt
            "temperature": 0,
        },
    }
    try:
        # In _extract_chunk:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=1200)  # 20 mi
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()
    except requests.RequestException as e:
        logger.error("Ollama request failed: %s", e)
        return []

    logger.debug("Chunk raw output (first 400 chars): %s", raw[:400])
    return _parse_json_output(raw)


def _dedup_rows(rows: list[dict]) -> list[dict]:
    seen  : set  = set()
    clean : list = []
    for row in rows:
        key = tuple(sorted((k, str(v)) for k, v in row.items()))
        if key not in seen:
            seen.add(key)
            clean.append(row)
    return clean


def extract_to_json(text: str, search_query: str) -> list:
    chunks   = _chunk_text(text)
    all_rows : list[dict] = []
    for i, chunk in enumerate(chunks, 1):
        logger.info("Processing chunk %d / %d  (%d chars)...", i, len(chunks), len(chunk))
        rows = _extract_chunk(chunk, search_query)
        logger.info("  → extracted %d items from chunk %d", len(rows), i)
        all_rows.extend(rows)
    all_rows = _dedup_rows(all_rows)
    logger.info("Total unique items after merging all chunks: %d", len(all_rows))
    return all_rows


def extract_from_text(raw_content: str, search_query: str) -> list:
    """Single-page extraction entry point called by the node."""
    logger.info("Extracting with query: '%s'", search_query)
    return extract_to_json(raw_content, search_query)