from typing import List, Dict, Any

class EntityResolverAgent:
    """
    Resolves user-provided values to actual database values.
    Currently uses simple fuzzy matching (Simulation of Vector Search).
    """
    
    def __init__(self, semantic_layer, vector_db=None):
        self.semantic_layer = semantic_layer
        self.vector_db = vector_db
        self.threshold = 0.85
    
    def resolve_entities(self, user_query: str, selected_tables: List[dict]) -> Dict[str, Any]:
        """
        For each table, extract entity references from query and map to canonical values.
        """
        resolutions = {}
        
        # Simple implementation: Iterate over all entity mappings for selected tables
        # and check if any alias is in the user query.
        
        normalized_query = user_query.lower()
        
        for table in selected_tables:
            table_id = table.get("table_id")
            
            # Get categorical columns with mappings
            categorical_cols = self.semantic_layer.get_categorical_columns(table_id)
            
            for col in categorical_cols:
                mappings = self.semantic_layer.get_entity_mappings(table_id, col["name"])
                
                for mapping in mappings:
                    # Check canonical value
                    val = mapping.get("canonical_value", "").lower()
                    if val in normalized_query:
                         resolutions[f"{table_id}.{col['name']}"] = mapping["canonical_value"]
                         continue

                    # Check aliases
                    for alias in mapping.get("aliases", []):
                        if alias.lower() in normalized_query:
                             resolutions[f"{table_id}.{col['name']}"] = mapping["canonical_value"]
                             break
        
        return resolutions
