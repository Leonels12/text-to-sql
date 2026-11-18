"""Check that LLM-generated SQL is a single, read-only query before running it."""
import re


class UnsafeSQLError(ValueError):
    """Raised when a query is not allowed to run."""


FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX",
    "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "LOAD_EXTENSION",
]

# Whole words only. REPLACE is checked only as "REPLACE INTO", because
# REPLACE(text, a, b) is a harmless string function inside SELECT.
_FORBIDDEN_RE = re.compile(
    r"\b(?:" + "|".join(FORBIDDEN_KEYWORDS) + r")\b|\bREPLACE\s+INTO\b",
    re.IGNORECASE,
)

# Things that can hide keywords: strings, quoted names and comments.
_IGNORED_PARTS_RE = re.compile(
    r"""
    '(?:[^']|'')*'     # 'single-quoted string' ('' is an escaped quote)
  | "(?:[^"]|"")*"     # "double-quoted identifier"
  | --[^\n]*           # line comment
  | /\*.*?\*/          # block comment
    """,
    re.VERBOSE | re.DOTALL,
)


def validate_sql(sql: str) -> str:
    """Return the query if it is safe to run, otherwise raise UnsafeSQLError."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("Empty query.")

    # Blank out strings and comments in one pass so that text inside them
    # ('DROP TABLE' as a value, a comment, ...) cannot trigger or hide a rule.
    cleaned = _IGNORED_PARTS_RE.sub(" ", sql).strip()

    # Anything still open here is an unterminated string or comment.
    if "'" in cleaned or '"' in cleaned or "/*" in cleaned:
        raise UnsafeSQLError("Unterminated string or comment.")

    # Allow a trailing semicolon, but no second statement.
    body = cleaned.rstrip("; \n\t")
    if ";" in body:
        raise UnsafeSQLError("Only one statement is allowed.")

    if not re.match(r"(?:SELECT|WITH)\b", body, re.IGNORECASE):
        raise UnsafeSQLError("Only SELECT queries are allowed.")

    match = _FORBIDDEN_RE.search(body)
    if match:
        raise UnsafeSQLError(f"Forbidden keyword: {match.group(0).upper()}")

    return sql.strip().rstrip(";").strip()