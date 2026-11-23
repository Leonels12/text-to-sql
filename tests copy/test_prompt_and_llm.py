"""Prompt building and SQL cleaning, no API calls."""
import json
from pathlib import Path

import pytest

from src.llm import clean_sql
from src.prompt import FEW_SHOT_EXAMPLES, VARIANTS, build_system_prompt

HAS_DB = Path("data/chinook.db").exists()


def test_clean_sql_removes_code_fences():
    assert clean_sql("```sql\nSELECT 1;\n```") == "SELECT 1;"
    assert clean_sql("```\nSELECT 1\n```") == "SELECT 1"
    assert clean_sql("  SELECT 1  ") == "SELECT 1"


def test_few_shot_examples_are_not_in_the_test_set():
    # Otherwise the evaluation would reward memorised answers.
    test_questions = {q["question"].lower() for q in
                      json.loads(Path("tests/test_set.json").read_text(encoding="utf-8"))}
    for question, _ in FEW_SHOT_EXAMPLES:
        assert question.lower() not in test_questions


@pytest.mark.skipif(not HAS_DB, reason="data/chinook.db not downloaded")
@pytest.mark.parametrize("variant", VARIANTS)
def test_every_variant_contains_the_schema(variant):
    prompt = build_system_prompt(variant=variant)
    for table in ["Album", "Artist", "Customer", "Invoice", "InvoiceLine", "Track"]:
        assert f"CREATE TABLE [{table}]" in prompt or f'CREATE TABLE "{table}"' in prompt \
            or f"CREATE TABLE {table}" in prompt


def test_unknown_variant_is_rejected():
    with pytest.raises(ValueError):
        build_system_prompt(variant="nonsense")
