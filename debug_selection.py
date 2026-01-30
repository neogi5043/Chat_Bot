
import sys
import os
import json

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from agents.schema_selector import SchemaSelectorAgent
from agents.semantic_layer import SemanticLayer

def debug_selection():
    print("Initializing SchemaSelector...")
    semantic_layer = SemanticLayer()
    selector = SchemaSelectorAgent(semantic_layer)
    
    query = "What is the resume intake to select ratio?"
    print(f"\nQuery: {query}")
    
    selected_schema = selector.select_schema(query)
    # select_schema returns a List[dict] where each dict is the table schema
    table_ids = [schema.get('table_id') for schema in selected_schema]
    print(f"\nSelected Tables: {table_ids}")
    
    if "candidates" in table_ids:
        print("[PASS] Selected 'candidates' table.")
    else:
        print("[FAIL] Did NOT select 'candidates' table.")

    if "demand_cvs" in table_ids:
        print("[WARN] Selected 'demand_cvs' table (should ideally be avoided).")

if __name__ == "__main__":
    debug_selection()
