import os
from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults
from typing import TypedDict
from langgraph.prebuilt import ToolNode
import ollama
from langchain_ollama import OllamaLLM

load_dotenv()

#api_key = os.getenv("TAVILY_API_KEY")
#tavily_search = TavilySearchResults(api_key=api_key, num_results=1)

#tools = [tavily_search]
#tool_executor = ToolNode(tools)

llm = OllamaLLM(model="gemma3:1b", temperature=0, stream=True)
print("Hello World!")

