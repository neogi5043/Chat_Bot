
import sys
import os
import io

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from agents.orchestrator import TextToSQLOrchestrator

def main():
    print("Testing Generic Resume Ratio Query...")
    orchestrator = TextToSQLOrchestrator()
    
    query = "What is the resume intake to select ratio?"
    print(f"\nQuery: {query}")
    
    try:
        result = orchestrator.process_query(query)
        print(f"Success: {result['success']}")
        sql = result.get('sql', '')
        print(f"SQL: {sql}")
        
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()
