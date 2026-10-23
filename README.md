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
| 2 | Search engine | Char-level TF-IDF that tolerates Arabic spelling variations | ⏳ |
| 3 | Agent | An LLM that calls the search tool and answers in Arabic | ⏳ |
| 4 | Evaluate with Langfuse | Traces, 12 fixed test questions, code check + LLM judge | ⏳ |
| 5 | Improve the prompt | Change one thing, re-test, keep it only if it wins | ⏳ |
| 6 | Deploy on AWS | Container on ECS Express Mode with HTTPS and secure keys | ⏳ |
| 7 | Document and clean up | README, evaluation article, delete cloud resources | ⏳ |

## Data

The catalog comes from the public
[Jamalon Arabic Books Dataset](https://www.kaggle.com/datasets/dareenalharthi/jamalon-arabic-books-dataset)
(books scraped from the Jamalon online bookstore). It was explored step by step in
[notebooks/01_data_exploration.ipynb](notebooks/01_data_exploration.ipynb)
([run it on Kaggle](https://www.kaggle.com/code/jamalla/jamalon-eda-arabic-book-recommender)).

| Step | Books |
|------|------:|
| Raw dataset | 8,986 |
| Has a real description (not empty, not "None") | 4,443 |
| Description of 100+ characters, duplicates removed | 3,979 |
| Known author, 10 chosen categories, balanced sample of 20 each (seed 42) | **200** |

`python -m bookrec.prepare_data` downloads the dataset and rebuilds
[data/catalog.csv](data/catalog.csv). Its fingerprint is `20958bc305` both on Kaggle and on a
local machine, so anyone can reproduce exactly the same 200 books.

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
```

## License

Code: MIT. The book data belongs to its original source (Jamalon, via Kaggle) and is used here
for education.
