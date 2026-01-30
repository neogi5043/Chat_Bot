
import sys
import os
import json

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from agents.schema_selector import SchemaSelectorAgent
from agents.semantic_layer import SemanticLayer

def debug_lc_selection():
    print("Initializing SchemaSelector...")
    semantic_layer = SemanticLayer()
    selector = SchemaSelectorAgent(semantic_layer)
    
    query = "What is the most time taking phase in the demand life cycle technology wise?"
    print(f"\nQuery: {query}")
    
    selected_schema = selector.select_schema(query)
    table_ids = [schema.get('table_id') for schema in selected_schema]
    print(f"\nSelected Tables: {table_ids}")
    
    if "practices" in table_ids:
        print("[PASS] Selected 'practices'.")
    else:
        print("[FAIL] Missed 'practices'.")

    if "demands" in table_ids:
        print("[PASS] Selected 'demands'.")
    else:
        print("[FAIL] Missed 'demands'.")

if __name__ == "__main__":
    debug_lc_selection()
