import os
import json
import re
from langchain_groq.chat_models import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import db  # Import our local db.py file
from prompt import INSIGHTS_GENERATION_PROMPT
from sql_prompts import SQL_GENERATION_PROMPT

load_dotenv()

def clean_sql(sql_text):
    """Removes Markdown fencing (```sql) from LLM output"""
    cleaned = re.sub(r"^```sql\s*|\s*```$", "", sql_text.strip(), flags=re.MULTILINE)
    return cleaned.strip()


def generate_sql(query_request, user_email=None):
    """Generates SQL using Groq based on the DB schema"""
    
    db_structure = db.fetch_schema()
    
    # Format schema in a clearer way
    schema_text = "TABLES AND COLUMNS:\n"
    for table_name, columns in db_structure["tables"].items():
        schema_text += f"\n{table_name}:\n"
        for col_name, col_type in columns.items():
            schema_text += f"  - {col_name} ({col_type})\n"
    
    if db_structure["relationships"]:
        schema_text += "\nTABLE RELATIONSHIPS (Foreign Keys):\n"
        for rel in db_structure["relationships"]:
            schema_text += f"  - {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}\n"

    model = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="meta-llama/llama-4-maverick-17b-128e-instruct", 
        temperature=0.01,
        max_tokens=512
    )

    user_context = ""
    if user_email:
        user_context = f"\n\nCurrent user email: {user_email}\nWhen the query references 'my' or 'I', filter by this email in the users/demands tables."

    human_prompt = f"""Database Schema:
{schema_text}{user_context}

User Question:
{query_request}

Generate a PostgreSQL query following all the rules above. CRITICAL: Verify which table each column belongs to before using it. Return ONLY the SQL query with no explanations."""

    messages = [
        SystemMessage(content=SQL_GENERATION_PROMPT),
        HumanMessage(content=human_prompt)
    ]

    response = model.invoke(messages)
    return clean_sql(response.content)


def generate_insights(result_data, original_query=None):
    """Generates insights from query results using Groq"""
    
    # 1. Convert result data to JSON string if it's a DataFrame
    if hasattr(result_data, 'to_json'):
        data_json = result_data.to_json(orient='records', indent=4)
    elif isinstance(result_data, str):
        data_json = result_data
    else:
        data_json = json.dumps(result_data, indent=4)

    # 2. Initialize Model
    model = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="meta-llama/llama-4-maverick-17b-128e-instruct", 
        temperature=0.3,
        max_tokens=256
    )

    # 3. Construct the human message with data
    human_prompt = f"""Based on the guidelines provided, analyze this data and answer the question directly.

DATASET:
{data_json}

QUESTION:
{original_query if original_query else "Provide key insights from this data."}

Provide your answer now (1-2 sentences maximum with specific numbers):"""

    # 4. Construct Messages
    messages = [
        SystemMessage(content=INSIGHTS_GENERATION_PROMPT),
        HumanMessage(content=human_prompt)
    ]

    # 5. Invoke AI
    response = model.invoke(messages)
    return response.content