from .sql_generator import SQLGeneratorAgent

class CorrectionAgent:
    """
    Detects execution failures and attempts automatic correction.
    """
    
    def __init__(self, sql_generator: SQLGeneratorAgent):
        self.sql_generator = sql_generator
    
    def attempt_correction(self, original_sql: str, error_message: str, user_query: str, db_schema_str: str) -> dict:
        """
        Ask LLM to fix the SQL based on the error.
        """
        print(f"Attempting correction for error: {error_message}")
        
        # Reuse the SQL Generator's LLM but with a correction prompt
        prompt = f"""
The following SQL generated an error. Please fix it.

User Question: {user_query}

Original SQL:
{original_sql}

Error Message:
{error_message}

Database Schema:
{db_schema_str}

Provide only the corrected SQL query.
"""
        
        try:
             messages = [
                {"role": "system", "content": "You are a SQL expert. Fix the query directly."},
                {"role": "user", "content": prompt}
             ]
             # HACK: Manually invoking the underlying LLM from sql_generator
             # In robust code we'd use a proper method on the generator or a shared LLM instance
             from langchain_core.messages import HumanMessage, SystemMessage
             
             lc_messages = [
                 SystemMessage(content="You are a SQL expert. Fix the query directly."),
                 HumanMessage(content=prompt)
             ]
             
             response = self.sql_generator.llm.invoke(lc_messages)
             corrected_sql = self.sql_generator._extract_sql(response.content)
             
             return {
                 "success": True,
                 "corrected_sql": corrected_sql,
                 "correction_type": "llm_fix"
             }
             
        except Exception as e:
            print(f"Correction failed: {e}")
            return {"success": False, "message": str(e)}
