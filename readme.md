# Code Review and Improvement Plan for NL→SQL→Insights Pipeline

## Executive Summary

This project implements a natural-language-to-SQL chatbot that:

- Infers PostgreSQL queries from user questions via Groq (LLM).
- Executes those queries against a PostgreSQL database.
- Generates concise, metric-focused insights from the result set.

The core architecture is solid and modular:

- `db.py` handles database connectivity and schema discovery.
- `llm.py` manages prompt construction and interaction with Groq.
- `prompt.py` defines the insights generation system prompt.
- `chatbot.py` orchestrates the end-to-end pipeline.

However, several areas can be improved to enhance **reliability**, **performance**, **cost efficiency**, and **maintainability**, especially considering constraints like **limited API budget (≈200 calls/day)** and **single-developer maintenance**.

This document details targeted recommendations and example code changes.

---

## 1. Database Layer (`db.py`) Improvements

### 1.1 Connection Management and Pooling

**Current state:**

- `get_connection()` creates a new raw `psycopg2` connection each time.
- `get_sqlalchemy_engine()` creates a new SQLAlchemy engine on demand.
- Connections are not pooled or reused.

This can lead to:

- Connection exhaustion under moderate load.
- Higher latency due to repeated connection setup.

**Recommendations:**

1. **Use SQLAlchemy connection pooling** for all query execution.
2. Prefer a single, reusable engine instead of creating a new one per query.

**Example refactor:**

```python
# db.py
import psycopg2
import pandas as pd
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

load_dotenv()

_ENGINE = None


def get_connection():
    """Establishes a raw connection to PostgreSQL (use sparingly)."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=os.getenv("DB_PORT"),
    )


def get_sqlalchemy_engine():
    """Returns a global SQLAlchemy engine with connection pooling."""
    global _ENGINE
    if _ENGINE is None:
        db_url = (
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        )
        _ENGINE = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _ENGINE
```

### 1.2 Robust Schema Fetching

**Current state:**

- `fetch_schema()` reads from `information_schema` without error handling.
- It returns a nested dict with `tables` and `relationships`.

**Recommendations:**

- Wrap the logic with try/finally to ensure cursor/connection cleanup.
- Add basic logging and graceful failure behavior.

**Improved version (structure-level):**

```python
import logging

logger = logging.getLogger(__name__)


def fetch_schema():
    """Fetches table/column metadata and foreign key relationships."""
    conn = None
    cursor = None
    db_structure = {"tables": {}, "relationships": []}

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Tables
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
            """
        )
        tables = cursor.fetchall()

        # Columns per table
        for (table_name,) in tables:
            cursor.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position;
                """,
                (table_name,),
            )
            columns = cursor.fetchall()
            db_structure["tables"][table_name] = {col[0]: col[1] for col in columns}

        # Foreign-key relationships
        cursor.execute(
            """
            SELECT
                tc.table_name AS from_table,
                kcu.column_name AS from_column,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.column_name;
            """
        )
        relationships = cursor.fetchall()

        for rel in relationships:
            db_structure["relationships"].append(
                {
                    "from_table": rel[0],
                    "from_column": rel[1],
                    "to_table": rel[2],
                    "to_column": rel[3],
                }
            )

        return db_structure

    except Exception as e:
        logger.error(f"Failed to fetch schema: {e}", exc_info=True)
        return db_structure  # Return whatever is available

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
```

### 1.3 Safer Query Execution

**Current state:**

```python
def run_query(sql):
    engine = None
    try:
        engine = get_sqlalchemy_engine()
        df = pd.read_sql(sql, engine)
        return df
    except Exception as e:
        print(f"Error running query: {e}")
        return None
    finally:
        if engine:
            engine.dispose()
```

Issues:

- Engine is disposed after each query (negates pooling benefit).
- Errors are printed but not structured/logged.

**Improved version:**

```python
def run_query(sql: str) -> pd.DataFrame | None:
    """Executes a SQL query and returns a DataFrame or None on failure."""
    engine = get_sqlalchemy_engine()
    try:
        logger.info(f"Executing query (truncated): {sql[:200]}")
        df = pd.read_sql(sql, engine)
        if df.empty:
            logger.warning("Query returned an empty result set.")
        return df
    except Exception as e:
        logger.error(f"Error running query: {e}\nSQL: {sql}", exc_info=True)
        return None
```

Engine is now reused and not disposed on every call.

---

## 2. LLM Layer (`llm.py`) Improvements

### 2.1 Centralized Schema Caching

**Current state:**

- `generate_sql()` calls `db.fetch_schema()` directly for every request.
- This introduces a heavy DB hit and latency before every LLM call.

**Recommendation:**

Implement a simple, time-based cache for the schema. This is critical for:

- Reducing DB calls.
- Improving latency.
- Staying within your daily API and infrastructure budgets.

**Example implementation:**

```python
# llm.py
import os
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from langchain_groq.chat_models import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

import db
from prompt import INSIGHTS_GENERATION_PROMPT
from sql_prompts import SQL_GENERATION_PROMPT

load_dotenv()

_SCHEMA_CACHE: Dict[str, Any] = {"data": None, "timestamp": None}
_SCHEMA_TTL_MINUTES = 60


def _get_schema_cached() -> Dict[str, Any]:
    now = datetime.now()
    if (
        _SCHEMA_CACHE["data"] is None
        or _SCHEMA_CACHE["timestamp"] is None
        or (now - _SCHEMA_CACHE["timestamp"]) > timedelta(minutes=_SCHEMA_TTL_MINUTES)
    ):
        _SCHEMA_CACHE["data"] = db.fetch_schema()
        _SCHEMA_CACHE["timestamp"] = now
    return _SCHEMA_CACHE["data"]
```

Now use `_get_schema_cached()` inside `generate_sql()` instead of calling `db.fetch_schema()` directly.

### 2.2 SQL Generation and Cleaning

Your existing `clean_sql()` is conceptually correct. Keep it, but add more robust handling for stray backticks/whitespace.

```python
def clean_sql(sql_text: str) -> str:
    """Removes Markdown fencing (```sql ... ```) from LLM output."""
    cleaned = re.sub(r"^```sql\s*|^```\s*|```$", "", sql_text.strip(), flags=re.MULTILINE)
    return cleaned.strip()
```

### 2.3 SQL Safety and Validation

To avoid destructive or unexpected queries from the LLM, enforce simple constraints:

```python
DANGEROUS_KEYWORDS = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE"]


def _validate_sql(sql: str) -> None:
    upper_sql = sql.upper()

    if not upper_sql.startswith("SELECT"):
        raise ValueError("Only SELECT statements are allowed.")

    if any(kw in upper_sql for kw in DANGEROUS_KEYWORDS):
        raise ValueError("Detected potentially dangerous SQL statement.")
```

Integrate into `generate_sql()`:

```python
def generate_sql(query_request: str, user_email: Optional[str] = None) -> str:
    db_structure = _get_schema_cached()

    # Build schema text
    schema_text = "TABLES AND COLUMNS:\n"
    for table_name, columns in db_structure["tables"].items():
        schema_text += f"\n{table_name}:\n"
        for col_name, col_type in columns.items():
            schema_text += f" - {col_name} ({col_type})\n"

    if db_structure["relationships"]:
        schema_text += "\nTABLE RELATIONSHIPS (Foreign Keys):\n"
        for rel in db_structure["relationships"]:
            schema_text += (
                f" - {rel['from_table']}.{rel['from_column']} → "
                f"{rel['to_table']}.{rel['to_column']}\n"
            )

    user_context = ""
    if user_email:
        user_context = (
            "\n\nCurrent user email: "
            f"{user_email}\nWhen the query references 'my' or 'I', "
            "filter by this email in the appropriate table."
        )

    human_prompt = f"""Database Schema:
{schema_text}{user_context}

User Question:
{query_request}

Generate a PostgreSQL SELECT query following all the rules above.
Return ONLY the SQL query with no explanations."""

    model = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="meta-llama/llama-4-maverick-17b-128e-instruct",
        temperature=0.01,
        max_tokens=512,
    )

    messages = [
        SystemMessage(content=SQL_GENERATION_PROMPT),
        HumanMessage(content=human_prompt),
    ]

    response = model.invoke(messages)
    sql = clean_sql(response.content)
    _validate_sql(sql)
    return sql
```

### 2.4 Insights Generation Efficiency

**Current state:**

- Insights prompt (`INSIGHTS_GENERATION_PROMPT`) is relatively long.
- `max_tokens` is set to 256, which may be more than needed for "1–2 sentence" answers.

**Recommendations:**

- Shorten the system prompt.
- Limit `max_tokens` further to reduce latency and cost.

**Example simplified system prompt (in `prompt.py`):**

```python
INSIGHTS_GENERATION_PROMPT = """
role: SQL Query Results Analyst
objective: Answer the user's question in 1-2 short sentences based on the provided dataset.
rules:
- Always include concrete numerical values from the data.
- No bullet points, no lists.
- Do not explain how you derived the result.
- Start directly with the answer.
"""
```

**Adjusted model call:**

```python
def generate_insights(result_data: Any, original_query: Optional[str] = None) -> str:
    if hasattr(result_data, "to_json"):
        data_json = result_data.to_json(orient="records", indent=2)
    elif isinstance(result_data, str):
        data_json = result_data
    else:
        data_json = json.dumps(result_data, indent=2)

    model = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="meta-llama/llama-4-maverick-17b-128e-instruct",
        temperature=0.3,
        max_tokens=128,  # Reduced from 256
    )

    human_prompt = f"""Analyze this data and answer the question briefly.

DATASET:
{data_json}

QUESTION:
{original_query or "Provide key insights from this data."}

Remember: 1-2 sentences, direct answer, include specific numbers."""

    messages = [
        SystemMessage(content=INSIGHTS_GENERATION_PROMPT),
        HumanMessage(content=human_prompt),
    ]

    response = model.invoke(messages)
    return response.content
```

---

## 3. Pipeline Layer (`chatbot.py`) Improvements

### 3.1 Robust Pipeline with Graceful Degradation

**Current state:**

- Any exception in SQL generation, DB execution, or insights generation is caught at once.
- On exceptions, a generic error DataFrame is returned.

**Recommended behavior:**

- Distinguish failure modes:
  - SQL generation failure.
  - Query execution failure.
  - Insights generation failure.
- Return partial results when possible (e.g., data without insights if only insights step fails).

**Example refactor:**

```python
# chatbot.py
import json
from typing import Optional, Tuple

import pandas as pd

import llm
import db


def pipeline(query_request: str) -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[str]]:
    """Executes the full NL → SQL → DB → insights pipeline.

    Returns:
        sql_query: Generated SQL string or None on failure.
        df: Resulting DataFrame or None on failure.
        insights: Generated insights text or None if not available.
    """
    sql_query: Optional[str] = None
    df: Optional[pd.DataFrame] = None
    insights: Optional[str] = None

    # 1. SQL generation
    try:
        sql_query = llm.generate_sql(query_request)
    except Exception as e:
        error_msg = f"SQL generation failed: {e}"
        error_df = pd.DataFrame([[error_msg]], columns=["Error"])
        return None, error_df, None

    # 2. Run SQL
    df = db.run_query(sql_query)
    if df is None:
        error_df = pd.DataFrame([["Database query failed."]], columns=["Error"])
        return sql_query, error_df, None

    if df.empty:
        msg_df = pd.DataFrame([["No results found."]], columns=["Message"])
        return sql_query, msg_df, "No data matched your query."

    # 3. Insights generation (best-effort)
    try:
        insights = llm.generate_insights(df, original_query=query_request)
    except Exception:
        insights = None

    return sql_query, df, insights


def main() -> None:
    query_request = "list all open demands of digital engineering"
    sql_query, df, insights = pipeline(query_request)

    print("Generated SQL:\n")
    print(sql_query or "<no SQL generated>")
    print("\n" + "=" * 50 + "\n")

    if df is not None:
        json_data = df.to_json(orient="records")
        parsed_json = json.loads(json_data)

        print("Result in JSON:")
        print(json.dumps(parsed_json, indent=4))
    else:
        print("No DataFrame returned.")

    print("\n" + "=" * 50 + "\n")

    if insights:
        print("Insights:")
        print(insights)
    else:
        print("No insights generated.")


if __name__ == "__main__":
    main()
```

### 3.2 Separation of Concerns for UI Layer

If you later add Gradio/FastAPI/Streamlit, keep `pipeline()` framework-agnostic and call it from UI-specific modules. The current structure already supports that, so keep `chatbot.py` as a thin CLI/testing wrapper.

---

## 4. Prompt Design & Token Optimization

Given your **200 LLM calls/day** constraint, prompt design has a direct cost impact.

### 4.1 SQL Prompt (`SQL_GENERATION_PROMPT`)

Ensure that `SQL_GENERATION_PROMPT` is:

- Focused on:
  - Using only columns/tables present in the schema.
  - Preferring simple joins.
  - Returning only the SQL.
- Short enough to not dominate the context window.

Example structure:

```python
SQL_GENERATION_PROMPT = """
You are an expert PostgreSQL query generator.

Follow these rules:
- Use only the tables and columns provided in the schema.
- Use explicit JOINs, not implicit joins.
- Only generate a single SELECT statement.
- Do not modify or delete data.
- Return only the SQL query, with no explanation or commentary.
"""
```

### 4.2 Insights Prompt (`INSIGHTS_GENERATION_PROMPT`)

The simplified version shown earlier is already optimized:

- Lower token usage.
- Clear behavioral constraints.

This yields faster responses and lower cost per call.

---

## 5. Type Hints, Documentation, and Maintainability

To keep the codebase maintainable for a single developer and easy to evolve:

- Add **type hints** to all public functions.
- Write short **docstrings** describing arguments and return types.
- Use a consistent **logging** setup across modules.

**Example:**

```python
# llm.py
from typing import Any, Dict, Optional


def generate_sql(query_request: str, user_email: Optional[str] = None) -> str:
    """Generate a PostgreSQL SELECT query from a natural language request.

    Args:
        query_request: The user's natural language question.
        user_email: Optional email to apply user-specific filters.

    Returns:
        A SELECT SQL string.

    Raises:
        ValueError: If the generated SQL is unsafe or invalid.
    """
    ...
```

---

## 6. Dependency and File Consistency

- `llm.py` imports `from sql_prompts import SQL_GENERATION_PROMPT`, but `sql_prompts.py` is not listed in the attached files.

**Action items:**

- Either create `sql_prompts.py` containing the SQL generation system prompt, or
- Move `SQL_GENERATION_PROMPT` into `prompt.py` and update the import.

Ensure `requirements.txt` is aligned with imports:

```text
langchain-groq
mysql-connector-python
pandas
gradio
python-dotenv
psycopg2
SQLAlchemy
```

If eventually you are only using PostgreSQL, `mysql-connector-python` may be removable unless there is another system depending on it.

---

## 7. Prioritized Implementation Plan

Given limited time and API budget, here is a **practical implementation order**:

1. **Schema caching in `llm.py`**
   - Biggest latency improvement.
   - Reduces repeated DB calls per LLM request.

2. **Connection pooling in `db.py`**
   - Prevents connection exhaustion.
   - Improves performance under concurrent use.

3. **Prompt and token optimization**
   - Lower cost per request.
   - Faster responses.

4. **SQL validation & safety**
   - Protects production data.
   - Mitigates risky LLM outputs.

5. **Robust pipeline error handling**
   - Better UX for users.
   - Clearer debugging for the developer.

6. **Type hints and logging**
   - Long-term code quality and maintainability.

Implementing these steps will give you a **production-ready, cost-aware NL→SQL→Insights microservice** that fits well into your broader multi-agent and BI tooling ecosystem (e.g., future integration with Tableau MCP or Denodo via a thin API layer).
