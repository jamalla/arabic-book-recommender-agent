"""Milestone 4 - run the fixed test set through the agent and score every answer in Langfuse.

    python -m evals.run_experiment --prompt v1

Each question becomes one trace with the scores invented_books and fit; the whole run gets
avg_fit, grounded_rate and invented_total. Compare runs side by side in Langfuse.
"""
import argparse

from langfuse import get_client

from bookrec.agent import BookAgent
from evals.dataset import sync_dataset
from evals.evaluators import avg_fit, catalog_check, fit_judge, grounded_rate, invented_total


def run(prompt_version="v1", max_concurrency=4):
    langfuse = get_client()
    dataset = sync_dataset(langfuse)
    agent = BookAgent(prompt_version=prompt_version)

    def task(*, item, **kwargs):
        return agent.answer(item.input["question"], tags=["eval", f"prompt-{prompt_version}"])

    result = dataset.run_experiment(
        name=f"prompt-{prompt_version}",
        description=f"Agent {agent.model} with system prompt {prompt_version} on the 12 fixed questions",
        task=task,
        evaluators=[catalog_check, fit_judge],
        run_evaluators=[avg_fit, grounded_rate, invented_total],
        max_concurrency=max_concurrency,
        metadata={"model": agent.model, "prompt": prompt_version},
    )
    langfuse.flush()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the 12-question experiment in Langfuse.")
    parser.add_argument("--prompt", default="v1", help="system prompt version, e.g. v1 or v2")
    args = parser.parse_args()
    print(run(args.prompt).format())
