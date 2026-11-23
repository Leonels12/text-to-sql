"""Build the prompts that are sent to the LLM.

There are three prompt variants, so the evaluation can measure what helps:
- basic:   instructions + schema (the baseline)
- samples: basic + 3 example rows per table, so the model sees real values
           (e.g. that Country is 'USA', not 'United States', and how dates look)
- fewshot: samples + a few example questions with correct SQL
"""
from src.schema_explanation import get_sample_rows, get_schema

VARIANTS = ("basic", "samples", "fewshot")

INSTRUCTIONS = """You are an expert data analyst who writes SQLite queries.

Rules:
- Return exactly one SQLite SELECT statement and nothing else: no explanation, no markdown.
- Use only the tables and columns in the schema below.
- Never modify data.
- If the question cannot be answered from this database, return exactly: CANNOT_ANSWER
"""

# Hints learned from the data. Only used from the "samples" variant on.
DATA_HINTS = """Notes about the data:
- Dates are stored as text in the format 'YYYY-MM-DD HH:MM:SS'. Use strftime('%Y', col) for years.
- Revenue of a sale is UnitPrice * Quantity in InvoiceLine; Invoice.Total is the invoice sum.
- Only return the columns the question asks for.
"""

# Example questions for the few-shot variant. They are deliberately NOT in
# tests/test_set.json, otherwise the evaluation would test memorised answers.
FEW_SHOT_EXAMPLES = [
    ("How many albums are there?",
     "SELECT COUNT(*) FROM Album;"),
    ("Which 3 cities have the most customers? Show city and number of customers.",
     "SELECT City, COUNT(*) AS Customers FROM Customer GROUP BY City ORDER BY Customers DESC LIMIT 3;"),
    ("List the names of all tracks by the artist Queen.",
     "SELECT t.Name FROM Track t JOIN Album al ON al.AlbumId = t.AlbumId "
     "JOIN Artist ar ON ar.ArtistId = al.ArtistId WHERE ar.Name = 'Queen';"),
    ("How many invoices were issued in 2010?",
     "SELECT COUNT(*) FROM Invoice WHERE strftime('%Y', InvoiceDate) = '2010';"),
    ("Which genres have no tracks on any invoice?",
     "SELECT Name FROM Genre WHERE GenreId NOT IN "
     "(SELECT t.GenreId FROM Track t JOIN InvoiceLine il ON il.TrackId = t.TrackId);"),
]


def build_system_prompt(db_path: str = "data/chinook.db", variant: str = "basic") -> str:
    """Fixed part of the prompt: instructions and schema. Build once, reuse."""
    if variant not in VARIANTS:
        raise ValueError(f"Unknown prompt variant {variant!r}. Use one of {VARIANTS}.")

    parts = [INSTRUCTIONS.strip()]
    parts.append("Database schema:\n" + get_schema(db_path))

    if variant in ("samples", "fewshot"):
        parts.append(DATA_HINTS.strip())
        parts.append("Example rows (3 per table):\n" + get_sample_rows(db_path, n=3))

    if variant == "fewshot":
        examples = "\n\n".join(f"Question: {q}\nSQL: {sql}" for q, sql in FEW_SHOT_EXAMPLES)
        parts.append("Examples of good answers:\n" + examples)

    return "\n\n".join(parts)


def build_user_prompt(question: str) -> str:
    """Changing part of the prompt: the user's question."""
    return f"Question: {question.strip()}"


def build_retry_prompt(question: str, bad_sql: str, error: str) -> str:
    """Prompt that shows the model its failed query and the database error."""
    return (
        f"Question: {question.strip()}\n\n"
        f"Your previous query:\n{bad_sql}\n\n"
        f"It failed with this error:\n{error}\n\n"
        "Return a corrected SQLite SELECT statement only."
    )


if __name__ == "__main__":
    import sys
    variant = sys.argv[1] if len(sys.argv) > 1 else "basic"
    system_prompt = build_system_prompt(variant=variant)
    print(system_prompt)
    print("\n---\n")
    print(build_user_prompt("Which 5 artists have the most albums?"))
    print(f"\n(variant {variant}: {len(system_prompt)} characters, about {len(system_prompt) // 4} tokens)")
