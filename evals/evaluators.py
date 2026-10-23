"""Milestone 4 - two ways to score an answer.

1. catalog_check (CODE): does every recommended book really exist in catalog.csv?
   An LLM only copies the titles out of the Arabic answer; the verdict is plain code.
2. fit_judge (LLM-as-a-judge): do the recommended books fit the reader's request?
   A stronger model (gpt-6.1-sol) grades the agent (gpt-6-luna).

Plus run-level scores for the whole experiment: avg_fit, grounded_rate, invented_total.
"""
import json
import os
from functools import cache

import pandas as pd
from langfuse import Evaluation
from openai import OpenAI

from bookrec.search import CATALOG_PATH, normalize_arabic

EXTRACT_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-6.1-sol")


@cache
def _openai():
    return OpenAI()


@cache
def _catalog_titles():
    return [normalize_arabic(title) for title in pd.read_csv(CATALOG_PATH)["title"]]


def _ask_json(model, instructions, text, schema_name, schema):
    """One Responses API call whose output must be JSON matching the schema."""
    response = _openai().responses.create(
        model=model,
        instructions=instructions,
        input=text,
        text={"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
    )
    return json.loads(response.output_text)


# ---------- 1. CODE check: are the recommended books real? ----------

TITLES_SCHEMA = {
    "type": "object",
    "properties": {"titles": {"type": "array", "items": {"type": "string"}}},
    "required": ["titles"],
    "additionalProperties": False,
}


def recommended_titles(answer):
    """Copy out the titles the answer RECOMMENDS (not the ones it says are unavailable)."""
    data = _ask_json(
        EXTRACT_MODEL,
        "Copy, exactly as written, the titles of the books this Arabic bookstore answer "
        "recommends to the reader. Leave out books the answer says are not available. "
        "Return an empty list if it recommends none.",
        answer, "recommended_titles", TITLES_SCHEMA,
    )
    return data["titles"]


def in_catalog(title):
    key = normalize_arabic(title).strip(' "«»*:.-')
    return bool(key) and any(key == c or key in c or c in key for c in _catalog_titles())


def catalog_check(*, output, **kwargs):
    """invented_books = recommended titles that are NOT in catalog.csv (0 is the only good value)."""
    titles = recommended_titles(output["answer"])
    invented = [t for t in titles if not in_catalog(t)]
    return Evaluation(
        name="invented_books",
        value=len(invented),
        comment=f"{len(titles)} recommended; not in the catalog: {invented}",
    )


# ---------- 2. LLM judge: do the books fit the request? ----------

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "number"}, "reason": {"type": "string"}},
    "required": ["score", "reason"],
    "additionalProperties": False,
}

JUDGE_INSTRUCTIONS = """You grade an Arabic bookstore assistant that may only recommend books from its catalog.
Give a score from 0 to 1 for how well the RECOMMENDED books fit the reader's request:
1.0 = every recommended book clearly fits, or nothing in the catalog fits and the answer says so honestly.
0.5 = a mix of fitting books and weak or unrelated ones (padding the list).
0.0 = the books do not fit, or the answer recommends books that are not in the catalog.
Base your judgement on the catalog books the search returned (title, author, category, description).
Give the reason in one short English sentence."""


def fit_judge(*, input, output, expected_output, **kwargs):
    """LLM-as-a-judge: fit score 0..1 with a one-sentence reason."""
    returned = {book["book_id"]: book for step in output["steps"] for book in step["books"]}
    case = {
        "reader_request": input["question"],
        "what_a_good_answer_does": expected_output,
        "assistant_answer": output["answer"],
        "catalog_books_the_search_returned": [
            {key: book[key] for key in ("title", "author", "category", "description")}
            for book in returned.values()
        ],
    }
    verdict = _ask_json(JUDGE_MODEL, JUDGE_INSTRUCTIONS, json.dumps(case, ensure_ascii=False),
                        "fit_verdict", JUDGE_SCHEMA)
    score = max(0.0, min(1.0, float(verdict["score"])))
    return Evaluation(name="fit", value=score, comment=verdict["reason"])


# ---------- run-level scores: one number per experiment ----------

def _values(item_results, name):
    return [e.value for r in item_results for e in r.evaluations if e.name == name and e.value is not None]


def avg_fit(*, item_results, **kwargs):
    fits = _values(item_results, "fit")
    return Evaluation(name="avg_fit", value=round(sum(fits) / len(fits), 3) if fits else None)


def grounded_rate(*, item_results, **kwargs):
    invented = _values(item_results, "invented_books")
    value = round(sum(v == 0 for v in invented) / len(invented), 3) if invented else None
    return Evaluation(name="grounded_rate", value=value, comment="share of answers with 0 invented books")


def invented_total(*, item_results, **kwargs):
    return Evaluation(name="invented_total", value=sum(_values(item_results, "invented_books")))
