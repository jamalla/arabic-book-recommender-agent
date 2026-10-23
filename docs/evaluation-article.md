# Measuring an LLM agent before trusting it: an Arabic book recommender

This project builds a small Arabic chat assistant with one promise: **it recommends only real books from a
catalog of 200**. That promise is easy to state and easy to break. Language models know thousands of famous
titles, and when a search comes back empty they are tempted to fill the gap from memory.

This article is about how we found out whether the promise held, how we made it hold better, and what changed
once real people could use the app. Every number comes from runs recorded in Langfuse and the notebooks in
[notebooks/](../notebooks).

## The agent in one paragraph

An OpenAI model gets one tool, `search_books(query)`, which runs a character-level TF-IDF search over the
catalog and returns the top 5 books with a 0-1 score. The model never sees the catalog file, only what the
tool returns, and writes the Arabic answer from that. There are two versions with the same interface: a plain
tool-calling loop on the OpenAI SDK and a LangGraph agent. The chat app uses whichever one won the evaluation.

## Step 1: decide what "good" means

Before writing a single scorer we listed what a bad answer looks like:

- **It invents books.** A title that is not in the catalog breaks the core promise, however good it sounds.
- **It pads.** Five weak matches are worse than one good one.
- **It hides a miss.** When the catalog has nothing, the right answer says so and offers something related.

Those three became the scores.

## Step 2: a small, fixed test set with traps

The test set ([evals/dataset.py](../evals/dataset.py)) has **12 questions**, each with a sentence describing
what a good answer does:

- **9 normal questions** across the catalog's shelves: a historical novel, parenting, simple philosophy,
  economics, Arab politics, science, memoirs, art and calligraphy, the Prophet's biography.
- **3 traps** the catalog provably cannot answer: Harry Potter, Naguib Mahfouz novels, learning Python.
  "Provably" matters. We checked in code that none of those books exist in `catalog.csv` before using them,
  so a refusal is the only correct answer.

The set is fixed, so every run answers the same questions and runs can be compared. It is small on purpose: it
is cheap to run after every change and small enough to read every answer. The price is that a single question
moves the average by more than 8 points.

## Step 3: two scorers that check each other

| Score | Who decides | What it measures |
|---|---|---|
| `invented_books` | **code** | Recommended titles that are not in `catalog.csv`. An LLM only copies the titles out of the answer (structured output); plain code decides whether each one exists. |
| `fit` | **LLM judge** | 0 to 1: do the recommended books fit the request? 1.0 = all fit, or nothing fits and the answer says so; 0.5 = a mix with padding; 0.0 = they do not fit or are invented. |

The judge is a stronger model than the agent and sees the reader's request, the "what a good answer does"
sentence, the answer, and the books the search actually returned. It must give a one-sentence reason, which
turned out to be the most useful part: a score tells you *that* something is wrong, the reason tells you
*where to look*.

Each run also gets three summary numbers: `avg_fit`, `grounded_rate` (share of answers with zero invented
books) and `invented_total`. The whole thing runs as a Langfuse dataset experiment, so every answer is a trace
with its tool calls, and two runs can be compared question by question.

## Step 4: evaluate the evaluator

The first run reported six invented books. Reading the traces showed all six were real. The two scorers
disagreed (the judge was happy, the code check was not), and that disagreement was the clue:

- the agent wrote «موجز تاريخ الكون: ...» while the catalog has «... الكون : ...» (a space before the colon);
- one catalog title has a typo, «مبائ» instead of «مبادئ», and the agent politely corrected it.

The fix was to compare titles by their letters only and accept titles that are at least 90% similar. Ten test
cases now pin that behaviour down. The lesson is general: **scorers are code, and code has bugs**. When two
independent scorers disagree, read the evidence before you believe either of them.

## Step 5: the baseline

Prompt v1 was an honest first draft. Its scores:

| Metric | Prompt v1 |
|---|---:|
| Average fit | 0.75 |
| Grounded answers | 11 / 12 |
| Invented books | 8 |

All eight invented books came from one question. Asked for Naguib Mahfouz novels, the agent searched three
times, found nothing, and then recommended his famous novels from memory: exactly the failure the trap was
built to catch. On "a simple philosophy book" it padded the answer with a science book.

One more warning from this stage: an earlier run of the same questions scored 0.83, not 0.75. LLM runs vary,
so small differences between two runs mean little on their own.

## Step 6: change one thing at a time

We made two changes, one per run, and kept a change only if invented books did not go up and average fit did
not go down.

| Run | Agent | Prompt | Average fit | Grounded | Invented |
|---|---|---|---:|---:|---:|
| A (baseline) | plain loop | v1 | 0.750 | 11 / 12 | 8 |
| B | plain loop | **v2** | 0.917 | 12 / 12 | 0 |
| C | **LangGraph** | v2 | **1.000** | 12 / 12 | 0 |

Prompt v2 turned what the baseline showed into five rules: recommend only books the search returned and copy
titles exactly; recommend only clear fits; say honestly when nothing fits and offer a related search; search
again with other words when results are weak (at most three searches); give title, author and one reason, in
Arabic.

The averages hide two things worth knowing.

**A fix caused a regression.** Run B removed every invented book, but the stricter prompt made the agent refuse
q09 (the Prophet's biography), a question the catalog can answer. Only the per-question scores show this; the
average went up anyway.

**Is C really better than B?** They differ on one question. We asked q09 five more times per agent: the plain
loop refused once, LangGraph never did. That makes LangGraph *at least as good* on this test, not proven
better. Five repeats of one question is a sanity check, not statistics. We shipped LangGraph with prompt v2,
and kept the plain agent one setting away (`AGENT_FRAMEWORK=openai`) so the comparison can be re-run at any
time.

## Step 7: keep measuring in production

The chat app runs the same agent, built by the same factory, so the scores we measured are the scores we
shipped. It is deployed on AWS (ECS Express Mode) and traces into the same Langfuse project, in a separate
`production` environment. Each browser chat is one session, and the 👍/👎 buttons store a `user_feedback`
score on the exact answer being rated. A two-question chat (three searches) cost about $0.001.

Real use taught two things the test set had not.

**Check the evidence before calling a refusal a bug.** The first real chat asked for a historical novel and was
told the catalog has none. It looked like the q09 over-caution again. The catalog said otherwise: none of its
20 fiction books is a historical novel, and the judge had accepted the same answer for q01. The real problem was
ours: "historical novel" was one of the example buttons on the welcome screen. We changed the examples, not the
agent.

**👎 measures satisfaction, not correctness.** A reader asked for a book on raising teenagers and got an honest
"our catalog has none", then clicked 👎. The trace shows two sensible searches and nothing to find. That 👎
points at a gap in the catalog, not at the agent. The useful habit: read the trace behind every 👎, decide
whether to fix the agent or the data, and add the question to the test set either way.

## What we would do next

- **Grow the test set from production.** Every 👎 is a candidate test question. Multi-turn chats deserve tests
  too: the current set is single-turn, while the app keeps the last ten messages.
- **Repeat runs and report spread.** Run each experiment three to five times and report the mean and the range,
  so a difference has to beat the noise before it counts.
- **Calibrate the judge.** Label a few dozen answers by hand and check how often the judge agrees, especially
  around the 0.5 "padding" boundary.
- **Track cost and latency as scores.** A prompt that searches more may be more accurate and slower; both belong
  in the comparison.

## Takeaways

1. Write down what a bad answer looks like before you write a scorer.
2. Use traps you can prove, and let code decide what code can decide.
3. When two scorers disagree, the bug may be in the scorer.
4. Change one thing per run, and read per-question results, not only the average.
5. A small difference is noise until a repeat says otherwise.
6. Production feedback is a signal to investigate, not a verdict.
