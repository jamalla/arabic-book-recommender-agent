"""Milestone 3 - the agent: an OpenAI model that uses our search engine as a TOOL.
Milestone 4 - every answer is traced in Langfuse, for eval runs and real chat users alike.

The model never reads catalog.csv. It asks search_books() for candidates and writes the
Arabic answer from what the tool returns. Tool-calling loop as in OpenAI's guide:
https://developers.openai.com/api/docs/guides/function-calling

    python -m bookrec.agent "أريد رواية تاريخية"
"""
import json
import os
import sys

from dotenv import load_dotenv
from langfuse import get_client, propagate_attributes
from openai import OpenAI

from bookrec.search import BookSearch

load_dotenv()  # OPENAI_API_KEY, LANGFUSE_* keys and the optional OPENAI_MODEL from .env
os.environ.setdefault("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")  # Langfuse EU region

DEFAULT_MODEL = "gpt-6-luna"  # cheap, fast, supports function calling
MAX_TOOL_ROUNDS = 3           # safety net: the loop can never run forever

# Prompt v1: an honest first draft. Milestone 4 measures it, Milestone 5 improves it.
SYSTEM_PROMPT_V1 = """You are a friendly bookstore assistant for Arabic readers.
Use the search_books tool to look up books in our catalog, then recommend books that match
the reader's request, with one short sentence on why each one fits.
Always answer in Arabic."""

PROMPTS = {"v1": SYSTEM_PROMPT_V1}

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


def _plain(items):
    """OpenAI SDK objects -> plain dicts, so Langfuse can display them."""
    return [item if isinstance(item, dict) else item.model_dump(exclude_none=True) for item in items]


class BookAgent:
    """Chat turns in, Arabic answers out. Every model call and tool call is traced in Langfuse."""

    def __init__(self, prompt_version="v1", model=None, search=None, client=None):
        self.prompt_version = prompt_version
        self.system_prompt = PROMPTS[prompt_version]
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self.search = search or BookSearch()
        self.client = client or OpenAI()

    def search_books(self, query):
        with get_client().start_as_current_observation(
            as_type="tool", name="search_books", input={"query": query}
        ) as tool:
            books = self.search.search(query, k=5)
            tool.update(output=books)
        return books

    def _ask_model(self, conversation, tool_choice="auto"):
        with get_client().start_as_current_observation(
            as_type="generation",
            name="llm",
            model=self.model,
            input=[{"role": "system", "content": self.system_prompt}, *_plain(conversation)],
        ) as generation:
            response = self.client.responses.create(
                model=self.model,
                instructions=self.system_prompt,
                tools=[SEARCH_TOOL],
                tool_choice=tool_choice,
                input=conversation,
            )
            generation.update(
                output=_plain(response.output),
                usage_details={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )
        return response

    def answer(self, question, history=None, session_id=None, tags=None):
        """Answer one chat turn.

        history: earlier turns of the same chat, as [{"role": "user" | "assistant", "content": str}].
        session_id groups the turns of one chat in Langfuse; tags mark eval vs production runs.
        Returns the answer, every search the model made, and the Langfuse trace id (for scores).
        """
        langfuse = get_client()
        attributes = {"tags": tags or [], "metadata": {"model": self.model, "prompt": self.prompt_version}}
        if session_id:
            attributes["session_id"] = session_id
        with langfuse.start_as_current_observation(
            as_type="agent", name="book-agent", input={"question": question, "history": history or []}
        ) as agent_span:
            with propagate_attributes(**attributes):
                conversation = list(history or []) + [{"role": "user", "content": question}]
                result = self._run(conversation)
            result["trace_id"] = langfuse.get_current_trace_id()
            agent_span.update(output=result["answer"])
        return result

    def _run(self, conversation):
        """The tool-calling loop. Returns the answer plus [{"query": ..., "books": [...]}] per search."""
        steps = []
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
    result = BookAgent().answer(question, tags=["cli"])
    for step in result["steps"]:
        print("search_books:", step["query"], "->", [book["book_id"] for book in step["books"]])
    print(result["answer"])
    get_client().flush()  # short-lived script: send the trace before exiting
