"""Read the database structure and turn it into text for the LLM prompt."""
import sqlite3


def _connect(db_path: str) -> sqlite3.Connection:
    # Open read-only: these functions can never change the database.
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def get_table_names(db_path: str = "data/chinook.db") -> list[str]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    return [name for (name,) in rows]


def get_schema(db_path: str = "data/chinook.db") -> str:
    """Return the CREATE TABLE statements of all tables as one string."""
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    return "\n\n".join(sql for (sql,) in rows if sql)


def get_sample_rows(db_path: str = "data/chinook.db", n: int = 3, max_value_len: int = 40) -> str:
    """Return the first n rows of every table, so the model sees real values."""
    con = _connect(db_path)
    blocks = []
    try:
        for table in get_table_names(db_path):
            cursor = con.execute(f'SELECT * FROM "{table}" LIMIT {int(n)}')
            columns = [d[0] for d in cursor.description]
            lines = [f"{table}: " + " | ".join(columns)]
            for row in cursor.fetchall():
                values = [str(v)[:max_value_len] if v is not None else "NULL" for v in row]
                lines.append("  " + " | ".join(values))
            blocks.append("\n".join(lines))
    finally:
        con.close()
    return "\n\n".join(blocks)


if __name__ == "__main__":
    print(get_schema())
    print("\n---\n")
    print(get_sample_rows())
