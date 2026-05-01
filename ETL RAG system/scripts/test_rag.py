"""
scripts/test_rag.py
Interactive CLI to test the RAG system.
Usage: python -m scripts.test_rag
"""
 
import logging
logging.basicConfig(level=logging.WARNING)
 
from app.agent import initialize, query
 
TEST_QUESTIONS = [
    "What data do we have?",
    "Give me a summary of the available information.",
    "How many records are there?",
]
 
if __name__ == "__main__":
    initialize()
 
    print(f"\n{'='*60}")
    print("RAG System — Interactive Test")
    print("Type your question or press Ctrl+C to exit.")
    print(f"{'='*60}\n")
 
    # Run default test questions first
    print("Running default test questions...\n")
    for q in TEST_QUESTIONS:
        print(f"Q: {q}")
        result = query(q)
        print(f"Route: {result.get('route', 'N/A')}")
        print(f"A: {result.get('answer', 'No answer')}")
        print(f"{'-'*40}")
 
    # Interactive loop
    print("\nEntering interactive mode...\n")
    while True:
        try:
            question = input("Your question: ").strip()
            if not question:
                continue
            result = query(question)
            print(f"\nRoute : {result.get('route', 'N/A')}")
            print(f"Answer: {result.get('answer')}")
            if result.get("sources"):
                print(f"Sources: {result.get('sources')}")
            print()
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
 