
import sys
import os
import pandas as pd
from sqlalchemy import text

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from common.db import get_sqlalchemy_engine

def debug_data():
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        print("\n=== DEMAND ACTIVITY SAMPLE ===")
        print(pd.read_sql(text("SELECT * FROM demand_activity LIMIT 10"), conn))
        
        print("\n=== DISTINCT ACTIONS ===")
        print(pd.read_sql(text("SELECT DISTINCT action FROM demand_activity"), conn))

        print("\n=== DEMANDS SAMPLE (for Technology/Description) ===")
        print(pd.read_sql(text("SELECT demand_id, job_description, practice_id FROM demands LIMIT 5"), conn))

        print("\n=== PRACTICES SAMPLE ===")
        print(pd.read_sql(text("SELECT * FROM practices LIMIT 5"), conn))


if __name__ == "__main__":
    debug_data()
