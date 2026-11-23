"""Compare all evaluation runs in results/ and print one table.

Run from the project root:
    python3 -m src.compare            # print the table and the hardest questions
    python3 -m src.compare --write    # also save it to results/summary.md (paste into README)
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

RESULTS_DIR = Path("results")
LEVELS = ["single_table", "aggregation", "join", "hard"]


def load_runs() -> list[dict]:
    runs = []
    for path in sorted(RESULTS_DIR.glob("eval_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["file"] = path.name
        data.setdefault("prompt_variant", "basic")  # older runs had no variant
        runs.append(data)
    return runs


def accuracy(results: list[dict]) -> str:
    if not results:
        return "-"
    ok = sum(r["verdict"] == "correct" for r in results)
    return f"{ok}/{len(results)} ({ok / len(results):.0%})"


def build_table(runs: list[dict]) -> str:
    header = ["model", "prompt", "retry", *LEVELS, "total", "refusals"]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for run in runs:
        results = run["results"]
        by_level = defaultdict(list)
        for r in results:
            by_level[r["difficulty"]].append(r)
        refusals = run.get("refusal_results") or []
        refusal_text = f"{sum(r['passed'] for r in refusals)}/{len(refusals)}" if refusals else "-"
        row = [run["model"], run["prompt_variant"], "on" if run.get("retry_enabled") else "off",
               *(accuracy(by_level[lvl]) for lvl in LEVELS), accuracy(results), refusal_text]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def hardest_questions(runs: list[dict], top: int = 10) -> str:
    """Questions that failed in the most runs: the best starting point for error analysis."""
    failed = Counter()
    seen = Counter()
    text = {}
    for run in runs:
        for r in run["results"]:
            seen[r["id"]] += 1
            text[r["id"]] = r["question"]
            if r["verdict"] != "correct":
                failed[r["id"]] += 1
    lines = []
    for qid, n in failed.most_common(top):
        lines.append(f"- [{qid}] failed in {n} of {seen[qid]} runs: {text[qid]}")
    return "\n".join(lines) or "- none"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare evaluation runs.")
    parser.add_argument("--write", action="store_true", help="save to results/summary.md")
    parser.add_argument("--full-only", action="store_true",
                        help="ignore short test runs (fewer than 40 questions)")
    args = parser.parse_args()

    runs = load_runs()
    if args.full_only:
        runs = [r for r in runs if len(r["results"]) >= 40]
    if not runs:
        print("No runs found in results/. Run: python3 -m src.evaluate")
        return

    text = "## Results\n\n" + build_table(runs) + "\n\n## Questions that failed most often\n\n" \
           + hardest_questions(runs) + "\n"
    print(text)
    if args.write:
        (RESULTS_DIR / "summary.md").write_text(text, encoding="utf-8")
        print(f"Saved to {RESULTS_DIR / 'summary.md'}")


if __name__ == "__main__":
    main()
