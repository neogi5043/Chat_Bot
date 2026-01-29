from agents.orchestrator import TextToSQLOrchestrator
import json

def test_orchestrator():
    print("Initializing Orchestrator...")
    orchestrator = TextToSQLOrchestrator()
    
    # Test Query 1: Simple
    query = "Show me the project budget for Phoenix Implementation"
    print(f"\nRunning Query: {query}")
    result = orchestrator.process_query(query)
    
    print("\nResult:")
    print(json.dumps(result, indent=2, default=str))

    # Test Query 2: Complex (Decomposition mostly)
    query2 = "Compare budget of Project Phoenix and Digital Transformation"
    print(f"\nRunning Query: {query2}")
    result2 = orchestrator.process_query(query2)
    print("\nResult:")
    print(json.dumps(result2, indent=2, default=str))

if __name__ == "__main__":
    test_orchestrator()
