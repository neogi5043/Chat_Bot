
import sys
import os
import time
from chatbot import pipeline

def run_tests_from_file(filename="test.txt"):
    if not os.path.exists(filename):
        print(f"Error: {filename} not found.")
        return

    with open(filename, "r") as f:
        queries = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(queries)} tests.\n")

    failures = []
    
    for i, query in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] Testing: {query}")
        
        # Rate limit protection
        time.sleep(60)
        
        try:
            # We don't care about the output insights here, just if SQL generation/execution works
            # The pipeline returns: sql, df, insights, intent
            sql, df, insights, intent = pipeline(query, verbose=False)
            
            if intent == "error":
                print(f"  FAILED: {sql}") 
                failures.append({"query": query, "error": sql if isinstance(sql, str) else "Unknown Error"})
            elif intent == "sql" and (df is None): # Empty dataframe is fine (0 results), None is not
                 print(f"  FAILED: No DataFrame returned")
                 failures.append({"query": query, "error": "No data returned"})
            else:
                row_count = len(df) if df is not None else 0
                print(f"  PASSED: {row_count} rows")
                
        except Exception as e:
            print(f"  CRITICAL ERROR: {e}")
            failures.append({"query": query, "error": str(e)})
        
        print("-" * 40)

    print(f"\nSummary: {len(queries) - len(failures)}/{len(queries)} Passed")
    
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"- {f['query']} -> {f['error']}")

if __name__ == "__main__":
    run_tests_from_file()
