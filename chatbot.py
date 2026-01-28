import pandas as pd
import json
from datetime import datetime
import time
import llm  # Import local llm.py
import db   # Import local db.py
from prompt import INSIGHTS_GENERATION_PROMPT
import post_execution_analyzer as analyzer

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



def pipeline(query_request, verbose=True):
    """
    Improved pipeline with:
    1. Validation before execution
    2. Better error handling
    3. Execution monitoring
    4. Empty/NULL result analysis and retry
    """
    start_time = time.time()
    
    try:
        # 1. Classify Intent
        intent = llm.classify_intent(query_request)
        
        # 2. Handle based on intent
        if intent == "general_conversation":
            # Handle conversational queries without SQL
            response = llm.handle_general_conversation(query_request)
            return None, None, response, "general"
        
        # 3. For SQL queries, proceed with improved flow
        if verbose: print("\n[PIPELINE] Generating SQL...")
        sql_query = llm.generate_sql(query_request)
        
        if not sql_query or len(sql_query.strip()) == 0:
            error_msg = "Failed to generate SQL query"
            logger.log(query_request, sql_query, False, error_msg)
            err_df = pd.DataFrame([[error_msg]], columns=["Error"])
            return None, err_df, None, "error"

        # 4. Run SQL with error handling
        if verbose: print("[PIPELINE] Executing SQL...")
        try:
            df = db.run_query(sql_query)
        except Exception as exec_error:
            error_msg = f"SQL Execution Error: {str(exec_error)}"
            if verbose: print(f"[ERROR] {error_msg}")
            
            exec_time = (time.time() - start_time) * 1000
            logger.log(query_request, sql_query, False, error_msg, exec_time)
            
            err_df = pd.DataFrame([[error_msg]], columns=["Error"])
            return sql_query, err_df, None, "error"

        # 5. Handle empty OR NULL results with intelligent retry
        if is_result_empty_or_null(df):
            if verbose: print("[EMPTY/NULL RESULT] Analyzing why query returned no usable results...")
            
            # Get schema for analysis
            db_structure = db.fetch_schema()
            
            # Try to suggest a better query
            suggested_sql, explanation = analyzer.analyze_empty_result(
                sql_query, 
                db_structure,
                db_connection=db.get_sqlalchemy_engine()
            )
            
            if suggested_sql and suggested_sql != sql_query:
                if verbose:
                    print(f"[RETRY] {explanation}")
                    print(f"[RETRY] Trying improved query...")
                    print(f"[RETRY SQL] {suggested_sql[:200]}...")
                
                try:
                    df_retry = db.run_query(suggested_sql)
                    
                    # Check if retry gave us better results
                    if df_retry is not None and not is_result_empty_or_null(df_retry):
                        if verbose: print(f"[RETRY SUCCESS] Found results with improved query!")
                        
                        exec_time = (time.time() - start_time) * 1000
                        logger.log(query_request, suggested_sql, True, None, exec_time, 
                                 retry_info={"original_sql": sql_query, "reason": explanation})
                        
                        # Generate insights with the successful query
                        insights = llm.generate_insights(df_retry, original_query=query_request)
                        
                        # Add explanation about the correction
                        insights = f"{insights}\n\n(Note: Used fuzzy matching to find closest match)"
                        
                        return suggested_sql, df_retry, insights, "sql"
                    else:
                        if verbose: print("[RETRY] Still no usable results with improved query")
                        
                except Exception as retry_error:
                    if verbose: print(f"[RETRY FAILED] {str(retry_error)}")
            
            # If retry didn't work, provide helpful feedback
            exec_time = (time.time() - start_time) * 1000
            logger.log(query_request, sql_query, True, None, exec_time)
            
            # LOG FEEDBACK (PENALIZE) - Empty result is likely a strict/bad query
            llm.feedback_manager.log_feedback(query_request, sql_query, False, "Returned empty/null result")
            
            # Try to get available values to show user
            where_values = analyzer.extract_where_values(sql_query)
            
            message = "Query executed but returned no results. "
            
            if where_values and db.get_sqlalchemy_engine():
                for column, value in where_values[:20]:  # Show feedback for first 20 columns
                    try:
                        available = analyzer.get_available_values(
                            db.get_sqlalchemy_engine(),
                            sql_query,
                            column,
                            db_structure,
                            limit=10
                        )
                        if available:
                            col_display = column.split('.')[-1] if '.' in column else column
                            message += f"\n\nAvailable {col_display} values: {', '.join(map(str, available[:5]))}"
                            if len(available) > 5:
                                message += f" (and {len(available) - 5} more)"
                    except Exception as e:
                        if verbose: print(f"Could not fetch available values: {e}")
            
            df = pd.DataFrame([[message]], columns=["Message"])
            return sql_query, df, None, "sql"

        # 6. Generate Insights for successful queries
        if verbose: print("[PIPELINE] Generating insights...")
        insights = llm.generate_insights(df, original_query=query_request)
        
        # Log success
        exec_time = (time.time() - start_time) * 1000
        logger.log(query_request, sql_query, True, None, exec_time)
        
        # LOG FEEDBACK (GRATIFY)
        llm.feedback_manager.log_feedback(query_request, sql_query, True)
        
        if verbose: print(f"[SUCCESS] Query completed in {exec_time:.0f}ms")

        return sql_query, df, insights, "sql"
    
    except Exception as e:
        error_msg = f"Pipeline Error: {str(e)}"
        if verbose: print(f"[ERROR] {error_msg}")
        
        exec_time = (time.time() - start_time) * 1000
        logger.log(query_request, "", False, error_msg, exec_time)
        
        # LOG FEEDBACK (PENALIZE) - If we have a generated SQL but execution failed
        if 'sql_query' in locals() and sql_query:
            llm.feedback_manager.log_feedback(query_request, sql_query, False, error_msg)
        
        err_df = pd.DataFrame([[error_msg]], columns=["Error"])
        return None, err_df, None, "error"


def get_stats():
    """Get pipeline statistics"""
    return {
        "query_stats": logger.get_stats(),
        "cache_stats": llm.get_cache_stats(),
        "learning_stats": llm.feedback_manager.get_score_stats()
    }


def show_recent_failures():
    """Show recent failures for debugging"""
    failures = logger.get_recent_failures()
    if not failures:
        print("No recent failures!")
        return
    
    print("\nRECENT FAILURES:")
    print("=" * 80)
    for i, failure in enumerate(failures, 1):
        print(f"\n{i}. Query: {failure['query']}")
        print(f"   SQL: {failure['sql'][:100]}...")
        print(f"   Error: {failure['error']}")
        print(f"   Time: {failure['timestamp']}")


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