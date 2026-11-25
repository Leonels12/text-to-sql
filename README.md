# Text-to-SQL with an Evaluation Harness

A small Python pipeline that turns natural-language questions into SQL with the Gemini API, checks the SQL for safety, and runs it read-only against the [Chinook](https://github.com/lerocha/chinook-database) sample database (a SQLite music store). The repo also contains a 40-question test set with reference SQL, so different prompts and settings can be measured with **execution accuracy** instead of judged by eye.

## How it works

```
question → schema + prompt → Gemini → SQL → validator → read-only execution → rows
                                         ↑                      │
                                         └── one retry on error ┘
```

1. **Schema extraction and prompt building.** The table definitions are read from the database and put into the prompt. Three prompt variants exist: `basic` (schema only), `samples` (schema plus a few example rows per table) and `fewshot` (schema plus worked question/SQL examples).
2. **LLM call.** The model returns one SQL statement, or says the question can't be answered from the database.
3. **Validation.** Anything that is not a plain read query (for example `DROP`, `DELETE`, `UPDATE`) is blocked before it reaches the database.
4. **Safe execution.** The query runs on a read-only connection with a row cap and a timeout.
5. **Retry.** If the query fails, the error message is sent back to the model once for a corrected query. This can be switched off for experiments.

## How it is evaluated

The test set has **40 questions** in four difficulty levels (10 each): single table, aggregation, joins and hard (subqueries, set operations, window logic). Each question has a hand-checked reference query. "Top N" questions were checked for ties at the cut-off, because a tie means two correct answers.
`tests/refusal_set.json` adds **5 questions that must be refused or blocked** (for example "Drop the Album table.", or "What is the weather in Munich today?").

**Grading:** an answer is correct if the model's query returns the same rows as the reference query. Column names are ignored, numbers are rounded to 2 decimals, and row order only counts when the question asks for an order (for example "top 3"). Comparing the SQL text instead would be wrong here: only 19 to 21 of the 40 generated queries are textually identical to the reference, although all 40 return the correct rows.

## Results

Model: `gemini-3.1-flash-lite` (the only model tested). Seven full runs on the 40-question set, plus the 5 refusal questions each time.

| model | prompt | retry | runs | single_table | aggregation | join | hard | total | refusals |
|---|---|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | basic | on | 2 | 10/10 | 10/10 | 10/10 | 10/10 | 40/40 | 5/5 |
| gemini-3.1-flash-lite | basic | off | 2 | 10/10 | 10/10 | 10/10 | 10/10 | 40/40 | 5/5 |
| gemini-3.1-flash-lite | samples | on | 2 | 10/10 | 10/10 | 10/10 | 10/10 | 40/40 | 5/5 |
| gemini-3.1-flash-lite | fewshot | on | 1 | 10/10 | 10/10 | 10/10 | 10/10 | 40/40 | 5/5 |

Raw per-question results (generated SQL, verdict, attempts, seconds) are in [`results/`](results/).

**Findings**

- **The test set is saturated for this model.** Every configuration answered all 40 questions correctly and passed all 5 refusal questions. That means the 40 questions can't tell the prompt variants apart. With 40/40, the 95% confidence interval for the true accuracy is roughly 91% to 100%, so the result says "at least about 91%", not "perfect".
- **The retry was never used.** Every question was answered on the first attempt, so switching it on or off made no difference here.
- **The prompt changes the SQL but not the score.** Compared with `basic`, 7 of 40 queries differ with `samples` and 17 of 40 with `fewshot`, and all of them still return the correct rows. One example: for "Which employees were hired in 2003?", `basic` writes `HireDate LIKE '2003%'`, while `samples` and `fewshot` use `strftime('%Y', HireDate) = '2003'`. Both are correct on this database, but only the second does not depend on how dates are stored.
- **Runs are reproducible.** Repeating a configuration on a different day gave identical SQL for all 40 questions (checked for the three configurations that were run twice).
- **Latency.** The median is 1.1 to 2.2 seconds per question. Single calls sometimes take 20 to 55 seconds, which is most likely waiting on the API.

Details and examples of correct-but-different queries: [docs/error_analysis.md](docs/error_analysis.md)

### Example

Question: *Which 3 customers spent the most money in total? Show first name, last name and the amount.*

```sql
SELECT T1.FirstName, T1.LastName, SUM(T2.Total) AS TotalSpent
FROM Customer AS T1 JOIN Invoice AS T2 ON T1.CustomerId = T2.CustomerId
GROUP BY T1.CustomerId ORDER BY TotalSpent DESC LIMIT 3
```

## Run it yourself

You need Python 3.10+ and a free Gemini API key from [Google AI Studio](https://aistudio.google.com/). The Gemini API is not available in every country. If you get `User location is not supported`, the API is blocking your region.

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
| `python3 -m src.evaluate --model gemini-3.1-flash-lite --variant fewshot` | One full evaluation run |
| `./run_experiments.sh` | All experiments and the results table |

A full run takes 5 to 10 minutes because of the pause between API calls (`--sleep`, default 4 seconds), which keeps the free tier from rate-limiting you.

## Limitations

- **Saturated benchmark.** All configurations score 40/40, so the results do not show which prompt is better. A harder question set, or a weaker model, would be needed for that.
- **One model, one database.** Only `gemini-3.1-flash-lite` was tested, on an 11-table database. Real databases have hundreds of tables, where choosing the relevant tables becomes the hard part.
- **Small test set.** 40 questions can show clear differences, not small ones: one question is 2.5 percentage points.
- **Grading by result rows** can mark a correct answer wrong if it only differs in extra columns, and it cannot tell a robust query from one that happens to work on this data.
- **The safety check is a filter, not a guarantee.** The read-only connection, row cap and timeout are the second line of defence.
