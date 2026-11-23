"""Send a question to the LLM and get a SQL string back."""
import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.prompt import build_retry_prompt, build_system_prompt, build_user_prompt

load_dotenv()  # load values from the .env file

MODEL = os.getenv("LLM_MODEL", "gemini-3.1-flash-lite")
# Backup models, tried in order when the main model keeps failing (e.g. 503 overloaded).
FALLBACK_MODELS = [m.strip() for m in os.getenv("LLM_FALLBACKS", "").split(",") if m.strip()]
PROMPT_VARIANT = os.getenv("PROMPT_VARIANT", "basic")

ATTEMPTS_PER_MODEL = 3       # tries per model before moving to the next one
REQUEST_TIMEOUT_MS = 30_000  # give up on a single request after 30 seconds

_client = None
_system_prompt = None

# Which model produced the last answer. The evaluation records this, so a result
# is never credited to the main model when a fallback model actually answered.
last_model_used: str | None = None


def _get_client() -> genai.Client:
    """Create the API client once and reuse it."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )
    return _client


def clean_sql(text: str) -> str:
    """Remove markdown code fences and surrounding whitespace from model output."""
    text = text.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    return text.strip()


def _ask(user_prompt: str) -> str:
    """Send one request. Retry on failure, then try the fallback models."""
    global _system_prompt, last_model_used
    if _system_prompt is None:
        _system_prompt = build_system_prompt(variant=PROMPT_VARIANT)

    last_error = None
    for model in [MODEL] + FALLBACK_MODELS:
        for attempt in range(ATTEMPTS_PER_MODEL):
            try:
                response = _get_client().models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_system_prompt,
                        temperature=0,
                    ),
                )
                last_model_used = model
                return clean_sql(response.text or "")
            except Exception as exc:  # overload (503), rate limit (429), timeout, network
                last_error = exc
                print(f"  [{model}] attempt {attempt + 1} failed: {str(exc)[:80]}", flush=True)
                time.sleep(2 ** attempt)  # wait 1 s, 2 s, 4 s
    raise RuntimeError(f"All models failed. Last error: {last_error}")


def generate_sql(question: str) -> str:
    """Ask the model for a SQL query that answers the question."""
    return _ask(build_user_prompt(question))


def fix_sql(question: str, bad_sql: str, error: str) -> str:
    """Ask the model to correct a query that failed with a database error."""
    return _ask(build_retry_prompt(question, bad_sql, error))


if __name__ == "__main__":
    question = "Which 5 artists have the most albums?"
    print(f"Model: {MODEL} (fallbacks: {FALLBACK_MODELS or 'none'}), prompt: {PROMPT_VARIANT}")
    print(f"Question: {question}\n")
    print(generate_sql(question))
    print(f"\n(answered by {last_model_used})")
