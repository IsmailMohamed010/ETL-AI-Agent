# prompt_generator.py
"""
prompt_generator.py
-------------------
Generates refined extraction prompts using Ollama (llama3).
"""

import logging

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

OLLAMA_MODEL    = "llama3"
OLLAMA_BASE_URL = "http://localhost:11434"

_META_SYSTEM = """You are a prompt-engineering assistant for a web data extraction system.

Your job: analyze the user's description of what they want to extract from a webpage, and produce a CLEAR, SPECIFIC extraction instruction.

Instructions:
1. Identify every data field the user wants extracted.
2. List each field with a brief description of what to look for.
3. Be specific about format if implied (e.g., currency symbols, date formats).
4. End your instruction with exactly this line: "Return ONLY a flat JSON array. Each object = one item. No extra text."

Output the extraction instruction ONLY — no explanation, no preamble, no markdown formatting."""


def generate_extraction_prompt(user_description: str) -> str:
    """Use Ollama to refine a user's extraction query into a precise prompt."""
    try:
        llm = ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0,
        )
        chain = llm | StrOutputParser()

        result = chain.invoke([
            SystemMessage(content=_META_SYSTEM),
            HumanMessage(content=f"User wants to extract: {user_description}"),
        ])

        if isinstance(result, str) and result.strip():
            logger.info("Ollama refined prompt generated successfully.")
            return result.strip()
        else:
            logger.warning("Ollama returned empty result, falling back to original query.")
            return user_description

    except Exception as exc:
        logger.warning("Ollama prompt generation failed (%s), falling back to original query.", exc)
        return user_description