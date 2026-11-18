"""Chain the steps: question -> SQL -> validate -> execute (-> retry on error)."""
from dataclasses import dataclass

from src.query_execution import QueryResult, execute_query
from src.llm import fix_sql, generate_sql
from src.validator import UnsafeSQLError, validate_sql

CANNOT_ANSWER = "CANNOT_ANSWER"


@dataclass
class Answer:
    question: str
    sql: str                       # last SQL that was tried ("" if none)
    result: QueryResult | None     # None if nothing was executed
    status: str                    # "ok", "cannot_answer", "blocked" or "error"
    message: str = ""              # explanation for the user when status != "ok"
    attempts: int = 1              # number of times the model was asked


def answer(question: str, use_retry: bool = True, max_retries: int = 1) -> Answer:
    """Answer a question about the database. Never raises for SQL problems."""
    sql = generate_sql(question)
    attempts = 1

    while True:
        # The model signals that the question can't be answered from the data.
        if sql.strip().upper() == CANNOT_ANSWER:
            return Answer(question, "", None, "cannot_answer",
                          "This question can't be answered from the database.", attempts)

        # Layer 1: validator. A blocked query is never retried.
        try:
            safe_sql = validate_sql(sql)
        except UnsafeSQLError as exc:
            return Answer(question, sql, None, "blocked",
                          f"Query blocked: {exc}", attempts)

        # Layer 2: read-only execution with limits.
        result = execute_query(safe_sql)
        if result.error is None:
            return Answer(question, safe_sql, result, "ok", "", attempts)

        # The query failed. Give up, or ask the model to fix it once more.
        retries_used = attempts - 1
        if not use_retry or retries_used >= max_retries:
            return Answer(question, safe_sql, result, "error", result.error, attempts)

        sql = fix_sql(question, safe_sql, result.error)
        attempts += 1


if __name__ == "__main__":
    for q in [
        "Which 5 artists have the most albums?",
        "What is the weather in Munich today?",
        "Delete all customers",
    ]:
        a = answer(q)
        print(f"Q: {q}\n   status={a.status}, attempts={a.attempts}")
        print(f"   SQL: {a.sql}")
        if a.result and a.result.rows:
            print(f"   rows: {a.result.rows[:3]}")
        if a.message:
            print(f"   message: {a.message}")
        print()