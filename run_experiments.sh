#!/usr/bin/env bash
# Run all experiments one after another, then build the comparison table.
# Each run makes about 45 API calls. Use a longer --sleep if you hit rate limits.
set -u
SLEEP=4
SMALL=gemini-3.1-flash-lite
BIG=gemini-3.7-flash

run() { echo; echo ">>> $*"; python3 -m src.evaluate --sleep "$SLEEP" "$@" || echo "!!! run failed: $*"; }

# 1. Baseline
run --model "$SMALL" --variant basic
# 2. Does the retry help?
run --model "$SMALL" --variant basic --no-retry
# 3. Do better prompts help?
run --model "$SMALL" --variant samples
run --model "$SMALL" --variant fewshot
# 4. Does a bigger model help?
run --model "$BIG" --variant basic
run --model "$BIG" --variant fewshot

python3 -m src.compare --full-only --write
