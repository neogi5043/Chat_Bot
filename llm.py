import os
import json
import re
from langchain_groq.chat_models import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import db  # Import our local db.py file
from prompt import INSIGHTS_GENERATION_PROMPT
from sql_prompts import SQL_GENERATION_PROMPT
import validation
import feedback

import cache
import few_shot

load_dotenv()

# Initialize managers
query_cache = cache.QueryCache(ttl_seconds=3600)
feedback_manager = feedback.FeedbackManager()


def classify_intent(query):
    """Classifies user intent as 'sql_query' or 'general_conversation'"""
    
    model = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="meta-llama/llama-4-maverick-17b-128e-instruct",
        temperature=0.1,
        max_tokens=50
    )
    
    system_prompt = """You are an intent classifier for a Demand Management System chatbot.

Classify the user's message as one of these intents:
- "sql_query": User wants data/information from the database (demands, users, statistics, reports, etc.)
- "general_conversation": Greetings, clarifications, general questions, chitchat, or questions about the system itself

CRITICAL RULES:
- Respond with ONLY ONE WORD: either "sql_query" or "general_conversation"
- No explanations, no punctuation, just the classification

EXAMPLES:
"hi" → general_conversation
"hello there" → general_conversation
"what is this?" → general_conversation
"what can you do?" → general_conversation
"how does this work?" → general_conversation
"list all open demands" → sql_query
"show me demands for digital engineering" → sql_query
"how many users are there?" → sql_query
"what is the average fulfillment time?" → sql_query
"tell me about my demands" → sql_query"""

    human_prompt = f"""Classify this user message:
"{query}"

Classification:"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    response = model.invoke(messages)
    classification = response.content.strip().lower()
    
    # Default to general_conversation if unclear
    if "sql" in classification:
        return "sql_query"
    else:
        return "general_conversation"


def handle_general_conversation(query):
    """Handles general conversational queries that don't require database access"""
    
    model = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="meta-llama/llama-4-maverick-17b-128e-instruct",
        temperature=0.7,
        max_tokens=200
    )
    
    system_prompt = """You are a helpful assistant for a Demand Management System chatbot.

Your role:
- Answer general questions about the system
- Provide friendly greetings and responses
- Explain what the system can do when asked
- Keep responses concise (2-3 sentences maximum)
- Be professional but conversational

The system capabilities:
- Query demand information (open/closed demands, by practice, by technology)
- Get user and candidate information
- Calculate statistics (fulfillment times, averages, counts)
- Track demand lifecycle phases
- Analyze practices and technologies

IMPORTANT:
- For greetings: Be warm and brief
- For "what can you do" questions: Mention key capabilities
- For unclear questions: Ask for clarification
- For data questions: Encourage them to ask specific queries about demands, users, or statistics"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query)
    ]
    
    response = model.invoke(messages)
    return response.content


def clean_sql(sql_text):
    """Removes Markdown fencing (```sql) from LLM output"""
    cleaned = re.sub(r"^```sql\s*|\s*```$", "", sql_text.strip(), flags=re.MULTILINE)
    return cleaned.strip()

def generate_sql(query_request, user_email=None):
    """
    Generates SQL using Groq with improvements:
    1. Checks cache first
    2. Uses few-shot examples
    3. Validates output
    4. Auto-corrects if needed
    5. Learns from feedback (Gratify/Penalize)
    """
    
    # STEP 1: Check cache
    cached_sql = query_cache.get(query_request)
    if cached_sql:
        return cached_sql
    
    # STEP 2: Use Semantic Layer (Load schema + valid values)
    db_structure = db.fetch_schema()
    
    # Try to load semantic values
    semantic_values = {}
    try:
        with open('semantic_schema.json', 'r') as f:
            semantic_values = json.load(f)
    except Exception:
        pass  # It's okay if file doesn't exist yet

    # STEP 3: Get relevant few-shot examples (Static)
    relevant_examples = few_shot.get_relevant_examples(query_request)
    examples_text = few_shot.format_examples(relevant_examples)
    
    # STEP 3.5: Get Dynamic Feedback Examples (RLHF)
    correct_history, incorrect_history = feedback_manager.get_similar_feedback(query_request)
    
    feedback_context = ""
    if correct_history:
        feedback_context += "\n\nCORRECT EXAMPLES FROM HISTORY (DO THIS):\n"
        for item in correct_history:
            feedback_context += f"Q: {item['query']}\nSQL: {item['sql']}\n\n"
            
    if incorrect_history:
        feedback_context += "\n\nAVOID THESE MISTAKES (PREVIOUSLY FAILED):\n"
        for item in incorrect_history:
            feedback_context += f"Q: {item['query']}\nBAD SQL: {item['sql']}\nError: {item['error']}\n\n"
    
    # STEP 4: Format schema with valid values
    schema_text = "TABLES AND COLUMNS:\n"
    for table_name, columns in db_structure["tables"].items():
        schema_text += f"\nTABLE: {table_name}\n"
        for col_name, col_type in columns.items():
            schema_text += f"  - {col_name} ({col_type})"
            
            # Inject valid values if available
            if table_name in semantic_values and col_name in semantic_values[table_name]:
                vals = semantic_values[table_name][col_name]
                # Only show if not too many, or just show first 10
                if len(vals) > 0:
                    schema_text += f" -> Valid Values: {str(vals[:20])}"
            schema_text += "\n"
    
    if db_structure["relationships"]:
        schema_text += "\nRELATIONSHIPS:\n"
        for rel in db_structure["relationships"]:
            schema_text += f"  - {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}\n"

    # STEP 5: Generate SQL with Chain of Thought
    model = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="meta-llama/llama-4-maverick-17b-128e-instruct", 
        temperature=0.01,
        max_tokens=1024  # Increased for CoT
    )

    user_context = ""
    if user_email:
        user_context = f"\n\nCurrent user email: {user_email}\nWhen the query references 'my' or 'I', filter by this email."

    human_prompt = f"""Database Schema & Valid Values:
{schema_text}

{examples_text}

{feedback_context}

{user_context}

User Question:
{query_request}

Generate the SQL now."""

    print("\n[DEBUG] Schema Context Sent to LLM:")
    print("-" * 40)
    print(schema_text) # Print FULL schema
    if feedback_context:
        print("\n[DEBUG] Feedback Injected:")
        print(feedback_context)
    print("-" * 40)

    messages = [
        SystemMessage(content=SQL_GENERATION_PROMPT),
        HumanMessage(content=human_prompt)
    ]

    response = model.invoke(messages)
    
    # Clean up response (extract SQL from CoT)
    content = response.content
    
    # Method 1: Remove the /* ... */ block if it exists
    # Non-greedy match for the comment block
    sql_clean = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL).strip()
    
    # Method 2: If Method 1 left nothing or failed, try finding SELECT
    if not sql_clean:
         # Fallback: look for the part after reasoning
        sql_match = re.search(r'(SELECT\s+.*)', content, re.IGNORECASE | re.DOTALL)
        if sql_match:
            sql_query = clean_sql(sql_match.group(1))
        else:
             sql_query = clean_sql(content)
    else:
        sql_query = clean_sql(sql_clean)
    
    # STEP 6: Validate SQL
    is_valid, errors = validation.validate_sql(sql_query, db_structure)
    
    if not is_valid:
        print(f"[VALIDATION FAILED] Errors: {errors}")
        
        # Try auto-fix
        fixed_sql = validation.attempt_fix(sql_query, errors, db_structure)
        if fixed_sql:
            print("[AUTO-FIX] Successfully corrected SQL")
            sql_query = fixed_sql
        else:
            # Try one retry with error feedback
            print("[RETRY] Attempting to regenerate SQL with error feedback")
            sql_query = _retry_with_feedback(query_request, sql_query, errors, db_structure)
    
    # STEP 7: Cache the result
    query_cache.set(query_request, sql_query)
    
    return sql_query


def _retry_with_feedback(original_query, failed_sql, errors, db_structure):
    """
    Retry SQL generation with error feedback
    Simple version - just one retry
    """
    schema_text = "TABLES:\n"
    for table_name, columns in db_structure["tables"].items():
        schema_text += f"\n{table_name}: {', '.join(columns.keys())}\n"
    
    model = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="meta-llama/llama-4-maverick-17b-128e-instruct", 
        temperature=0.01,
        max_tokens=512
    )
    
    correction_prompt = f"""You generated this SQL which has errors:

{failed_sql}

ERRORS FOUND:
{chr(10).join([f"- {err}" for err in errors])}

Database Schema:
{schema_text}

Original Question: {original_query}

FIX the SQL to address these errors. Return ONLY the corrected SQL."""

    messages = [
        SystemMessage(content=SQL_GENERATION_PROMPT),
        HumanMessage(content=correction_prompt)
    ]
    
    response = model.invoke(messages)
    corrected_sql = clean_sql(response.content)
    
    # Validate the corrected version
    is_valid, new_errors = validation.validate_sql(corrected_sql, db_structure)
    
    if is_valid:
        print("[RETRY SUCCESS] Corrected SQL is valid")
        return corrected_sql
    else:
        print(f"[RETRY FAILED] Still has errors: {new_errors}")
        # Return corrected version anyway - might work at execution
        return corrected_sql


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


def get_cache_stats():
    """Get cache statistics - useful for monitoring"""
    return query_cache.get_stats()


def clear_cache():
    """Clear the query cache - useful for testing"""
    query_cache.clear()