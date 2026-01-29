"""
Few-shot examples for SQL generation
Add your own examples here to improve accuracy
"""

EXAMPLES = [
    {
        "question": "How many active demands are there?",
        "sql": "SELECT COUNT(*) as count FROM demands WHERE LOWER(status) = LOWER('active')",
        "keywords": ["count", "demands", "active", "how many"]
    },
    {
        "question": "What is the average fulfillment time for Java?",
        "sql": "SELECT AVG(fulfillment_time) as avg_time FROM demands WHERE LOWER(technology) = LOWER('Java')",
        "keywords": ["average", "fulfillment", "java", "time"]
    },
    {
        "question": "Show me open demands",
        "sql": "SELECT * FROM demands WHERE LOWER(status) = LOWER('open') ORDER BY created_at DESC",
        "keywords": ["show", "open", "demands", "list"]
    },
    {
        "question": "How many demands by practice?",
        "sql": "SELECT practice, COUNT(*) as count FROM demands GROUP BY practice ORDER BY count DESC",
        "keywords": ["count", "demands", "practice", "group"]
    },
    {
        "question": "List all users",
        "sql": "SELECT * FROM users ORDER BY created_at DESC",
        "keywords": ["list", "users", "all"]
    }
]


def get_relevant_examples(question, max_examples=3):
    """
    Get most relevant examples based on keyword matching
    Returns: list of example dicts
    """
    question_lower = question.lower()
    scored_examples = []
    
    for example in EXAMPLES:
        # Count matching keywords
        matches = sum(1 for keyword in example["keywords"] if keyword in question_lower)
        
        if matches > 0:
            scored_examples.append((matches, example))
    
    # Sort by match score and return top N
    scored_examples.sort(key=lambda x: x[0], reverse=True)
    return [ex for _, ex in scored_examples[:max_examples]]


def format_examples(examples):
    """Format examples for prompt"""
    if not examples:
        return ""
    
    formatted = "\n\nRELEVANT EXAMPLES:\n"
    for i, ex in enumerate(examples, 1):
        formatted += f"\nExample {i}:\n"
        formatted += f"Question: {ex['question']}\n"
        formatted += f"SQL: {ex['sql']}\n"
    
    return formatted