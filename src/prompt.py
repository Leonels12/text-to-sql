"""Build the prompts that are sent to the LLM."""
from src.schema_explanation import get_schema

INSTRUCTIONS = """You are an expert data analyst who writes SQLite queries.

Rules:
- Return exactly one SQLite SELECT statement and nothing else: no explanation, no markdown.
- Use only the tables and columns in the schema below.
- Never modify data.
- If the question cannot be answered from this database, return exactly: CANNOT_ANSWER
"""


def build_system_prompt(db_path: str = "data/chinook.db") -> str:
    """Fixed part of the prompt: instructions and schema. Build once, reuse."""
    parts = [INSTRUCTIONS.strip()]
    parts.append("Database schema:\n" + get_schema(db_path))
    return "\n\n".join(parts)


def build_user_prompt(question: str) -> str:
    """Changing part of the prompt: the user's question."""
    return f"Question: {question.strip()}"


if __name__ == "__main__":
    system_prompt = build_system_prompt()
    print(system_prompt)
    print("\n---\n")
    print(build_user_prompt("Which 5 artists have the most albums?"))
    print(f"\n(system prompt: {len(system_prompt)} characters, about {len(system_prompt) // 4} tokens)")