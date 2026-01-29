import json
import os
import time
from difflib import SequenceMatcher

FEEDBACK_FILE = "feedback_history.json"

class FeedbackManager:
    def __init__(self):
        self.history = self._load_history()

    def _load_history(self):
        if os.path.exists(FEEDBACK_FILE):
            try:
                with open(FEEDBACK_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def log_feedback(self, query, sql, success, error_msg=None, exec_time_ms=None, row_count=None):
        """
        Log query execution result (Gratify/Penalize)
        """
        entry = {
            "timestamp": time.time(),
            "query": query,
            "sql": sql,
            "success": success,
            "error": error_msg,
            "exec_time_ms": exec_time_ms,
            "row_count": row_count
        }
        self.history.append(entry)
        self._save_history()

    def _save_history(self):
        with open(FEEDBACK_FILE, 'w') as f:
            json.dump(self.history, f, indent=4)

    def get_similar_feedback(self, current_query, limit=3):
        """
        Find relevant past examples (both good and bad)
        """
        relevant = []
        
        # Simple similarity check
        for entry in self.history:
            similarity = SequenceMatcher(None, current_query.lower(), entry["query"].lower()).ratio()
            if similarity > 0.4:  # Threshold for relevance
                relevant.append((similarity, entry))
        
        # Sort by most similar
        relevant.sort(key=lambda x: x[0], reverse=True)
        
        # Split into correct and incorrect
        correct_examples = [item[1] for item in relevant if item[1]["success"]]
        incorrect_examples = [item[1] for item in relevant if not item[1]["success"]]
        
        return correct_examples[:limit], incorrect_examples[:limit]

    def get_score_stats(self):
        if not self.history:
            return {"total": 0, "success_rate": 0}
            
        total = len(self.history)
        success = sum(1 for x in self.history if x["success"])
        return {
            "total": total,
            "success": success,
            "success_rate": round((success / total) * 100, 1)
        }
