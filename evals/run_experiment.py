"""Milestone 4 - run the fixed test set through the agent and score every answer in Langfuse.
Milestone 5 - pick the agent (framework + prompt); defaults come from bookrec.factory.

    python -m evals.run_experiment                          # the shipped agent: LangGraph + prompt v2
    python -m evals.run_experiment --agent openai --prompt v1

Each question becomes one trace with the scores invented_books and fit; the whole run gets
avg_fit, grounded_rate and invented_total. Compare runs side by side in Langfuse.
"""
import argparse

from langfuse import get_client

from bookrec.factory import agent_settings, make_agent
from evals.dataset import sync_dataset
from evals.evaluators import avg_fit, catalog_check, fit_judge, grounded_rate, invented_total


def run(prompt_version=None, framework=None, max_concurrency=4):
    framework, prompt_version = agent_settings(framework, prompt_version)
    langfuse = get_client()
    dataset = sync_dataset(langfuse)
    agent = make_agent(framework, prompt_version)

    def task(*, item, **kwargs):
        return agent.answer(item.input["question"], tags=["eval", f"prompt-{prompt_version}", framework])

    result = dataset.run_experiment(
        name=f"{framework}-prompt-{prompt_version}",
        description=f"{framework} agent ({agent.model}) with system prompt {prompt_version} on the 12 fixed questions",
        task=task,
        evaluators=[catalog_check, fit_judge],
        run_evaluators=[avg_fit, grounded_rate, invented_total],
        max_concurrency=max_concurrency,
        metadata={"model": agent.model, "prompt": prompt_version, "framework": framework},
    )
    langfuse.flush()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the 12-question experiment in Langfuse.")
    parser.add_argument("--prompt", help="system prompt version: v1 or v2 (default: PROMPT_VERSION or v2)")
    parser.add_argument("--agent", choices=["openai", "langgraph"], help="agent framework (default: AGENT_FRAMEWORK or langgraph)")
    args = parser.parse_args()
    print(run(args.prompt, args.agent).format())
