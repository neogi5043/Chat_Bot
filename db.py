
import psycopg2
import pandas as pd
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables
load_dotenv()

def get_connection():
    """Establishes connection to PostgreSQL"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=os.getenv("DB_PORT")
    )

def get_sqlalchemy_engine():
    """Creates SQLAlchemy engine for pandas"""
    db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    return create_engine(db_url)

def fetch_schema():
    """Fetches table and column names with data types and foreign key relationships"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = cursor.fetchall()
    
    db_structure = {
        "tables": {},
        "relationships": []
    }
    
    # Get columns with data types for each table
    for (table_name,) in tables:
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        columns = cursor.fetchall()
        # Store both column name and data type
        db_structure["tables"][table_name] = {col[0]: col[1] for col in columns}
    
    # Get foreign key relationships
    cursor.execute("""
        SELECT
            tc.table_name AS from_table,
            kcu.column_name AS from_column,
            ccu.table_name AS to_table,
            ccu.column_name AS to_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.column_name;
    """)
    
    relationships = cursor.fetchall()
    for rel in relationships:
        db_structure["relationships"].append({
            "from_table": rel[0],
            "from_column": rel[1],
            "to_table": rel[2],
            "to_column": rel[3]
        })
    
    cursor.close()
    conn.close()
    return db_structure

def run_query(sql):
    """Executes SQL and returns a Pandas DataFrame"""
    engine = None
    try:
        engine = get_sqlalchemy_engine()
        df = pd.read_sql(sql, engine)
        return df
    except Exception as e:
        print(f"Error running query: {e}")
        return None
    finally:
        if engine:
            engine.dispose()