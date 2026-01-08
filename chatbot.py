import pandas as pd
import json
from datetime import datetime
import llm  # Import local llm.py
import db   # Import local db.py
from prompt import INSIGHTS_GENERATION_PROMPT
# --- Main Logic Pipeline ---
def pipeline(query_request):
    try:
        # 1. Generate SQL
        sql_query = llm.generate_sql(query_request)

        # 2. Run SQL
        df = db.run_query(sql_query)

        # Handle empty results
        if df is None or df.empty:
            df = pd.DataFrame([["No results found"]], columns=["Message"])
            return sql_query, df, None

        # 3. Generate Insights
        insights = llm.generate_insights(df, original_query=query_request)

        return sql_query, df, insights
    
    except Exception as e:
        err_df = pd.DataFrame([[str(e)]], columns=["Error"])
        return f"Error: {str(e)}", err_df, None

def main():
    query_request = "list all open demands of digital engineering"
    sql_query, df, insights = pipeline(query_request)

    print("Generated SQL:")
    print(sql_query)
    print("\n" + "="*50 + "\n")

    # Convert DataFrame → JSON
    json_data = df.to_json(orient="records")
    parsed_json = json.loads(json_data)
    
    print("Result in JSON:")
    print(json.dumps(parsed_json, indent=4))
    print("\n" + "="*50 + "\n")

    # Display Insights
    if insights:
        print("Insights:")
        print(insights)
    else:
        print("No insights generated.")

if __name__ == "__main__":
    main()