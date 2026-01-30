
import sys
import os
import io

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from agents.orchestrator import TextToSQLOrchestrator

def main():
    print("Testing Lifecycle Query...")
    orchestrator = TextToSQLOrchestrator()
    
    query = "What is the most time taking phase in the demand life cycle technology wise?"
    print(f"\nQuery: {query}")
    
    try:
        result = orchestrator.process_query(query)
        print(f"Success: {result['success']}")
        sql = result.get('sql', '')
        print(f"SQL: {sql}")
        
        # Check for joins
        if "JOIN practices" in sql and "demand_activity" in sql:
             print("[PASS] Correctly joins activity and practices.")
        else:
             print("[FAIL] Missing required joins.")
             
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()
