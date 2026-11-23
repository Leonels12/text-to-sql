"""The validator is the first safety layer: nothing dangerous may pass it."""
import pytest

from src.validator import UnsafeSQLError, validate_sql

DANGEROUS = [
    "DELETE FROM Customer",
    "DROP TABLE Album",
    "UPDATE Customer SET Email = 'x'",
    "INSERT INTO Genre VALUES (99, 'x')",
    "ALTER TABLE Album ADD COLUMN x",
    "PRAGMA table_info(Album)",
    "ATTACH DATABASE 'x.db' AS x",
    "REPLACE INTO Genre VALUES (1, 'x')",
    "SELECT 1; DELETE FROM Customer",          # second statement
    "SELECT 1; -- harmless?\nDROP TABLE Album",
    "WITH x AS (SELECT 1) DELETE FROM Customer",
    "select * from Album; drop table Album",   # lower case
    "",
    "   ",
    "SELECT 'unterminated",
]

SAFE = [
    "SELECT * FROM Customer",
    "SELECT * FROM Customer;",                           # one trailing semicolon is fine
    "select Name from Artist limit 5",
    "WITH t AS (SELECT * FROM Track) SELECT COUNT(*) FROM t",
    "SELECT * FROM Track WHERE Name = 'Drop the Bomb'",  # keyword inside a string
    "SELECT REPLACE(Name, 'a', 'b') FROM Artist",        # REPLACE as a function
    "SELECT Name FROM Track -- a comment with DELETE",
    "SELECT * FROM Customer WHERE LastName = 'O''Brien'",
]


@pytest.mark.parametrize("sql", DANGEROUS)
def test_dangerous_queries_are_blocked(sql):
    with pytest.raises(UnsafeSQLError):
        validate_sql(sql)


@pytest.mark.parametrize("sql", SAFE)
def test_safe_queries_pass(sql):
    assert validate_sql(sql)


def test_trailing_semicolon_is_removed():
    assert validate_sql("SELECT 1;") == "SELECT 1"
