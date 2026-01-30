import os
import json
import re
from langchain_groq.chat_models import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

# We can reuse the prompt template or import it if it's external
# For now, defining strict prompt here.

class SQLGeneratorAgent:
    """
    Generates SQL queries step-by-step using:
    1. Decomposed query plan
    2. Selected schema
    3. Resolved entities
    """
    
    def __init__(self, semantic_layer, few_shot_manager=None, model_name="meta-llama/llama-4-maverick-17b-128e-instruct"):
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model=model_name,
            temperature=0.01, # Extremely low temperature for code
            max_tokens=1024
        )
        self.semantic_layer = semantic_layer
        self.few_shot_manager = few_shot_manager
    
    def generate_sql(self, query_plan, selected_schema, entity_resolutions, user_query) -> str:
        
        # Get Few-Shot Examples (Correct & Incorrect)
        correct_examples, incorrect_examples = [], []
        if self.few_shot_manager:
            correct_examples, incorrect_examples = self.few_shot_manager.get_similar_feedback(user_query)

        # Build prompt
        prompt = self._build_generation_prompt(
            user_query=user_query,
            query_plan=query_plan,
            selected_schema=selected_schema,
            entity_resolutions=entity_resolutions,
            business_metrics=self.semantic_layer.business_metrics,
            sql_dialect="PostgreSQL",
            correct_examples=correct_examples,
            incorrect_examples=incorrect_examples
        )
        
        messages = [
            SystemMessage(content="You are an expert PostgreSQL developer. Output ONLY SQL."),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        return self._extract_sql(response.content)

    def _build_generation_prompt(self, user_query, query_plan, selected_schema, entity_resolutions, business_metrics, sql_dialect, correct_examples=None, incorrect_examples=None):
        
        # Format schema
        schema_str = ""
        for table in selected_schema:
            schema_str += f"\nTable: {table.get('business_name', table.get('table_id'))} (ID: {table.get('table_id')})\n"
            schema_str += f"Description: {table.get('description', '')}\n"
            schema_str += "Columns:\n"
            for col_name, col_meta in table.get("columns", {}).items():
                schema_str += f"  - {col_name} ({col_meta.get('type')}): {col_meta.get('description', '')}\n"

        # Format Examples
        examples_str = ""
        if correct_examples:
            examples_str += "\n## Guidelines (Follow these patterns):\n"
            for ex in correct_examples:
                examples_str += f"Q: {ex.get('user_question')}\nSQL: {ex.get('sql')}\n\n"
        
        if incorrect_examples:
            examples_str += "\n## Anti-Patterns (Avoid these mistakes):\n"
            for ex in incorrect_examples:
                examples_str += f"Q: {ex.get('query')}\nBAD SQL: {ex.get('sql')}\nError: {ex.get('error')}\n\n"

        prompt = f"""
# Task: Generate SQL Query

## Database Dialect
{sql_dialect}

## Business Metrics
{json.dumps(business_metrics, indent=2)}

## Schema Information
{schema_str}

## Entity Resolutions (Use these values in WHERE clauses)
{json.dumps(entity_resolutions, indent=2)}

## Query Decomposition Plan
{json.dumps(query_plan.get('steps', []), indent=2)}
{examples_str}
## Your Task
Generate SQL for this question: "{user_query}"

Requirements:
- Use ONLY tables/columns present in the schema above.
- Apply entity resolutions where provided.
- Match {sql_dialect} syntax.
- Output only the SQL query without markdown or explanation.
"""
        return prompt

    def _extract_sql(self, llm_response: str) -> str:
        """Extract SQL from LLM response (handles markdown, etc.)"""
        import re
        sql_match = re.search(r'```(?:sql)?\n(.*?)\n```', llm_response, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        
        # Fallback: remove simple code blocks
        clean = llm_response.replace("```sql", "").replace("```", "").strip()
        return clean
