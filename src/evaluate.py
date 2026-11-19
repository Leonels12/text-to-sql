"""Evaluate the pipeline: ask every test question and compare with the reference result.

A question counts as CORRECT when the model's query returns the same rows as the
reference query. The SQL text does not matter, only the result.
"""
import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from src.llm import MODEL
from src.pipeline import answer
from src.query_execution import execute_query

TEST_SET = Path("tests/test_set.json")
REFUSAL_SET = Path("tests/refusal_set.json")
RESULTS_DIR = Path("results")
LEVELS = ["single_table", "aggregation", "join", "hard"]

# The pipeline cuts results at 200 rows to protect the user. For fair grading we
# re-run both queries with a much higher limit, so that long results are not
# marked wrong just because they were cut off.
GRADING_MAX_ROWS = 100_000
GRADING_TIMEOUT = 30.0


# ---------- comparing results ----------

def _normalize_value(value):
    """Floats are rounded to 2 decimals so 5.6519417 and 5.65194175 count as equal."""
    return round(value, 2) if isinstance(value, float) else value


def _normalize_rows(rows) -> list[tuple]:
    return [tuple(_normalize_value(v) for v in row) for row in rows]


def results_match(expected_rows, actual_rows, order_matters: bool) -> bool:
    """True if both results contain the same rows.

    Column names are ignored (aliases like 'Revenue' vs 'Total' are fine).
    order_matters=True  -> rows must be in the same order (e.g. "top 5" questions)
    order_matters=False -> same rows in any order
    """
    expected = _normalize_rows(expected_rows)
    actual = _normalize_rows(actual_rows)
    if order_matters:
        return expected == actual
    return Counter(expected) == Counter(actual)


# ---------- running one question ----------

def grade_question(q: dict, use_retry: bool) -> dict:
    """Run one test question through the pipeline and return a result record."""
    record = {
        "id": q["id"],
        "difficulty": q["difficulty"],
        "question": q["question"],
        "reference_sql": q["reference_sql"],
        "generated_sql": "",
        "status": "",          # what the pipeline reported
        "verdict": "",         # correct, wrong_result, error, cannot_answer, blocked, crash
        "attempts": 0,
        "seconds": 0.0,
        "detail": "",          # error message or explanation
    }
    start = time.monotonic()

    expected = execute_query(q["reference_sql"], max_rows=GRADING_MAX_ROWS, timeout=GRADING_TIMEOUT)
    if expected.error:
        # Should never happen after check_reference.py. Do not blame the model.
        record.update(verdict="reference_error", detail=expected.error)
        return record

    try:
        result = answer(q["question"], use_retry=use_retry)
    except Exception as exc:  # e.g. every model was overloaded
        record.update(verdict="crash", detail=str(exc)[:300])
        record["seconds"] = round(time.monotonic() - start, 1)
        return record

    record.update(status=result.status, generated_sql=result.sql,
                  attempts=result.attempts, detail=result.message)

    if result.status != "ok":
        record["verdict"] = result.status        # cannot_answer, blocked or error
    else:
        actual = execute_query(result.sql, max_rows=GRADING_MAX_ROWS, timeout=GRADING_TIMEOUT)
        if actual.error:
            record.update(verdict="error", detail=actual.error)
        elif results_match(expected.rows, actual.rows, q["order_matters"]):
            record["verdict"] = "correct"
        else:
            record["verdict"] = "wrong_result"
            record["detail"] = (f"expected {len(expected.rows)} rows, got {len(actual.rows)}; "
                                f"expected first: {expected.rows[:1]}, got first: {actual.rows[:1]}")

    record["seconds"] = round(time.monotonic() - start, 1)
    return record


def grade_refusal(q: dict) -> dict:
    """A refusal question passes if the pipeline refuses it or the validator blocks it."""
    allowed = {"cannot_answer": {"cannot_answer"},
               "cannot_answer_or_blocked": {"cannot_answer", "blocked"}}[q["expected_status"]]
    record = {"id": q["id"], "question": q["question"], "expected": q["expected_status"],
              "status": "", "passed": False, "generated_sql": "", "detail": ""}
    try:
        result = answer(q["question"], use_retry=False)
    except Exception as exc:
        record["status"] = "crash"
        record["detail"] = str(exc)[:300]
        return record
    record.update(status=result.status, generated_sql=result.sql, detail=result.message,
                  passed=result.status in allowed)
    return record


# ---------- reporting ----------

def print_summary(results: list[dict], refusals: list[dict]) -> None:
    print("\n" + "=" * 60)
    print(f"Model: {MODEL}   questions: {len(results)}")
    print("=" * 60)

    by_level = defaultdict(list)
    for r in results:
        by_level[r["difficulty"]].append(r)
    print(f"{'level':<14}{'correct':>8}{'total':>7}{'accuracy':>10}")
    for level in LEVELS:
        rs = by_level.get(level, [])
        if rs:
            ok = sum(r["verdict"] == "correct" for r in rs)
            print(f"{level:<14}{ok:>8}{len(rs):>7}{ok / len(rs):>10.0%}")
    total_ok = sum(r["verdict"] == "correct" for r in results)
    if results:
        print(f"{'ALL':<14}{total_ok:>8}{len(results):>7}{total_ok / len(results):>10.0%}")

    print("\nWhat happened to the wrong ones:")
    for verdict, n in Counter(r["verdict"] for r in results if r["verdict"] != "correct").most_common():
        print(f"  {verdict:<16}{n}")
    retried = [r for r in results if r["attempts"] > 1]
    if retried:
        fixed = sum(r["verdict"] == "correct" for r in retried)
        print(f"\nRetry was used for {len(retried)} questions and {fixed} of them ended up correct.")

    if refusals:
        passed = sum(r["passed"] for r in refusals)
        print(f"\nRefusal/safety questions passed: {passed} of {len(refusals)}")
        for r in refusals:
            if not r["passed"]:
                print(f"  FAILED: {r['question']} -> status={r['status']} sql={r['generated_sql']}")

    wrong = [r for r in results if r["verdict"] != "correct"]
    if wrong:
        print("\nWrong or failed questions (details are in the results file):")
        for r in wrong:
            print(f"  [{r['id']:>2}] {r['verdict']:<14}{r['question']}")


def save_results(results, refusals, use_retry) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = RESULTS_DIR / f"eval_{MODEL}_{stamp}"
    total_ok = sum(r["verdict"] == "correct" for r in results)
    payload = {
        "model": MODEL,
        "timestamp": stamp,
        "retry_enabled": use_retry,
        "accuracy": round(total_ok / len(results), 4) if results else None,
        "results": results,
        "refusal_results": refusals,
    }
    base.with_suffix(".json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    return base


# ---------- main ----------

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the text-to-SQL pipeline.")
    parser.add_argument("--limit", type=int, help="only run the first N questions")
    parser.add_argument("--ids", help="comma-separated question ids, e.g. 3,17,31")
    parser.add_argument("--no-retry", action="store_true", help="disable the SQL-fix retry")
    parser.add_argument("--no-refusal", action="store_true", help="skip the refusal/safety questions")
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds to wait between questions")
    args = parser.parse_args()
    use_retry = not args.no_retry

    questions = json.loads(TEST_SET.read_text(encoding="utf-8"))
    if args.ids:
        wanted = {int(i) for i in args.ids.split(",")}
        questions = [q for q in questions if q["id"] in wanted]
    if args.limit:
        questions = questions[: args.limit]

    results = []
    for i, q in enumerate(questions, 1):
        r = grade_question(q, use_retry)
        mark = "OK  " if r["verdict"] == "correct" else "FAIL"
        print(f"[{i:>2}/{len(questions)}] {mark} {r['verdict']:<14} {q['question'][:60]}", flush=True)
        results.append(r)
        time.sleep(args.sleep)

    refusals = []
    if not args.no_refusal:
        for q in json.loads(REFUSAL_SET.read_text(encoding="utf-8")):
            r = grade_refusal(q)
            print(f"[refusal] {'OK  ' if r['passed'] else 'FAIL'} {r['status']:<14} {q['question']}", flush=True)
            refusals.append(r)
            time.sleep(args.sleep)

    print_summary(results, refusals)
    if results:
        base = save_results(results, refusals, use_retry)
        print(f"\nSaved: {base}.json and {base}.csv")


if __name__ == "__main__":
    main()