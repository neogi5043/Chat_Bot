import pandas as pd
import json
from datetime import datetime
import time
from src.common import llm  # Import local llm.py
from src.common import db   # Import local db.py
from src.prompts.prompt import INSIGHTS_GENERATION_PROMPT
from . import post_execution_analyzer as analyzer

# Simple query logger
class QueryLogger:
    def __init__(self):
        self.queries = []
    
    def log(self, query, sql, success, error_msg=None, exec_time=None, retry_info=None):
        """Log query execution"""
        self.queries.append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "sql": sql,
            "success": success,
            "error": error_msg,
            "exec_time_ms": exec_time,
            "retry_info": retry_info
        })
    
    def get_stats(self):
        """Get execution statistics"""
        if not self.queries:
            return {"total": 0, "success": 0, "failure": 0, "success_rate": 0}
        
        total = len(self.queries)
        success = sum(1 for q in self.queries if q["success"])
        
        return {
            "total": total,
            "success": success,
            "failure": total - success,
            "success_rate": round((success / total) * 100, 2)
        }
    
    def get_recent_failures(self, n=5):
        """Get recent failed queries"""
        failures = [q for q in self.queries if not q["success"]]
        return failures[-n:]

# Initialize logger
logger = QueryLogger()


def is_result_empty_or_null(df):
    """
    Check if result is empty or contains only NULL/None values
    """
    if df is None or df.empty:
        return True
    
    # Check if all values are None/NULL
    # This handles cases where query returns a row but with NULL values
    if len(df) == 1 and len(df.columns) == 1:
        value = df.iloc[0, 0]
        if pd.isna(value) or value is None:
            return True
    
    return False



from src.agents.orchestrator import TextToSQLOrchestrator

# Initialize Global Orchestrator
orchestrator = TextToSQLOrchestrator()

def pipeline(query_request, verbose=True):
    """
    New Entry Point: Delegates to TextToSQLOrchestrator.
    """
    start_time = time.time()
    
    if verbose:
        print(f"\n[PIPELINE] Processing: {query_request}")
    
    # 1. Intent Classification (Legacy check for greeting)
    # We can keep using llm.classify_intent or better, force the orchestrator to handle it.
    # For now, let's fast-track greetings to keep it cheap.
    intent = llm.classify_intent(query_request)
    if intent == "general_conversation":
         response = llm.handle_general_conversation(query_request)
         return None, None, response, "general"

    # Delegate to Orchestrator
    try:
        response = orchestrator.process_query(query_request)
        
        duration = time.time() - start_time
        
        if response["success"]:
            # Success
            result_data = response["data"]
            sql_query = response["sql"]
            
            # Convert to DataFrame for app.py compatibility
            df = pd.DataFrame(result_data) if result_data else pd.DataFrame()
            
            # Generate insights
            if verbose: print("[PIPELINE] Generating insights...")
            from src.common.llm import generate_insights
            insight = generate_insights(result_data, query_request)
            
            if verbose:
                print(f"[PIPELINE] Success in {duration:.2f}s")
            
            return sql_query, df, insight, "sql"
            
        else:
            # Failure
            error_msg = response.get("error", "Unknown error")
            sql = response.get("sql", "")
            if verbose:
                print(f"[PIPELINE] Failed: {error_msg}")
            
            err_df = pd.DataFrame([[error_msg]], columns=["Error"])
            return sql, err_df, None, "error"

    except Exception as e:
        print(f"[PIPELINE] Critical Error: {e}")
        err_df = pd.DataFrame([[str(e)]], columns=["Error"])
        return "", err_df, None, "error"


def get_stats():
    """
    Returns system statistics.
    """
    return {
        "cache_hits": 0,
        "feedback_count": len(orchestrator.feedback_manager.history),
        "few_shot_count": len(orchestrator.feedback_manager.few_shots)
    }

def show_recent_failures():
    """Show recent failures (from FeedbackManager)"""
    failures = orchestrator.feedback_manager.get_similar_feedback("", top_k=5)[1] # get incorrect
    if not failures:
        print("No recent failures logged.")
        return

    print("\nRECENT FAILURES (from Feedback History):")
    for f in failures:
        print(f"- {f.get('query')}: {f.get('error')}")



def main():
    # Test queries including the problematic ones
    test_queries = [
        "Who are you?"
    ]
    
    for query in test_queries:
        print(f"\n\n{'='*80}")
        print(f"QUERY: {query}")
        print(f"{'='*80}")
        
        sql_query, df, insights, query_type = pipeline(query)

        if query_type == "general":
            print("\nType: General Conversation")
            print(f"\nResponse:\n{insights}")
            
        elif query_type == "sql":
            print("\nType: SQL Query")
            print(f"\nGenerated SQL:\n{sql_query}")
            print(f"\n{'='*80}")
            
            # Show results
            if df is not None and not df.empty:
                print("\nResults:")
                print(df.to_string())
            
            print(f"\n{'='*80}")
            
            # Display Insights
            if insights:
                print(f"\nInsights:\n{insights}")
            
        else:
            print("\nType: Error")
            print(f"\nError Details:")
            if df is not None:
                print(df.to_string())
    
    # Show statistics
    print(f"\n\n{'='*80}")
    print("SESSION STATISTICS")
    print(f"{'='*80}")
    stats = get_stats()
    print(f"\nQuery Stats: {stats['query_stats']}")
    print(f"Cache Stats: {stats['cache_stats']}")
    
    # Show failures if any
    show_recent_failures()


if __name__ == "__main__":
    main()