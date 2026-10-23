# Arabic Book Recommender Agent 📚🤖

An Arabic chat assistant that recommends **only real books from a catalog**, proves with
measurements that it improves, and runs online.

> **Key lesson:** treat an AI agent like software. Test it, measure it, improve it, and keep
> watching it after launch.

## How it works

```text
Reader ──question──▶ Web app ──▶ Agent (OpenAI LLM) ──tool call──▶ search_books() ──▶ Catalog
                                   │                               char TF-IDF        200 real books
                                   └──traces──▶ Langfuse (prompts, tool calls, answers, scores)
```

## Roadmap

Every milestone is committed separately, so you can check out any step and see the project as it was then.

| # | Milestone | Purpose | Status |
|---|-----------|---------|--------|
| 0 | Project skeleton | Separate code, secrets and data from day one | ✅ |
| 1 | Prepare the data | A trustworthy 200-book catalog from the Jamalon dataset | ✅ |
| 2 | Search engine | Char-level TF-IDF that tolerates Arabic spelling variations | ✅ |
| 3 | Agent | An LLM that calls the search tool and answers in Arabic | ✅ |
| 4 | Evaluate with Langfuse | Traces, 12 fixed test questions, code check + LLM judge | ⏳ |
| 5 | Improve the prompt | Change one thing, re-test, keep it only if it wins | ⏳ |
| 6 | Deploy on AWS | Container on ECS Express Mode with HTTPS and secure keys | ⏳ |
| 7 | Document and clean up | README, evaluation article, delete cloud resources | ⏳ |

## Data

The catalog comes from the public
[Jamalon Arabic Books Dataset](https://www.kaggle.com/datasets/dareenalharthi/jamalon-arabic-books-dataset)
(books scraped from the Jamalon online bookstore). It was explored step by step in
[notebooks/01_data_exploration.ipynb](notebooks/01_data_exploration.ipynb).

| Step | Books |
|------|------:|
| Raw dataset | 8,986 |
| Has a real description (not empty, not "None") | 4,443 |
| Description of 100+ characters, duplicates removed | 3,979 |
| Known author, 10 chosen categories, balanced sample of 20 each (seed 42) | **200** |

`python -m bookrec.prepare_data` downloads the dataset and rebuilds
[data/catalog.csv](data/catalog.csv). Current fingerprint: `3d092a3bb7`.

The first version (`20958bc305`, identical on Kaggle and on a local machine) still contained
scraping leftovers such as the literal text `u200e` in some titles. The search demo in
Milestone 2 exposed them, `clean_text()` now removes them, and the catalog was rebuilt.

## Search engine

[bookrec/search.py](bookrec/search.py) joins each book's title, author, category, subcategory and
description, normalizes Arabic spelling, and indexes **character n-grams (2 to 4 letters)** with
TF-IDF. A request is normalized the same way and ranked by cosine similarity (0 to 1).

```bash
python -m bookrec.search "روايات عن الحب"
```

| Normalization | Example |
|---|---|
| أ إ آ → ا and ة → ه | «الإسلامية» → «الاسلاميه» |
| ى → ي | «مستشفى» → «مستشفي» |
| remove tashkeel | «القُرْآن» → «القران» |

Why characters, not words? «رواية» and «روايات» share 9 n-grams, and «لتربية» still matches «تربية».
[notebooks/02_search_engine.ipynb](notebooks/02_search_engine.ipynb) compares both approaches and shows
the key limitation: search **always** returns k books, even for «هاري بوتر» (Harry Potter), which is
not in the catalog (scores around 0.1). Deciding that nothing fits is the agent's job, and the trap
questions in Milestone 4 test exactly that.

## Agent

[bookrec/agent.py](bookrec/agent.py) gives an OpenAI model one tool, `search_books(query)`, and runs
the tool-calling loop from OpenAI's
[function calling guide](https://developers.openai.com/api/docs/guides/function-calling)
(Responses API, at most 3 rounds). The model never reads the catalog file: it only sees the books the
tool returns, and writes the Arabic answer from them.

```bash
python -m bookrec.agent "أريد رواية تاريخية"
```

| Setting | Value |
|---|---|
| Agent model | `gpt-6-luna` ($0.10 / $0.50 per 1M input / output tokens) |
| Tool | `search_books(query)` returns the top 5 books with a 0-1 score (strict JSON schema) |
| Prompt | v1, an honest first draft (`SYSTEM_PROMPT_V1`) |

First live run in [notebooks/03_agent.ipynb](notebooks/03_agent.ipynb): three of four questions went
well, including the Harry Potter trap ("not in our catalog"). But asked for Naguib Mahfouz novels, the
agent searched, found none, and then recommended five famous Mahfouz novels **from memory**. A simple
code check counted 5 of 9 recommended titles that are not in the catalog. Milestone 4 turns this into a
fixed, repeatable evaluation.

## Project layout (filled in milestone by milestone)

```text
bookrec/     the assistant: data prep, search engine, agent   (milestones 1-3)
data/        catalog.csv is committed; raw/ downloads are git-ignored
notebooks/   exploration notebooks (run on Kaggle)
eval/        test questions, scorers, experiment runner      (milestones 4-5)
app/         web chat UI + Dockerfile                        (milestone 6)
```

## Setup

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate          # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # then put your real keys in .env, never commit it
python -m bookrec.prepare_data  # rebuilds data/catalog.csv
python -m bookrec.search "كتب عن تربية الأطفال"
python -m bookrec.agent "أريد رواية تاريخية"   # needs OPENAI_API_KEY in .env
```

## License

Code: MIT. The book data belongs to its original source (Jamalon, via Kaggle) and is used here
for education.
