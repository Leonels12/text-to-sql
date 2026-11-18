"""Run validated SQL on the database in read-only mode, with row and time limits."""
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

DB_PATH = "data/chinook.db"
MAX_ROWS = 200
TIMEOUT_SECONDS = 5.0


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool = False     # True if more rows existed than max_rows
    error: str | None = None    # Set if the query failed, otherwise None


def execute_query(
    sql: str,
    db_path: str = DB_PATH,
    max_rows: int = MAX_ROWS,
    timeout: float = TIMEOUT_SECONDS,
) -> QueryResult:
    """Run a query read-only. Never raises for SQL problems; returns them in .error."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)  # raises if the file is missing: a setup problem
    try:
        deadline = time.monotonic() + timeout
        # Called every 10,000 SQLite VM steps; returning 1 aborts the query.
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)

        cursor = con.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(max_rows + 1)  # one extra row tells us if there was more
        truncated = len(rows) > max_rows
        return QueryResult(columns, rows[:max_rows], truncated)
    except sqlite3.Error as exc:
        message = str(exc)
        if "interrupt" in message.lower():
            message = f"Query took longer than {timeout:g} seconds and was stopped."
        return QueryResult([], [], error=message)
    finally:
        con.close()


if __name__ == "__main__":
    ok = execute_query("SELECT Name FROM Artist ORDER BY Name LIMIT 3")
    print(ok)
    print(execute_query("DELETE FROM Artist"))  # must fail: read-only