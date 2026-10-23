"""Which agent the chat app and the experiments use: the Milestone 5 decision, overridable by env vars.

    AGENT_FRAMEWORK = langgraph (default) | openai
    PROMPT_VERSION  = v2 (default) | v1

Evidence (notebooks/05_improve.ipynb, the same 12 questions):
    A  plain loop + prompt v1   avg fit 0.750   invented books 8
    B  plain loop + prompt v2   avg fit 0.917   invented books 0
    C  LangGraph  + prompt v2   avg fit 1.000   invented books 0
"""
import os

DEFAULT_FRAMEWORK = "langgraph"
DEFAULT_PROMPT = "v2"


def agent_settings(framework=None, prompt_version=None):
    """Explicit arguments win, then environment variables, then the measured defaults."""
    return (
        framework or os.getenv("AGENT_FRAMEWORK", DEFAULT_FRAMEWORK),
        prompt_version or os.getenv("PROMPT_VERSION", DEFAULT_PROMPT),
    )


def make_agent(framework=None, prompt_version=None):
    framework, prompt_version = agent_settings(framework, prompt_version)
    if framework == "langgraph":
        from bookrec.agent_langgraph import LangGraphBookAgent  # LangChain is imported only when used
        return LangGraphBookAgent(prompt_version=prompt_version)
    if framework == "openai":
        from bookrec.agent import BookAgent
        return BookAgent(prompt_version=prompt_version)
    raise ValueError(f"Unknown AGENT_FRAMEWORK {framework!r}: use 'langgraph' or 'openai'")
