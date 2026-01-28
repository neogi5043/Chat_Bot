import json
import os
from langchain_groq.chat_models import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

class DecomposerAgent:
    """
    Uses LLM to decompose complex natural language queries
    into logical steps and sub-queries.
    """
    
    def __init__(self, model_name="meta-llama/llama-4-maverick-17b-128e-instruct"):
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model=model_name,
            temperature=0.1,
            max_tokens=512
        )
    
    def decompose(self, user_query: str, semantic_layer) -> dict:
        """
        Decompose complex query into logical steps.
        Returns a dict with "steps" list.
        """
        
        prompt = self._build_decomposition_prompt(
            user_query=user_query,
            semantic_layer=semantic_layer
        )
        
        messages = [
            SystemMessage(content="You are a SQL query planner. Output JSON only."),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        # Parse structured output
        try:
            content = response.content.strip()
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            query_plan = json.loads(content)
            return query_plan
        except Exception as e:
            # Fallback for simple queries or parsing errors
            print(f"Decomposition parsing failed: {e}")
            return {"steps": [{"id": 1, "description": "Execute query directly"}]}
            
    
    def _build_decomposition_prompt(self, user_query, semantic_layer):
        prompt = f"""
You are a SQL query planner. Your task is to decompose natural language 
business questions into logical steps.

## Business Context
Business Metrics Available:
{json.dumps(semantic_layer.business_metrics, indent=2)}

## Few-Shot Examples

Example 1:
Q: "Show me monthly revenue trends"
A: {{
  "steps": [
    {{"id": 1, "description": "Group sales by month"}},
    {{"id": 2, "description": "Sum revenue by month"}},
    {{"id": 3, "description": "Order chronologically"}}
  ]
}}

Example 2:
Q: "Compare Q1 sales with Q2 and show growth percentage"
A: {{
  "steps": [
    {{"id": 1, "description": "Calculate Q1 total sales"}},
    {{"id": 2, "description": "Calculate Q2 total sales"}},
    {{"id": 3, "description": "Calculate (Q2-Q1)/Q1 * 100"}},
    {{"id": 4, "description": "Return comparison as single row"}}
  ]
}}

## Your Task
Decompose this query: "{user_query}"

Return a JSON object with "steps" array following the format above.
"""
        return prompt
