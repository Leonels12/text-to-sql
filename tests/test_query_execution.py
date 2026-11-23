"""The executor is the second safety layer: read-only, with limits."""
from pathlib import Path

import pytest

from src.query_execution import execute_query

pytestmark = pytest.mark.skipif(not Path("data/chinook.db").exists(),
                                reason="data/chinook.db not downloaded")


def test_simple_query():
    result = execute_query("SELECT COUNT(*) FROM Customer")
    assert result.error is None
    assert result.rows == [(59,)]


def test_database_is_read_only():
    # Even if the validator were bypassed, the database must refuse writes.
    result = execute_query("DELETE FROM Customer")
    assert result.error is not None
    assert execute_query("SELECT COUNT(*) FROM Customer").rows == [(59,)]


def test_row_limit():
    result = execute_query("SELECT * FROM Track", max_rows=10)
    assert len(result.rows) == 10
    assert result.truncated


def test_sql_error_is_returned_not_raised():
    result = execute_query("SELECT nonsense FROM nowhere")
    assert result.error is not None
    assert result.rows == []


def test_timeout_stops_slow_query():
    slow = ("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) "
            "SELECT COUNT(*) FROM n")
    result = execute_query(slow, timeout=0.5)
    assert result.error is not None and "longer than" in result.error
