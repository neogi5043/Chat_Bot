"""
Simple in-memory cache for SQL queries
"""
import hashlib
import time

class QueryCache:
    def __init__(self, ttl_seconds=3600):
        """
        Simple cache with time-to-live
        ttl_seconds: how long to keep cached results (default 1 hour)
        """
        self.cache = {}  # {query_hash: {"sql": str, "timestamp": float}}
        self.ttl = ttl_seconds
    
    def _hash_query(self, question):
        """Create hash from question"""
        normalized = question.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def get(self, question):
        """
        Get cached SQL for question
        Returns: sql string or None
        """
        key = self._hash_query(question)
        
        if key in self.cache:
            cached = self.cache[key]
            age = time.time() - cached["timestamp"]
            
            # Check if expired
            if age < self.ttl:
                print(f"[CACHE HIT] Retrieved SQL for: {question[:50]}...")
                return cached["sql"]
            else:
                # Remove expired entry
                del self.cache[key]
        
        print(f"[CACHE MISS] Generating SQL for: {question[:50]}...")
        return None
    
    def set(self, question, sql):
        """Cache SQL for question"""
        key = self._hash_query(question)
        self.cache[key] = {
            "sql": sql,
            "timestamp": time.time()
        }
    
    def clear(self):
        """Clear all cached entries"""
        self.cache = {}
    
    def get_stats(self):
        """Get cache statistics"""
        return {
            "entries": len(self.cache),
            "ttl_seconds": self.ttl
        }