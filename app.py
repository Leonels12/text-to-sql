"""Small web interface for the text-to-SQL pipeline.

Run from the project root:  streamlit run app.py
"""
import json
from pathlib import Path

import streamlit as st

import src.llm as llm
from src.pipeline import answer

st.set_page_config(page_title="Text-to-SQL", page_icon="🎵", layout="wide")
st.title("Ask the music store database")
st.caption("Questions in plain English, answered with generated SQL on the Chinook database "
           "(read-only, validated before it runs).")

with st.sidebar:
    st.header("Settings")
    model = st.text_input("Model", value=llm.MODEL)
    variant = st.selectbox("Prompt variant", ["basic", "samples", "fewshot"],
                           index=["basic", "samples", "fewshot"].index(llm.PROMPT_VARIANT)
                           if llm.PROMPT_VARIANT in ("basic", "samples", "fewshot") else 0)
    use_retry = st.checkbox("Retry once on SQL errors", value=True)
    st.divider()
    st.markdown("**Example questions**")
    examples = [q["question"] for q in
                json.loads(Path("tests/test_set.json").read_text(encoding="utf-8"))[::8]]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["question"] = ex

if model != llm.MODEL or variant != llm.PROMPT_VARIANT:
    llm.MODEL, llm.PROMPT_VARIANT = model, variant
    llm._system_prompt = None  # rebuild the prompt with the new settings

question = st.text_input("Your question", key="question",
                         placeholder="Which 5 artists have the most albums?")

if st.button("Ask", type="primary") and question.strip():
    with st.spinner("Generating SQL..."):
        try:
            result = answer(question, use_retry=use_retry)
        except Exception as exc:  # every model failed, e.g. overloaded
            st.error(f"The model could not be reached: {exc}")
            st.stop()

    if result.status == "ok":
        st.success(f"Answered by {llm.last_model_used} in {result.attempts} attempt(s).")
        st.code(result.sql, language="sql")
        rows = [dict(zip(result.result.columns, row)) for row in result.result.rows]
        st.dataframe(rows, use_container_width=True)
        if result.result.truncated:
            st.info("Only the first 200 rows are shown.")
    elif result.status == "blocked":
        st.error(result.message)
        st.code(result.sql, language="sql")
    elif result.status == "cannot_answer":
        st.warning(result.message)
    else:
        st.error(f"The query failed: {result.message}")
        st.code(result.sql, language="sql")
