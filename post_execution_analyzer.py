"""
Post-Execution Analyzer - WORKING version that handles JOINs properly
"""
import re
from difflib import get_close_matches
import pandas as pd

def analyze_empty_result(sql, schema, db_connection=None):
    """
    Analyze why a query returned no results and suggest fixes
    
    Args:
        sql: The SQL query that returned no results or NULL
        schema: Database schema
        db_connection: Database connection to check actual values
    
    Returns:
        (suggested_sql, explanation) or (None, None)
    """
    # Extract WHERE clause values
    where_values = extract_where_values(sql)
    
    if not where_values:
        return None, None
    
    # Check for exact string matches that should use LIKE
    for column, value in where_values:
        # Check if this is a text field that might need fuzzy matching
        if any(keyword in column.lower() for keyword in ['practice', 'technology', 'status', 'name', 'title']):
            
            # If we have DB connection, find actual similar values
            if db_connection:
                # Figure out which table this column is from
                actual_table = find_table_for_column(sql, column, schema)
                
                if actual_table:
                    # Extract just the column name (without alias)
                    column_name = column.split('.')[-1] if '.' in column else column
                    
                    similar = find_similar_values_safe(db_connection, actual_table, column_name, value)
                    
                    if similar:
                        # Found similar values - suggest the best match
                        best_match = similar[0]
                        suggested_sql = sql.replace(f"'{value}'", f"'{best_match}'")
                        
                        explanation = (
                            f"No results for '{value}'. Using closest match: '{best_match}'"
                        )
                        
                        return suggested_sql, explanation
            
            # Fallback: Convert to LIKE query
            suggested_sql = convert_to_like(sql, column, value)
            
            if suggested_sql != sql:
                explanation = (
                    f"No results found with exact match '{value}'. "
                    f"Trying partial match with LIKE '%{value}%'"
                )
                
                return suggested_sql, explanation
    
    return None, None


def find_table_for_column(sql, column, schema):
    """
    Figure out which table a column belongs to by analyzing the SQL
    
    Returns: table_name or None
    """
    # If column has alias (e.g., p.practice_name)
    if '.' in column:
        alias = column.split('.')[0]
        column_name = column.split('.')[1]
        
        # Find what table this alias refers to in the FROM/JOIN clauses
        # Pattern: FROM table_name alias or JOIN table_name alias
        pattern = rf'\b(?:FROM|JOIN)\s+([a-zA-Z_]\w+)\s+{re.escape(alias)}\b'
        match = re.search(pattern, sql, re.IGNORECASE)
        
        if match:
            return match.group(1)
    else:
        # Column without alias - check schema to find which table has it
        column_name = column
    
    # Search schema for this column
    if schema and "tables" in schema:
        for table_name, columns in schema["tables"].items():
            if column_name in columns:
                return table_name
    
    return None


def extract_where_values(sql):
    """
    Extract column-value pairs from WHERE clause
    Returns: [(column, value), ...]
    """
    values = []
    
    # Pattern 1: LOWER(column) = LOWER('value')
    pattern1 = r"LOWER\(([^)]+)\)\s*=\s*LOWER\(['\"]([^'\"]+)['\"]\)"
    for match in re.finditer(pattern1, sql, re.IGNORECASE):
        column = match.group(1).strip()
        value = match.group(2).strip()
        values.append((column, value))
    
    # Pattern 2: column = 'value' (without LOWER)
    pattern2 = r"(\w+\.?\w+)\s*=\s*['\"]([^'\"]+)['\"]"
    for match in re.finditer(pattern2, sql, re.IGNORECASE):
        if 'LOWER' not in match.group(0):  # Skip if already caught by pattern1
            column = match.group(1).strip()
            value = match.group(2).strip()
            values.append((column, value))
    
    return values


def find_similar_values_safe(db_connection, table_name, column_name, search_value):
    """
    Query database to find similar values - SAFE version
    Returns: list of similar values sorted by similarity
    """
    try:
        # Simple query - just table and column, no aliases
        query = f"""
        SELECT DISTINCT {column_name} 
        FROM {table_name} 
        WHERE {column_name} IS NOT NULL 
        LIMIT 100
        """
        
        df = pd.read_sql(query, db_connection)
        
        if df.empty:
            return []
        
        actual_values = df[column_name].astype(str).tolist()
        
        # Find close matches
        matches = get_close_matches(
            search_value.lower(), 
            [v.lower() for v in actual_values], 
            n=5, 
            cutoff=0.3  # Lower threshold for more matches
        )
        
        # Return original case versions
        result = []
        for match in matches:
            for orig in actual_values:
                if orig.lower() == match:
                    result.append(orig)
                    break
        
        return result
        
    except Exception as e:
        print(f"Error finding similar values in {table_name}.{column_name}: {e}")
        return []


def convert_to_like(sql, column, value):
    """
    Convert exact match to LIKE for better fuzzy matching
    Handles both LOWER() and plain comparisons
    """
    # Escape special regex characters in column and value
    column_escaped = re.escape(column)
    value_escaped = re.escape(value)
    
    # Try replacing LOWER() version first
    pattern1 = f"LOWER\\({column_escaped}\\)\\s*=\\s*LOWER\\(['\"]({value_escaped})['\"]\\)"
    replacement1 = f"LOWER({column}) LIKE LOWER('%{value}%')"
    
    new_sql = re.sub(pattern1, replacement1, sql, flags=re.IGNORECASE)
    
    if new_sql != sql:
        return new_sql
    
    # Try plain version
    pattern2 = f"{column_escaped}\\s*=\\s*['\"]({value_escaped})['\"]"
    replacement2 = f"{column} LIKE '%{value}%'"
    
    new_sql = re.sub(pattern2, replacement2, sql, flags=re.IGNORECASE)
    
    return new_sql


def get_available_values(db_connection, sql, column, schema, limit=10):
    """
    Get list of available values in a column - for user feedback
    Handles JOINed tables correctly
    """
    try:
        # Find which table this column is in
        table_name = find_table_for_column(sql, column, schema)
        
        if not table_name:
            return []
        
        # Extract just column name (without alias)
        column_name = column.split('.')[-1] if '.' in column else column
        
        query = f"""
        SELECT DISTINCT {column_name} 
        FROM {table_name} 
        WHERE {column_name} IS NOT NULL 
        ORDER BY {column_name}
        LIMIT {limit}
        """
        
        df = pd.read_sql(query, db_connection)
        
        if df.empty:
            return []
        
        return df[column_name].tolist()
        
    except Exception as e:
        print(f"Error getting available values: {e}")
        return []


def extract_table_name(sql):
    """Extract the main table name from SQL (for backward compatibility)"""
    match = re.search(r'\bFROM\s+([a-zA-Z_]\w*)(?:\s+[a-zA-Z_]\w*)?\s', sql, re.IGNORECASE)
    if match:
        return match.group(1)
    return None