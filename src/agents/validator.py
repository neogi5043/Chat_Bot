from typing import List, Tuple, Dict
import re

class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings
        
from src.common.db import release_connection

class ValidatorAgent:
    """
    Validates generated SQL before execution.
    Catches syntax errors, schema violations, and logical issues.
    """
    
    def __init__(self, database_connection_factory):
        self.get_db_connection = database_connection_factory
    
    def validate(self, sql: str, selected_schema: List[dict]) -> ValidationResult:
        """
        Run multiple validation checks.
        """
        errors = []
        warnings = []
        
        # Check 1: SQL Syntax via EXPLAIN (safest check)
        syntax_ok, syntax_errors = self._validate_syntax(sql)
        if not syntax_ok:
            errors.extend(syntax_errors)
        
        # Check 2: Basic Schema Compliance (Regex based)
        # In a robust system, we'd use a parser. Here we filter simple mismatches.
        for table in selected_schema:
            t_id = table.get("table_id")
            # If the query seems to reference this table but gets columns wrong...
            # This is hard to do reliably with just regex. 
            # We will rely on EXPLAIN to catch "column does not exist" errors.
            pass
            
        # Check 3: Logic
        if "COUNT(" in sql.upper() and "GROUP BY" not in sql.upper() and "HAVING" in sql.upper():
             # Logic warning
             warnings.append("Possible Logic Issue: Aggregation without GROUP BY")

        return ValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings
        )
    
    def _validate_syntax(self, sql: str) -> Tuple[bool, List[str]]:
        """
        Test query syntax using EXPLAIN (non-destructive).
        """
        conn = None
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            
            # Use EXPLAIN to check validity without executing
            # Postgres supports `EXPLAIN (FORMAT JSON) ...`
            cur.execute(f"EXPLAIN {sql}")
            cur.close()
            return True, []
        except Exception as e:
            msg = str(e).split('\n')[0] # First line usually has the error
            return False, [f"Syntax Error: {msg}"]
        finally:
            if conn:
                release_connection(conn)
