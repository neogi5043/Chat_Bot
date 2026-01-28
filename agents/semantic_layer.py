import json
import os
from typing import Dict, List, Any

class SemanticLayer:
    """
    Interface to the Semantic Layer definitions.
    """
    def __init__(self, semantic_layer_path: str = "semantic_layer"):
        self.base_path = semantic_layer_path
        self.business_metrics = self._load_json("business_metrics.json").get("business_metrics", {})
        self.data_dictionary = self._load_json("data_dictionary.json").get("data_dictionary", {})
        self.entity_mappings = self._load_json("entity_mappings.json").get("entity_mappings", {})
        self.join_paths = self._load_json("join_paths.json").get("join_paths", {})

    def _load_json(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.base_path, filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def get_categorical_columns(self, table_id: str) -> List[Any]:
        """Get columns specifically marked for entity resolution"""
        # In a real implementation, we'd check flags in data_dictionary
        # For now, we return columns that have mappings in entity_mappings
        cols = []
        for mapping_name, details in self.entity_mappings.items():
            if details.get("source_table") == table_id:
                cols.append({
                    "name": details.get("source_column"),
                    "business_term": mapping_name # simplified
                })
        return cols

    def get_entity_mappings(self, table_id: str, column_name: str) -> List[Any]:
         for mapping_name, details in self.entity_mappings.items():
            if details.get("source_table") == table_id and details.get("source_column") == column_name:
                return details.get("values", [])
         return []
