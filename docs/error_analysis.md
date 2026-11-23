# Error analysis

Fill this in after the experiments. Start with the questions at the top of
"Questions that failed most often" in `results/summary.md`. For each one, open the
results JSON, compare `generated_sql` with `reference_sql`, and decide **why** it failed.

## Categories

| Category | What it means | Example of how to spot it |
|---|---|---|
| wrong_join | Wrong table, missing table or wrong join key | Uses `Invoice.Total` where the question needs `InvoiceLine` |
| wrong_filter | Wrong value or condition | `'United States'` instead of `'USA'`, `>` instead of `>=` |
| wrong_aggregation | Wrong function or grouping | `COUNT` instead of `SUM`, grouped by name instead of id |
| date_handling | Date text not handled correctly | Compares `InvoiceDate = '2011'` instead of using `strftime` |
| extra_or_missing_columns | Right idea, but different columns | Adds an id column the question did not ask for |
| ordering_or_limit | Missing `ORDER BY`, wrong `LIMIT`, ties | Returns 5 rows for a top-3 question |
| ambiguity | The question allows more than one reading | "best-selling" as revenue vs. units |
| refused | Said `CANNOT_ANSWER` for an answerable question | |
| grading_issue | The answer is actually right, the comparison is too strict | Values are equal but formatted differently |

If many failures are `extra_or_missing_columns` or `grading_issue`, the model is better
than the score says. Mention that honestly in the README: it is a real finding.

## Failures

| id | level | runs failed | category | what went wrong (one sentence) |
|---|---|---|---|---|
|  |  |  |  |  |

## What I learned

- Most common failure:
- What the prompt variants fixed:
- What the bigger model fixed:
- What none of them fixed:
