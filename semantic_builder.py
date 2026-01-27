import json
import logging
import pandas as pd
from sqlalchemy import create_engine, inspect
import db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def build_semantic_layer(output_file='semantic_schema.json', limit_per_column=50):
    """
    Scans the database to find distinct values for categorical columns (text/varchar).
    Saves the result to a JSON file.
    """
    logger.info("Starting Semantic Layer Build...")
    
    try:
        engine = db.get_sqlalchemy_engine()
        inspector = inspect(engine)
        
        table_names = inspector.get_table_names()
        semantic_data = {}
        
        for table in table_names:
            logger.info(f"Analyzing table: {table}")
            semantic_data[table] = {}
            
            columns = inspector.get_columns(table)
            
            for col in columns:
                col_name = col['name']
                col_type = str(col['type']).lower()
                
                # We are interested in text/string columns that might be categorical
                # Skipping typical ID columns or huge text fields
                if ('char' in col_type or 'text' in col_type) and 'id' not in col_name.lower():
                    
                    try:
                        # Check cardinality (number of unique values)
                        # We only want categorical data, not unique descriptions per row
                        count_query = f"SELECT COUNT(DISTINCT \"{col_name}\") FROM \"{table}\""
                        with engine.connect() as conn:
                            distinct_count = conn.execute(db.text(count_query)).scalar()
                        
                        # Heuristic: If cardinality is low (heuristic < 100) or reasonable compared to table size
                        # For this specialized chatbot, we can be a bit more generous, say < 200 distinct values
                        if 0 < distinct_count <= 200:
                            logger.info(f"  - Fetching values for categorical column: {col_name} ({distinct_count} unique)")
                            
                            query = f"SELECT DISTINCT \"{col_name}\" FROM \"{table}\" WHERE \"{col_name}\" IS NOT NULL LIMIT {limit_per_column}"
                            df = pd.read_sql(query, engine)
                            values = df[col_name].tolist()
                            
                            if values:
                                semantic_data[table][col_name] = values
                        else:
                            logger.info(f"  - Skipping {col_name} (High cardinality: {distinct_count})")
                            
                    except Exception as e:
                        logger.warning(f"  - Could not analyze column {col_name}: {e}")
                        
        # Save to file
        with open(output_file, 'w') as f:
            json.dump(semantic_data, f, indent=4)
            
        logger.info(f"Semantic layer built successfully! Saved to {output_file}")
        return semantic_data
        
    except Exception as e:
        logger.error(f"Failed to build semantic layer: {e}")
        return None

if __name__ == "__main__":
    # Ensure db.py has 'text' imported from sqlalchemy or handle it here
    # Since db.py might not export text, we will patch it or rely on pandas read_sql
    # To be safe, let's fix the db.text issue dynamically if needed, 
    # but db.py usually doesn't export 'text'. 
    # Let's import text directly from sqlalchemy here.
    from sqlalchemy import text
    # Monkey patch db to have text if it doesn't (just for this script's context if we used db.text)
    db.text = text
    
    build_semantic_layer()
