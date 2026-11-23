# Text-to-SQL with evaluation

Ask questions about a database in plain English. A large language model (Gemini) writes
the SQL, a validator checks that it is safe, and the query runs read-only on the
[Chinook](https://github.com/lerocha/chinook-database) music-store database.

The main part of the project is the **evaluation**: a hand-checked test set of 40
questions with reference SQL, and a script that measures how often the model gets
the right answer, per difficulty level, model and prompt.

![tests](https://github.com/Leonels12/text-to-sql/actions/workflows/tests.yml/badge.svg)

## How it works

```
question
  -> schema (+ sample rows, + examples, depending on the prompt variant)
  -> Gemini writes one SELECT statement, or CANNOT_ANSWER
  -> validator: one statement, SELECT/WITH only, no forbidden keywords
  -> read-only execution with a 200-row limit and a 5-second timeout
  -> on a SQL error: show the error to the model and retry once
  -> rows
```

Safety has two independent layers. The validator rejects anything that is not a single
read query. Even if it missed something, the database is opened in read-only mode, so
writes fail anyway (tested in `tests/test_query_execution.py`).

| File | What it does |
|---|---|
| `src/schema_explanation.py` | Reads tables, columns and sample rows from the database |
| `src/prompt.py` | Builds the prompt; three variants: `basic`, `samples`, `fewshot` |
| `src/llm.py` | Calls Gemini with timeout, retries and optional backup models |
| `src/validator.py` | Blocks anything that is not one read-only query |
| `src/query_execution.py` | Runs the query read-only with row and time limits |
| `src/pipeline.py` | Chains everything together, including the retry on SQL errors |
| `src/evaluate.py` | Runs the test set and grades the answers |
| `src/compare.py` | Builds the results table from all evaluation runs |
| `app.py` | Streamlit web interface |

## Evaluation

**Test set** (`tests/test_set.json`): 40 questions, 10 per level

| Level | Examples of what is tested |
|---|---|
| single_table | filters, counts, `LIKE`, `NULL`, dates |
| aggregation | `GROUP BY`, `HAVING`, sums and averages |
| join | 2-4 tables, self-join on employees |
| hard | subqueries, "never bought", per-group ranking, date logic |

Every reference query was run and checked by hand. "Top N" questions were checked for
ties at the cut-off, because a tie means two correct answers.
`tests/refusal_set.json` adds 5 questions that must be refused or blocked
(e.g. "Drop the Album table").

**Grading:** an answer is correct if the model's query returns the same rows as the
reference query. Column names are ignored, numbers are rounded to 2 decimals, and row
order only counts when the question asks for an order (e.g. "top 3").

## Results

<!-- TODO: run ./run_experiments.sh, then paste results/summary.md here -->

| model | prompt | retry | single_table | aggregation | join | hard | total | refusals |
|---|---|---|---|---|---|---|---|---|
| TODO | | | | | | | | |

**Findings** <!-- TODO: 3-5 sentences from docs/error_analysis.md -->

- Most common failure:
- Effect of sample rows / few-shot examples:
- Effect of the retry:
- Effect of a bigger model:

Details: [docs/error_analysis.md](docs/error_analysis.md)

## Run it yourself

```bash
git clone https://github.com/Leonels12/text-to-sql.git
cd text-to-sql
pip install -r requirements.txt
mkdir -p data
curl -L -o data/chinook.db https://github.com/lerocha/chinook-database/releases/download/v1.4.5/Chinook_Sqlite.sqlite
cp .env.example .env          # then put your Gemini API key into .env
```

| Command | What it does |
|---|---|
| `python3 -m src.pipeline` | Answer three example questions |
| `streamlit run app.py` | Web interface |
| `python3 -m pytest` | Tests (no API key needed) |
| `python3 tests/check_reference.py` | Check that all reference queries run |
| `python3 -m src.evaluate --limit 5` | Quick evaluation on 5 questions |
| `python3 -m src.evaluate --model gemini-3.7-flash --variant fewshot` | One full evaluation run |
| `./run_experiments.sh` | All experiments + results table |

## Limitations

- One small database (11 tables). Real databases have hundreds of tables, where
  choosing the relevant tables becomes the hard part.
- 40 questions is enough to see clear differences, not small ones: one question is
  2.5 percentage points.
- Grading by result rows can mark an answer wrong that only differs in extra columns.
