from agents.orchestrator import TextToSQLOrchestrator
import json

def test_correction_loop():
    print("Initializing Orchestrator for Phase 3 Verification...")
    orchestrator = TextToSQLOrchestrator()
    
    # Test Query 1: Hard query that might fail (or we can inject a failure)
    # The idea is to verify if 'CorrectionAgent' is triggered. 
    # Since we can't easily force a fail without mocking, 
    # we'll look at logs if it works. 
    # But let's try a query with a typo to see if EntityResolver handles it 
    # OR if Validator catches something. 
    
    # Actually, Validator is hard to trigger with just natural language unless we mess up schema.
    
    query = "Find demands for non_existent_table" 
    # This might result in empty schema selection -> potentially bad SQL -> correction attempt?
    
    print(f"\nRunning Query: {query}")
    result = orchestrator.process_query(query)
    
    print("\nResult:")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    test_correction_loop()
