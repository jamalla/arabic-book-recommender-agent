"""Milestone 3 - the agent: an OpenAI model that uses our search engine as a TOOL.

The model never reads catalog.csv. It asks search_books() for candidates and writes the
Arabic answer from what the tool returns. Tool-calling loop as in OpenAI's guide:
https://developers.openai.com/api/docs/guides/function-calling

    python -m bookrec.agent "أريد رواية تاريخية"
"""
import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from bookrec.search import BookSearch

load_dotenv()  # reads OPENAI_API_KEY (and the optional OPENAI_MODEL) from .env

DEFAULT_MODEL = "gpt-6-luna"  # cheap, fast, supports function calling
MAX_TOOL_ROUNDS = 3           # safety net: the loop can never run forever

# Prompt v1: an honest first draft. Milestone 4 measures it, Milestone 5 improves it.
SYSTEM_PROMPT_V1 = """You are a friendly bookstore assistant for Arabic readers.
Use the search_books tool to look up books in our catalog, then recommend books that match
the reader's request, with one short sentence on why each one fits.
Always answer in Arabic."""

SEARCH_TOOL = {
    "type": "function",
    "name": "search_books",
    "description": (
        "Search the bookstore catalog (200 Arabic books). Returns up to 5 books, best first, "
        "each with book_id, title, author, category, year, a short description and a 0-1 "
        "relevance score."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What the reader is looking for, in Arabic: topic, genre, title or author.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "strict": True,
}


class BookAgent:
    """One question in, one Arabic answer out, with every tool call recorded."""

    def __init__(self, system_prompt=SYSTEM_PROMPT_V1, model=None, search=None, client=None):
        self.system_prompt = system_prompt
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self.search = search or BookSearch()
        self.client = client or OpenAI()

    def search_books(self, query):
        return self.search.search(query, k=5)

    def _ask_model(self, conversation, tool_choice="auto"):
        return self.client.responses.create(
            model=self.model,
            instructions=self.system_prompt,
            tools=[SEARCH_TOOL],
            tool_choice=tool_choice,
            input=conversation,
        )

    def answer(self, question):
        """Run the tool-calling loop. Returns the answer plus every search the model made."""
        conversation = [{"role": "user", "content": question}]
        steps = []  # [{"query": ..., "books": [...]}] - what the model asked for and got back
        for _ in range(MAX_TOOL_ROUNDS):
            response = self._ask_model(conversation)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return {"answer": response.output_text, "steps": steps}
            conversation += response.output  # keep the model's calls (and reasoning) in context
            for call in calls:
                query = json.loads(call.arguments)["query"]
                books = self.search_books(query)
                steps.append({"query": query, "books": books})
                conversation.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(books, ensure_ascii=False),
                })
        # Still calling tools after MAX_TOOL_ROUNDS: force a final written answer.
        response = self._ask_model(conversation, tool_choice="none")
        return {"answer": response.output_text, "steps": steps}


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "أريد رواية تاريخية"
    result = BookAgent().answer(question)
    for step in result["steps"]:
        print("search_books:", step["query"], "->", [book["book_id"] for book in step["books"]])
    print(result["answer"])
