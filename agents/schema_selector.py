from typing import List, Any

class SchemaSelectorAgent:
    """
    Selects top-K relevant tables from large databases.
    Currently uses simple keyword matching (Simulation of Vector Search).
    """
    
    def __init__(self, semantic_layer, vector_db=None):
        self.semantic_layer = semantic_layer
        self.vector_db = vector_db # Placeholder for Phase 2
        self.top_k = 5
        self.common_terms = {
            "demand_activity": ["history", "updated", "change", "audit", "log", "activity", "action", "detail", "activities"],
            "demand_cancellations": ["cancel", "reason", "revoked", "dropped", "cancelled", "canceling"],
            "demand_cvs": ["resume", "cv", "file", "download", "attachment", "document"],
            "managers": ["manager", "lead", "owner"],
            "users": ["user", "login", "admin", "role"]
        }
    
    def select_schema(self, user_query: str) -> List[dict]:
        """
        1. Identify potential tables based on query keywords matching data dictionary terms.
        2. Expand with join paths.
        """
        candidates = set()
        
        # Check Common Terms
        if hasattr(self, 'common_terms'):
            for table, terms in self.common_terms.items():
                for term in terms:
                    if term in user_query.lower():
                        candidates.add(table)
        
        # Simple Keyword Match Simulation
        query_lower = user_query.lower()
        
        # Check Data Dictionary
        for table_id, details in self.semantic_layer.data_dictionary.items():
            # Check table name
            if table_id in query_lower or details.get("business_name", "").lower() in query_lower:
                candidates.add(table_id)
                continue
            
            # Check column names/descriptions
            for col_name, col_details in details.get("columns", {}).items():
                if col_name in query_lower or col_details.get("business_term", "").lower() in query_lower:
                    candidates.add(table_id)
                    break
        
        # Check Business Metrics
        for metric_name, metric_details in self.semantic_layer.business_metrics.items():
             if metric_name.replace("_", " ") in query_lower or metric_details.get("name", "").lower() in query_lower:
                 for table in metric_details.get("required_tables", []):
                     candidates.add(table)

        # Fallback: If no candidates, return everything (safe default for small schema involved in Phase 1)
        # Or better: return a default set.
        if not candidates:
            # Fallback: If no specific matches, return core tables to give LLM a chance
            # rather than failing with 0 tables.
            candidates = {"demands", "candidates", "accounts", "users"}
            
        # Expand with Joins (Simplified)
        # In a real graph, we'd traverse. Here we check 1-hop based on join_paths
        final_selection = list(candidates)
        
        return self._fetch_table_schemas(final_selection)
    
    def _fetch_table_schemas(self, table_ids: List[str]) -> List[dict]:
        """
        Hydrate the selection with full schema details from Data Dictionary
        """
        schemas = []
        for tid in table_ids:
            if tid in self.semantic_layer.data_dictionary:
                schemas.append(self.semantic_layer.data_dictionary[tid])
        return schemas
