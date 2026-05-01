"""
app/rag_chain.py
Core RAG pipeline: retrieve relevant context → generate answer with LLM.
"""
 
import logging
from app.retriever import retrieve_and_format
from app.llm import get_llm
 
logger = logging.getLogger(__name__)
 
RAG_PROMPT = """You are a helpful data assistant. Use ONLY the context below to answer the question.
If the context does not contain enough information, say so clearly — do not make up data.
 
Context:
{context}
 
Question: {question}
 
Answer:"""
 
SQL_GEN_PROMPT = """You are a SQL Server expert.
Based on the database schema context below, write a valid T-SQL query to answer the user's question.
Return ONLY the SQL query — no explanation, no markdown fences.
 
Context (table schemas and samples):
{context}
 
Question: {question}
 
SQL Query:"""
 
 
def rag_answer(question: str) -> dict:
    """
    Full RAG pipeline:
      1. Retrieve relevant chunks from vector store
      2. Format context
      3. Generate answer with LLM
 
    Returns:
        {
            "answer": str,
            "sources": list[str],
            "route": "rag"
        }
    """
    context, sources = retrieve_and_format(question)
    llm = get_llm()
    prompt = RAG_PROMPT.format(context=context, question=question)
 
    try:
        response = llm.invoke(prompt)
        if hasattr(response, "content"):
            answer = response.content.strip()
        else:
            answer = str(response).strip()
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        answer = f"Sorry, I could not generate an answer. Error: {e}"
 
    return {"answer": answer, "sources": sources, "route": "rag"}
 
 
def sql_answer(question: str) -> dict:
    """
    SQL generation pipeline:
      1. Retrieve schema/sample context from vector store
      2. Generate a SQL query with LLM
      3. Execute the query against the DB
      4. Return results as a formatted string
 
    Returns:
        {
            "answer": str,
            "sql": str,
            "sources": list[str],
            "route": "sql"
        }
    """
    from app.db import run_sql_query
 
    context, sources = retrieve_and_format(question, k=8)
    llm = get_llm()
    prompt = SQL_GEN_PROMPT.format(context=context, question=question)
 
    try:
        response = llm.invoke(prompt)
        sql = response.content.strip() if hasattr(response, "content") else str(response).strip()
        # Strip markdown fences if LLM adds them anyway
        sql = sql.replace("```sql", "").replace("```", "").strip()
        logger.info(f"Generated SQL: {sql}")
    except Exception as e:
        return {"answer": f"Failed to generate SQL: {e}", "sql": "", "sources": sources, "route": "sql"}
 
    try:
        df = run_sql_query(sql)
        if df.empty:
            answer = "The query returned no results."
        else:
            answer = df.to_string(index=False)
    except Exception as e:
        answer = f"SQL execution failed: {e}\n\nGenerated query:\n{sql}"
 
    return {"answer": answer, "sql": sql, "sources": sources, "route": "sql"}