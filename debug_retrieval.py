
import sys
import os
import io

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from agents.orchestrator import TextToSQLOrchestrator

def main():
    print("Testing Retrieval...")
    # Initialize Orchestrator
    orchestrator = TextToSQLOrchestrator()
    
    # Failing Query
    query = "What is the average fulfillment time for Cloud and devops"
    print(f"\nQuery: {query}")
    
    # Process
    try:
        # We only care about the first few steps, but process_query does it all
        result = orchestrator.process_query(query)
        print(f"Generated SQL: {result.get('sql')}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()
