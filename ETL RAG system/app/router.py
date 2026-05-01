"""
app/router.py
Routes user queries to the appropriate handler:
  - "rag"     → answer from vector store (default)
  - "sql"     → generate and run a SQL query
  - "general" → general question, no data needed
"""

import logging
from app.llm import get_llm
from app.metadata import all_tables_summary_text

logger = logging.getLogger(__name__)

ROUTER_PROMPT = """You are a query routing assistant for a data system.
Given the user's question and the available database tables below, decide the best route:

Routes:
- "sql"     : The user wants specific numbers, counts, filters, or aggregations that need a live SQL query.
- "rag"     : The user wants to understand the data, search for information, or ask descriptive questions.
- "general" : The question is unrelated to the database (greetings, general knowledge, etc.).

Available database tables:
{db_summary}

User question: {question}

Reply with ONLY one word: sql, rag, or general."""


def route_query(question: str) -> str:
    try:
        db_summary = all_tables_summary_text()
        llm = get_llm()
        prompt = ROUTER_PROMPT.format(db_summary=db_summary, question=question)
        response = llm.invoke(prompt)

        if hasattr(response, "content"):
            route = response.content.strip().lower()
        else:
            route = str(response).strip().lower()

        if route not in ("sql", "rag", "general"):
            logger.warning(f"Unexpected route '{route}', defaulting to 'rag'.")
            route = "rag"

        logger.info(f"Query routed to: '{route}'")
        return route

    except Exception as e:
        logger.warning(f"Router failed: {e}. Defaulting to 'rag'.")
        return "rag"