"""
Simple SQL Validator - Catches common errors before execution
"""
import re

def validate_sql(sql, schema):
    """
    Validates SQL query against schema
    Returns: (is_valid: bool, errors: list)
    """
    errors = []
    sql_upper = sql.upper()
    
    # Rule 1: Only allow SELECT queries
    if not sql.strip().upper().startswith("SELECT"):
        errors.append("Query must start with SELECT")
        return False, errors
    
    # Rule 2: Block write operations
    write_ops = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'TRUNCATE', 'CREATE']
    for op in write_ops:
        if re.search(rf'\b{op}\b', sql_upper):
            errors.append(f"Write operation {op} not allowed")
            return False, errors
    
    # Rule 3: Validate table names
    tables = set(schema["tables"].keys())
    
    # Extract table names after FROM and JOIN
    table_pattern = r'\b(?:FROM|JOIN)\s+([a-zA-Z_]\w*)'
    for match in re.finditer(table_pattern, sql, re.IGNORECASE):
        table_name = match.group(1)
        if table_name.lower() not in [t.lower() for t in tables]:
            errors.append(f"Table '{table_name}' does not exist in schema")
    
    # Rule 4: Check for common SQL syntax issues
    if sql.count('(') != sql.count(')'):
        errors.append("Unbalanced parentheses")
    
    # Rule 5: Check for incomplete queries
    if '...' in sql or 'TODO' in sql_upper or 'PLACEHOLDER' in sql_upper:
        errors.append("Query contains placeholders or is incomplete")
    
    return len(errors) == 0, errors


def attempt_fix(sql, errors, schema):
    """
    Simple auto-fix for common issues
    Returns: fixed_sql or None if can't fix
    """
    fixed = sql
    
    # Fix 1: Remove markdown code fences if present
    fixed = re.sub(r"^```sql\s*|\s*```$", "", fixed.strip(), flags=re.MULTILINE)
    
    # Fix 2: Remove comments
    fixed = re.sub(r'--.*$', '', fixed, flags=re.MULTILINE)
    
    # Fix 3: Trim whitespace
    fixed = fixed.strip()
    
    # Check if auto-fixes resolved issues
    is_valid, remaining_errors = validate_sql(fixed, schema)
    
    if is_valid:
        return fixed
    
    return None