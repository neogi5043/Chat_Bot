
import sys
import os
import pandas as pd
from sqlalchemy import text

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from common.db import get_sqlalchemy_engine

def check_schema():
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        print("\n=== CHECKING TABLES ===")
        tables = pd.read_sql(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"), conn)
        print(tables)
        
        if 'candidates' in tables['tablename'].values:
            print("\n=== CANDIDATES COLUMNS ===")
            cols = pd.read_sql(text("SELECT * FROM candidates LIMIT 0"), conn).columns.tolist()
            print(cols)
            
            print("\n=== CANDIDATES SAMPLE STATUSES ===")
            print(pd.read_sql(text("SELECT DISTINCT interview_status FROM candidates"), conn))

        if 'demand_cvs' in tables['tablename'].values:
            print("\n=== DEMAND_CVS COLUMNS ===")
            cols = pd.read_sql(text("SELECT * FROM demand_cvs LIMIT 0"), conn).columns.tolist()
            print(cols)

if __name__ == "__main__":
    check_schema()
