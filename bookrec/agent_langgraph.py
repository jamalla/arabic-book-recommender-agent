"""Milestone 5 - the same agent built on LangGraph (LangChain's create_agent), to compare frameworks.

Same tool, same prompts and the same answer() interface as bookrec.agent.BookAgent, so the SAME
experiment scores both:

    python -m evals.run_experiment --agent langgraph --prompt v2
"""
import json
import os

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langfuse import get_client, propagate_attributes
from langfuse.langchain import CallbackHandler

from bookrec.agent import DEFAULT_MODEL, MAX_TOOL_ROUNDS, PROMPTS
from bookrec.search import BookSearch


class LangGraphBookAgent:
    """Drop-in replacement for BookAgent, built on LangGraph's prebuilt tool-calling agent."""

    def __init__(self, prompt_version="v1", model=None, search=None):
        self.prompt_version = prompt_version
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        engine = search or BookSearch()

        @tool
        def search_books(query: str) -> str:
            """Search the bookstore catalog (200 Arabic books). Returns up to 5 books, best first, each
            with book_id, title, author, category, year, a short description and a 0-1 relevance score.
            query: what the reader is looking for, in Arabic: topic, genre, title or author."""
            return json.dumps(engine.search(query, k=5), ensure_ascii=False)

        self.graph = create_agent(
            model=ChatOpenAI(model=self.model, use_responses_api=True),
            tools=[search_books],
            system_prompt=PROMPTS[prompt_version],
        )

    def answer(self, question, history=None, session_id=None, tags=None):
        """Same contract as BookAgent.answer: returns the answer, every search, and the trace id."""
        langfuse = get_client()
        metadata = {"model": self.model, "prompt": self.prompt_version, "framework": "langgraph"}
        attributes = {"tags": tags or [], "metadata": metadata}
        if session_id:
            attributes["session_id"] = session_id
        with langfuse.start_as_current_observation(
            as_type="agent", name="book-agent-langgraph", input={"question": question, "history": history or []}
        ) as agent_span:
            with propagate_attributes(**attributes):
                state = self.graph.invoke(
                    {"messages": list(history or []) + [{"role": "user", "content": question}]},
                    # Langfuse traces every graph step; each tool round is 2 steps (model + tool).
                    config={"callbacks": [CallbackHandler()], "recursion_limit": 2 * MAX_TOOL_ROUNDS + 2},
                )
            result = {"answer": state["messages"][-1].text, "steps": _steps(state["messages"])}
            result["trace_id"] = langfuse.get_current_trace_id()
            agent_span.update(output=result["answer"])
        return result


def _steps(messages):
    """Rebuild [{"query": ..., "books": [...]}] from the graph's messages (same shape as BookAgent)."""
    queries = {call["id"]: call["args"].get("query", "") for m in messages for call in getattr(m, "tool_calls", None) or []}
    return [
        {"query": queries.get(m.tool_call_id, ""), "books": json.loads(m.content)}
        for m in messages if m.type == "tool"
    ]
