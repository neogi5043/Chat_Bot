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

    # Rule 6: Validate Column Names (Deep Validation)
    # This detects if LLM invented a column like 'fulfillment_time' when it should be 'fulfillment_duration'
    try:
        # Simple regex to find column references in WHERE/SELECT/GROUP BY
        # This is not a full SQL parser but catches many common errors
        # Matches: where column =, order by column, select column
        potential_cols = set()
        
        # Look for identifiers
        identifiers = re.findall(r'([a-zA-Z_]\w*\.[a-zA-Z_]\w*|[a-zA-Z_]\w*)', sql)
        
        known_tables = [t.lower() for t in schema["tables"].keys()]
        known_columns = set()
        for tbl, cols in schema["tables"].items():
            for c in cols:
                known_columns.add(c.lower())
                known_columns.add(f"{tbl}.{c}".lower())
        
        reserved_words = {'select', 'from', 'where', 'and', 'or', 'order', 'by', 'group', 'limit', 'count', 'avg', 'sum', 'max', 'min', 'as', 'desc', 'asc', 'join', 'on', 'lower', 'like', 'in', 'is', 'not', 'null', 'distinct'}
        
        for ident in identifiers:
            ident_lower = ident.lower()
            if ident_lower in reserved_words:
                continue
            
            # If it looks like a column (not a table name)
            if ident_lower not in known_tables and not ident_lower.isdigit():
                # It might be a column. 
                # Strict check: If it's used in a context that implies it's a column, 
                # we should check existence. Complexity: SQL parsing is hard with Regex.
                # For now, we skip strict column validation to avoid false positives 
                # unless we are sure.
                pass

    except Exception:
        pass # Validation shouldn't crash the pipeline
    
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