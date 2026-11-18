"""Send a question to the LLM and get a SQL string back."""
import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.prompt import build_system_prompt, build_user_prompt

load_dotenv()  # load values from the .env file

MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")

_client = None
_system_prompt = None


def _get_client() -> genai.Client:
    """Create the API client once and reuse it."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")
        _client = genai.Client(api_key=api_key)
    return _client


def clean_sql(text: str) -> str:
    """Remove markdown code fences and surrounding whitespace from model output."""
    text = text.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    return text.strip()


def _ask(user_prompt: str) -> str:
    """Send one request to the model and return cleaned SQL text."""
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = build_system_prompt()

    response = _get_client().models.generate_content(
        model=MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=_system_prompt,
            temperature=0,
        ),
    )
    return clean_sql(response.text or "")


def generate_sql(question: str) -> str:
    """Ask the model for a SQL query that answers the question."""
    return _ask(build_user_prompt(question))


def fix_sql(question: str, bad_sql: str, error: str) -> str:
    """Ask the model to correct a query that failed with a database error."""
    return _ask(build_retry_prompt(question, bad_sql, error))


if __name__ == "__main__":
    question = "Which 5 artists have the most albums?"
    print(f"Model: {MODEL}")
    print(f"Question: {question}\n")
    print(generate_sql(question))