"""
domain_detector.py
------------------
Detect domain type from extracted rows.
Two-stage approach:
  1. Fast keyword heuristic (no LLM call)
  2. LLM fallback if heuristic is not confident
"""

from __future__ import annotations
import json
import logging
import re
import requests

from schema_models import DomainType
from schema_prompts import DOMAIN_DETECTION_PROMPT

logger = logging.getLogger(__name__)

OLLAMA_URL  = "http://localhost:11434/api/chat"
MODEL_ID    = "qwen2.5:7b-instruct"

# ── Heuristic keyword maps ─────────────────────────────────────────────────────

_KEYWORDS: dict[DomainType, list[str]] = {
    DomainType.FOOTBALL:     ["goal", "match", "player", "team", "league", "score",
                               "fixture", "assist", "club", "stadium", "kick", "halftime"],
    DomainType.ECOMMERCE:    ["price", "product", "cart", "sku", "discount", "stock",
                               "brand", "category", "review", "rating", "purchase", "order"],
    DomainType.REAL_ESTATE:  ["bedroom", "bathroom", "sqft", "property", "listing",
                               "rent", "mortgage", "realtor", "address", "lot", "garage"],
    DomainType.NEWS:         ["headline", "article", "author", "published", "source",
                               "journalist", "breaking", "reporter", "editor", "byline"],
    DomainType.LOGS:         ["timestamp", "level", "error", "warning", "exception",
                               "trace", "stacktrace", "service", "request", "response", "latency"],
    DomainType.JOBS:         ["salary", "job", "position", "employer", "company",
                               "remote", "skills", "experience", "requirement", "vacancy"],
    DomainType.FINANCE:      ["stock", "ticker", "dividend", "portfolio", "asset",
                               "revenue", "profit", "eps", "market_cap", "yield"],
    DomainType.HEALTHCARE:   ["patient", "diagnosis", "medication", "hospital", "doctor",
                               "symptom", "treatment", "prescription", "icd", "clinical"],
    DomainType.SOCIAL_MEDIA: ["likes", "followers", "tweet", "post", "comment", "share",
                               "hashtag", "mention", "retweet", "story", "reel"],
}

_URL_PATTERNS: dict[DomainType, list[str]] = {
    DomainType.FOOTBALL:     ["football", "soccer", "transfermarkt", "sofascore", "fbref",
                               "whoscored", "espn", "bbc/sport"],
    DomainType.ECOMMERCE:    ["amazon", "ebay", "shop", "store", "product", "aliexpress"],
    DomainType.REAL_ESTATE:  ["zillow", "realtor", "redfin", "trulia", "property"],
    DomainType.NEWS:         ["news", "reuters", "bbc", "cnn", "nytimes", "guardian"],
    DomainType.JOBS:         ["linkedin", "indeed", "glassdoor", "jobs", "career"],
    DomainType.FINANCE:      ["finance", "bloomberg", "nasdaq", "nyse", "investing"],
}


def _field_tokens(rows: list[dict]) -> set[str]:
    """Extract lowercase word tokens from all field names."""
    tokens = set()
    for row in rows:
        for key in row.keys():
            for word in re.split(r"[_.\- ]+", key.lower()):
                if word:
                    tokens.add(word)
    return tokens


def _heuristic_detect(rows: list[dict], url: str = "") -> tuple[DomainType, float]:
    """
    Return (domain, confidence) using keyword matching.
    confidence is ratio of matched keywords to total domain keywords.
    """
    tokens = _field_tokens(rows)
    url_lower = url.lower()

    scores: dict[DomainType, float] = {}

    for domain, keywords in _KEYWORDS.items():
        matched = sum(1 for kw in keywords if kw in tokens)
        scores[domain] = matched / len(keywords)

    # URL bonus
    for domain, patterns in _URL_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            scores[domain] = scores.get(domain, 0.0) + 0.3

    best_domain  = max(scores, key=scores.get)
    best_score   = min(scores[best_domain], 1.0)

    if best_score < 0.05:
        return DomainType.UNKNOWN, 0.0

    return best_domain, round(best_score, 2)


def _llm_detect(rows: list[dict], url: str = "") -> DomainType:
    """Fallback: ask the LLM to detect the domain."""
    field_names  = list(rows[0].keys()) if rows else []
    sample_row   = {k: rows[0][k] for k in field_names[:10]} if rows else {}
    prompt       = DOMAIN_DETECTION_PROMPT.format(
        field_names = field_names,
        sample_row  = json.dumps(sample_row, ensure_ascii=False),
        source_url  = url,
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model":    MODEL_ID,
                "messages": [{"role": "user", "content": prompt}],
                "stream":   False,
                "options":  {"temperature": 0, "num_predict": 20},
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip().lower()
        for domain in DomainType:
            if domain.value in raw:
                return domain
    except Exception as exc:
        logger.warning("LLM domain detection failed: %s", exc)
    return DomainType.UNKNOWN


def detect_domain(
    rows: list[dict],
    url:  str = "",
    llm_threshold: float = 0.15,
) -> DomainType:
    """
    Public API.
    If heuristic confidence >= llm_threshold → use heuristic result.
    Otherwise → call LLM.
    """
    domain, confidence = _heuristic_detect(rows, url)
    logger.info("Heuristic domain: %s (confidence=%.2f)", domain.value, confidence)

    if confidence >= llm_threshold:
        return domain

    logger.info("Low confidence — using LLM fallback for domain detection.")
    llm_domain = _llm_detect(rows, url)
    logger.info("LLM domain: %s", llm_domain.value)
    return llm_domain
