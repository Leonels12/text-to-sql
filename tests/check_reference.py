"""Sanity-check the test set: run every reference query and flag problems.

Run from the project root:  python3 -m tests.check_reference
(or: python3 tests/check_reference.py)
"""
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "chinook.db"
TEST_SET = ROOT / "tests" / "test_set.json"
LEVELS = ["single_table", "aggregation", "join", "hard"]


def main() -> int:
    questions = json.loads(TEST_SET.read_text(encoding="utf-8"))
    # read-only, same as the real pipeline
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    problems = 0

    for q in questions:
        try:
            rows = conn.execute(q["reference_sql"]).fetchall()
        except sqlite3.Error as exc:
            print(f"[{q['id']:>2}] ERROR  {exc}\n      {q['question']}")
            problems += 1
            continue
        flag = "EMPTY " if not rows else "ok    "
        if not rows:
            problems += 1
        first = rows[0] if rows else None
        print(f"[{q['id']:>2}] {flag} {q['difficulty']:<12} rows={len(rows):<4} first={first}")

    counts = Counter(q["difficulty"] for q in questions)
    print("\nPer level:", {lvl: counts[lvl] for lvl in LEVELS})
    if len(questions) != len({q["question"] for q in questions}):
        print("WARNING: duplicate questions"); problems += 1
    if len({q["id"] for q in questions}) != len(questions):
        print("WARNING: duplicate ids"); problems += 1
    for lvl in LEVELS:
        if counts[lvl] != 10:
            print(f"WARNING: {lvl} has {counts[lvl]} questions, expected 10"); problems += 1

    print(f"\n{len(questions)} questions, {problems} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
