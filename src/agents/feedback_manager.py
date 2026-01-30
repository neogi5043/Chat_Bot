import json
import os
import uuid
from typing import List, Dict, Any

FEEDBACK_FILE = "feedback_history.json"
FEW_SHOT_FILE = "training_data/few_shot_examples.json"

class FeedbackManager:
    """
    Manages the Active Learning Loop.
    1. Logs feedback (failures/successes).
    2. Retrieves relevant feedback for prompt injection.
    3. Manages the 'Few-Shot' database of correct examples.
    """
    
    def __init__(self):
        self.history = self._load_history()
        self.few_shots = self._load_few_shots()

    def _load_history(self) -> List[dict]:
        if os.path.exists(FEEDBACK_FILE):
            try:
                with open(FEEDBACK_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def _load_few_shots(self) -> List[dict]:
        if os.path.exists(FEW_SHOT_FILE):
            try:
                with open(FEW_SHOT_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def log_feedback(self, query, sql, success, error_msg=None, user_correction=None):
        """Log a feedback event"""
        entry = {
            "id": str(uuid.uuid4()),
            "query": query,
            "sql": sql,
            "success": success,
            "error": error_msg,
            "user_correction": user_correction,
            "timestamp": "TODO_TIMESTAMP" # In real app, import datetime
        }
        self.history.append(entry)
        self._save_history()
        
        # If user provided a correction, add to few-shots immediately
        if user_correction:
            self.add_few_shot(query, user_correction)

    def add_few_shot(self, query, sql):
        """Add a verified example to the few-shot database"""
        entry = {
            "id": str(uuid.uuid4()),
            "user_question": query,
            "sql": sql,
            "execution_success": True
        }
        self.few_shots.append(entry)
        self._save_few_shots()

    def _save_history(self):
        with open(FEEDBACK_FILE, 'w') as f:
            json.dump(self.history, f, indent=2)

    def _save_few_shots(self):
        # ensure dir exists
        os.makedirs(os.path.dirname(FEW_SHOT_FILE), exist_ok=True)
        with open(FEW_SHOT_FILE, 'w') as f:
            json.dump(self.few_shots, f, indent=2)

    def get_similar_feedback(self, query: str, top_k=3):
        """
        Retrieve relevant positive (few-shot) and negative (history) examples.
        Currently simple text match - in future use Vector DB.
        """
        # 1. Get Negative Examples (mistakes to avoid)
        incorrect = [
            item for item in self.history 
            if not item['success'] and self._calculate_similarity(query, item['query']) > 0.3
        ]
        
        # 2. Get Positive Examples (few-shots to emulate)
        # Calculate scores first
        scored_correct = []
        for item in self.few_shots:
            score = self._calculate_similarity(query, item['user_question'])
            if score > 0.3:
                scored_correct.append((score, item))
        
        # Sort by score (ascending) so that [-top_k:] gives the highest scores
        scored_correct.sort(key=lambda x: x[0])
        correct = [item for _, item in scored_correct]
        
        # Do same for incorrect (mistakes to avoid)
        scored_incorrect = []
        for item in self.history:
            if not item['success']:
                score = self._calculate_similarity(query, item['query'])
                if score > 0.3:
                    scored_incorrect.append((score, item))
        
        scored_incorrect.sort(key=lambda x: x[0])
        incorrect = [item for _, item in scored_incorrect]

        return correct[-top_k:], incorrect[-top_k:]

    def _calculate_similarity(self, q1, q2):
        # Jaccard similarity on tokens
        if not q1 or not q2: return 0.0
        s1 = set(q1.lower().split())
        s2 = set(q2.lower().split())
        return len(s1.intersection(s2)) / len(s1.union(s2))
