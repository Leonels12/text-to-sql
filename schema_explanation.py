"""Read the database structure and turn it into text for the LLM prompt."""
import sqlite3


def get_schema(db_path: str = "data/chinook.db") -> str:
    """Return the CREATE TABLE statements of all tables as one string."""
    # Open read-only: this function can never change the database.
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    return "\n\n".join(sql for (sql,) in rows if sql)


if __name__ == "__main__":
    print(get_schema())