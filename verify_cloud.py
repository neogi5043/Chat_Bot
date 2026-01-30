
import sys
import os
import io

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from agents.orchestrator import TextToSQLOrchestrator

def main():
    print("Testing 'Cloud and DevOps' Query...")
    # Initialize Orchestrator
    orchestrator = TextToSQLOrchestrator()
    
    query = "What is the average fulfillment time for Cloud and devops"
    print(f"\nQuery: {query}")
    
    try:
        result = orchestrator.process_query(query)
        print(f"Success: {result['success']}")
        sql = result.get('sql', '')
        print(f"SQL: {sql}")
        
        # Check if it uses the correct join
        if "JOIN practices" in sql and "practice_name" in sql:
            print("[PASS] Correctly used practice join.")
        else:
            print("[FAIL] Used incorrect logic (likely job_description filter).")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()
